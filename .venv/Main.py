from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox, QColorDialog,
    QFileDialog, QMenuBar, QMenu, QMessageBox, QTabWidget, QDialog,
    QDialogButtonBox, QFormLayout, QTextEdit, QGroupBox, QCheckBox,
    QToolButton, QSplitter, QListWidget, QListWidgetItem, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem,
    QGraphicsPolygonItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsPixmapItem,
    QGraphicsProxyWidget, QFrame, QScrollArea, QDockWidget, QToolTip
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QAction, QCursor, QPolygonF, QFont, QPixmap,
    QImage, QBrush, QPainterPath, QIcon, QKeySequence, QTextCharFormat,
    QTextCursor, QTextBlockFormat, QTextOption
)
from PySide6.QtCore import (
    Qt, QPointF, QRectF, QSizeF, QPropertyAnimation, QEasingCurve,
    QTimer, Signal, QObject, QPoint, QSize, QParallelAnimationGroup
)
from math import sin, cos, pi, atan2, sqrt
import sys
import json
import os
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any


class ElementType(Enum):
    """Типы элементов на холсте"""
    POINT = "point"
    LINE = "line"
    STRAIGHT = "straight"
    TRIANGLE = "triangle"
    RECT = "rect"
    CIRCLE = "circle"
    PENTAGON = "pentagon"
    HEXAGON = "hexagon"
    ARROW = "arrow"
    TEXT = "text"
    BUTTON = "button"
    INPUT = "input"
    MENU = "menu"
    ICON = "icon"
    IMAGE = "image"
    LINK = "link"


class AlignmentType(Enum):
    """Типы выравнивания"""
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    CENTER_H = "center_h"
    CENTER_V = "center_v"
    CENTER = "center"
    DISTRIBUTE_H = "distribute_h"
    DISTRIBUTE_V = "distribute_v"


class CanvasElement(QObject):
    """Базовый класс для элементов на холсте"""
    changed = Signal()

    def __init__(self, element_type: ElementType, position: QPointF, parent=None):
        super().__init__(parent)
        self.element_type = element_type
        self.position = position
        self.size = QSizeF(100, 100)
        self.selected = False
        self.color = QColor(150, 0, 150)
        self.z_value = 0
        self.data = {}  # Дополнительные данные элемента

    def get_bounds(self) -> QRectF:
        """Возвращает границы элемента"""
        return QRectF(self.position, self.size)

    def contains_point(self, point: QPointF) -> bool:
        """Проверяет, содержит ли элемент точку"""
        return self.get_bounds().contains(point)

    def move(self, delta: QPointF):
        """Перемещает элемент"""
        self.position += delta
        self.changed.emit()

    def set_size(self, size: QSizeF):
        """Устанавливает размер элемента"""
        self.size = size
        self.changed.emit()

    def to_dict(self) -> Dict:
        """Сериализация элемента"""
        return {
            'type': self.element_type.value,
            'position': (self.position.x(), self.position.y()),
            'size': (self.size.width(), self.size.height()),
            'color': self.color.name(),
            'z_value': self.z_value,
            'data': self.data
        }

    @staticmethod
    def from_dict(data: Dict) -> 'CanvasElement':
        """Десериализация элемента"""
        element = CanvasElement(
            ElementType(data['type']),
            QPointF(data['position'][0], data['position'][1])
        )
        element.size = QSizeF(data['size'][0], data['size'][1])
        element.color = QColor(data['color'])
        element.z_value = data.get('z_value', 0)
        element.data = data.get('data', {})
        return element


class Canvas(QWidget):
    """Холст для рисования"""

    def __init__(self, canvas_id: str, get_tool_callback, parent=None):
        super().__init__(parent)
        self.canvas_id = canvas_id
        self.get_tool = get_tool_callback

        # Элементы на холсте
        self.elements: List[CanvasElement] = []
        self.selected_elements: List[CanvasElement] = []

        # Состояние рисования
        self.drawing = False
        self.current_element: Optional[CanvasElement] = None
        self.start_point: Optional[QPointF] = None
        self.current_points: List[QPointF] = []

        # Состояние выделения
        self.selection_start: Optional[QPointF] = None
        self.selection_rect: Optional[QRectF] = None
        self.dragging = False
        self.drag_start: Optional[QPointF] = None
        self.resize_handle: Optional[int] = None

        # Настройки
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Подсказки
        self.tooltip_timer = QTimer()
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self.show_tooltip)
        self.tooltip_element = None

    def add_element(self, element: CanvasElement):
        """Добавляет элемент на холст"""
        self.elements.append(element)
        element.changed.connect(self.update)
        self.update()

    def remove_element(self, element: CanvasElement):
        """Удаляет элемент с холста"""
        if element in self.elements:
            self.elements.remove(element)
        if element in self.selected_elements:
            self.selected_elements.remove(element)
        self.update()

    def select_element(self, element: CanvasElement, add_to_selection=False):
        """Выделяет элемент"""
        if not add_to_selection:
            self.clear_selection()
        if element not in self.selected_elements:
            self.selected_elements.append(element)
            element.selected = True
        self.update()

    def clear_selection(self):
        """Снимает выделение со всех элементов"""
        for element in self.selected_elements:
            element.selected = False
        self.selected_elements.clear()
        self.update()

    def get_element_at(self, point: QPointF) -> Optional[CanvasElement]:
        """Возвращает элемент в указанной точке"""
        # Проверяем в обратном порядке (сверху вниз)
        for element in reversed(self.elements):
            if element.contains_point(point):
                return element
        return None

    def get_elements_in_rect(self, rect: QRectF) -> List[CanvasElement]:
        """Возвращает все элементы в прямоугольнике"""
        result = []
        for element in self.elements:
            if rect.intersects(element.get_bounds()):
                result.append(element)
        return result

    def regular_polygon(self, center: QPointF, size: float, sides: int) -> List[QPointF]:
        """Создает правильный многоугольник"""
        radius = size / 2
        points = []
        for i in range(sides):
            angle = 2 * pi * i / sides - pi / 2
            x = center.x() + radius * cos(angle)
            y = center.y() + radius * sin(angle)
            points.append(QPointF(x, y))
        return points

    def arrow_head(self, start: QPointF, end: QPointF, size: float = 30) -> Tuple[QPointF, QPointF]:
        """Создает наконечник стрелки"""
        angle = atan2(end.y() - start.y(), end.x() - start.x())
        left = angle + pi - pi / 6
        right = angle + pi + pi / 6

        p1 = QPointF(end.x() + size * cos(left), end.y() + size * sin(left))
        p2 = QPointF(end.x() + size * cos(right), end.y() + size * sin(right))
        return p1, p2

    def get_resize_handle(self, point: QPointF, bounds: QRectF) -> Optional[int]:
        """Определяет, какой маркер изменения размера находится в точке"""
        handles = [
            QPointF(bounds.left(), bounds.top()),  # 0: верхний левый
            QPointF(bounds.center().x(), bounds.top()),  # 1: верхний центр
            QPointF(bounds.right(), bounds.top()),  # 2: верхний правый
            QPointF(bounds.right(), bounds.center().y()),  # 3: правый центр
            QPointF(bounds.right(), bounds.bottom()),  # 4: нижний правый
            QPointF(bounds.center().x(), bounds.bottom()),  # 5: нижний центр
            QPointF(bounds.left(), bounds.bottom()),  # 6: нижний левый
            QPointF(bounds.left(), bounds.center().y())  # 7: левый центр
        ]

        handle_size = 8
        for i, handle in enumerate(handles):
            if (point - handle).manhattanLength() < handle_size:
                return i
        return None

    def mousePressEvent(self, event):
        pos = event.position()
        tool = self.get_tool()

        # Проверка клика по ссылке (вне зависимости от инструмента)
        if event.button() == Qt.LeftButton:
            element = self.get_element_at(pos)
            if element and element.element_type == ElementType.LINK:
                target_canvas_id = element.data.get('target_canvas')
                animate = element.data.get('animate', True)
                if target_canvas_id:
                    # Получаем главное окно через parent chain
                    parent = self.parent()
                    while parent and not isinstance(parent, QMainWindow):
                        parent = parent.parent()
                    if parent and hasattr(parent, 'navigate_to_canvas'):
                        parent.navigate_to_canvas(target_canvas_id, animate)
                return

        if event.button() == Qt.LeftButton:
            if tool == "select":
                # Режим выделения
                element = self.get_element_at(pos)
                if element:
                    self.select_element(element, event.modifiers() & Qt.ControlModifier)
                    self.dragging = True
                    self.drag_start = pos
                else:
                    self.clear_selection()
                    self.selection_start = pos
                    self.selection_rect = QRectF(pos, QSizeF(0, 0))
            else:
                # Режим рисования
                self.start_point = pos
                self.drawing = True
                self.current_points = [pos]

                if tool == "point":
                    element = CanvasElement(ElementType.POINT, pos)
                    element.size = QSizeF(5, 5)
                    element.data = {'radius': 5}
                    self.add_element(element)
                    self.drawing = False
                elif tool == "line":
                    # Кривая линия - начинаем сбор точек
                    pass
                elif tool in ["straight", "arrow"]:
                    # Прямая линия или стрелка
                    element = CanvasElement(ElementType.STRAIGHT if tool == "straight" else ElementType.ARROW, pos)
                    element.data = {'end': pos}
                    self.current_element = element
                elif tool == "triangle":
                    element = CanvasElement(ElementType.TRIANGLE, pos)
                    element.data = {'end': pos}
                    self.current_element = element
                elif tool == "rect":
                    element = CanvasElement(ElementType.RECT, pos)
                    element.data = {'end': pos}
                    self.current_element = element
                elif tool == "circle":
                    element = CanvasElement(ElementType.CIRCLE, pos)
                    element.data = {'end': pos}
                    self.current_element = element
                elif tool in ["pentagon", "hexagon"]:
                    element = CanvasElement(ElementType.PENTAGON if tool == "pentagon" else ElementType.HEXAGON, pos)
                    element.data = {'end': pos}
                    self.current_element = element
                elif tool == "text":
                    element = CanvasElement(ElementType.TEXT, pos)
                    element.data = {
                        'text': 'Текст',
                        'font_family': 'Arial',
                        'font_size': 12,
                        'alignment': Qt.AlignLeft,
                        'color': QColor(0, 0, 0).name()
                    }
                    self.add_element(element)
                    self.drawing = False
                elif tool == "button":
                    element = CanvasElement(ElementType.BUTTON, pos)
                    element.data = {'text': 'Кнопка', 'width': 100, 'height': 30}
                    element.size = QSizeF(100, 30)
                    self.add_element(element)
                    self.drawing = False
        elif tool == "input":
            element = CanvasElement(ElementType.INPUT, pos)
            element.data = {'placeholder': 'Введите текст', 'width': 150, 'height': 25}
            element.size = QSizeF(150, 25)
            self.add_element(element)
            self.drawing = False
        elif tool == "menu":
            element = CanvasElement(ElementType.MENU, pos)
            element.data = {'items': ['Пункт 1', 'Пункт 2', 'Пункт 3'], 'width': 120, 'height': 25}
            element.size = QSizeF(120, 25)
            self.add_element(element)
            self.drawing = False
        elif tool == "icon":
            element = CanvasElement(ElementType.ICON, pos)
            element.data = {'icon_type': 'default', 'size': 32}
            element.size = QSizeF(32, 32)
            self.add_element(element)
            self.drawing = False
        elif tool == "image":
            # Загрузка изображения будет обработана отдельно
            pass
        elif tool == "link":
            # Создание ссылки будет обработано через диалог
            pass

        if event.button() == Qt.RightButton:
            # Контекстное меню
            element = self.get_element_at(pos)
            if element:
                self.show_context_menu(element, event.globalPos())

    def mouseMoveEvent(self, event):
        pos = event.position()
        tool = self.get_tool()

        # Подсказки
        element = self.get_element_at(pos)
        if element != self.tooltip_element:
            self.tooltip_timer.stop()
            self.tooltip_element = element
            if element:
                self.tooltip_timer.start(500)  # Показать через 500мс

        if tool == "select" and self.dragging and self.drag_start and self.selected_elements:
            # Перемещение выделенных элементов
            delta = pos - self.drag_start
            for element in self.selected_elements:
                element.move(delta)
            self.drag_start = pos
            self.update()
        elif tool == "select" and self.selection_start:
            # Рисование прямоугольника выделения
            self.selection_rect = QRectF(self.selection_start, pos).normalized()
            self.update()
        elif self.drawing:
            if tool == "line":
                # Кривая линия
                self.current_points.append(pos)
                self.update()
            elif self.current_element:
                # Обновление размера элемента
                end = pos
                self.current_element.data['end'] = end

                if tool in ["straight", "arrow"]:
                    # Прямая линия или стрелка
                    dx = end.x() - self.start_point.x()
                    dy = end.y() - self.start_point.y()
                    self.current_element.size = QSizeF(sqrt(dx * dx + dy * dy), 1)
                elif tool == "rect":
                    # Прямоугольник
                    x = min(self.start_point.x(), end.x())
                    y = min(self.start_point.y(), end.y())
                    w = abs(end.x() - self.start_point.x())
                    h = abs(end.y() - self.start_point.y())
                    self.current_element.position = QPointF(x, y)
                    self.current_element.size = QSizeF(w, h)
                elif tool in ["circle", "triangle", "pentagon", "hexagon"]:
                    # Фигуры с размером
                    size = min(abs(end.x() - self.start_point.x()), abs(end.y() - self.start_point.y()))
                    self.current_element.size = QSizeF(size, size)

                self.update()

    def mouseDoubleClickEvent(self, event):
        """Обработка двойного клика для редактирования элементов"""
        if event.button() == Qt.LeftButton:
            pos = event.position()
            element = self.get_element_at(pos)
            if element:
                self.edit_element(element)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            tool = self.get_tool()

            if tool == "select" and self.selection_start:
                # Завершение выделения
                if self.selection_rect:
                    elements = self.get_elements_in_rect(self.selection_rect)
                    for element in elements:
                        self.select_element(element, True)
                self.selection_start = None
                self.selection_rect = None
                self.update()
            elif tool == "select":
                self.dragging = False
                self.drag_start = None
            elif self.drawing:
                if tool == "line" and len(self.current_points) > 1:
                    # Сохранение кривой линии
                    element = CanvasElement(ElementType.LINE, self.current_points[0])
                    element.data = {'points': [(p.x(), p.y()) for p in self.current_points]}
                    # Вычисляем размеры
                    xs = [p.x() for p in self.current_points]
                    ys = [p.y() for p in self.current_points]
                    element.position = QPointF(min(xs), min(ys))
                    element.size = QSizeF(max(xs) - min(xs), max(ys) - min(ys))
                    self.add_element(element)
                    self.current_points = []
                elif self.current_element:
                    # Сохранение элемента
                    self.add_element(self.current_element)
                    self.current_element = None

                self.drawing = False
                self.update()

    def show_tooltip(self):
        """Показывает подсказку для элемента"""
        if self.tooltip_element:
            tooltip_text = self.get_tooltip_text(self.tooltip_element)
            if tooltip_text:
                QToolTip.showText(QCursor.pos(), tooltip_text, self)

    def get_tooltip_text(self, element: CanvasElement) -> str:
        """Возвращает текст подсказки для элемента"""
        tooltips = {
            ElementType.POINT: "Точка - базовый элемент",
            ElementType.LINE: "Кривая линия - рисуется от руки",
            ElementType.STRAIGHT: "Прямая линия - соединяет две точки",
            ElementType.TRIANGLE: "Треугольник - правильный треугольник",
            ElementType.RECT: "Прямоугольник - можно изменять размер",
            ElementType.CIRCLE: "Круг - можно изменять размер",
            ElementType.PENTAGON: "Пятиугольник - правильный многоугольник",
            ElementType.HEXAGON: "Шестиугольник - правильный многоугольник",
            ElementType.ARROW: "Стрелка - указывает направление",
            ElementType.TEXT: "Текст - двойной клик для редактирования",
            ElementType.BUTTON: "Кнопка - элемент интерфейса. Двойной клик для редактирования",
            ElementType.INPUT: "Поле ввода - элемент интерфейса. Двойной клик для редактирования",
            ElementType.MENU: "Меню - элемент интерфейса. Двойной клик для редактирования",
            ElementType.ICON: "Иконка - графический элемент. Двойной клик для редактирования",
            ElementType.IMAGE: "Изображение - внешний файл",
            ElementType.LINK: "Ссылка - переход на другой холст"
        }
        return tooltips.get(element.element_type, "Элемент")

    def show_context_menu(self, element: CanvasElement, global_pos: QPoint):
        """Показывает контекстное меню для элемента"""
        menu = QMenu(self)

        edit_action = menu.addAction("Редактировать")
        delete_action = menu.addAction("Удалить")
        menu.addSeparator()
        align_action = menu.addAction("Выровнять...")
        link_action = menu.addAction("Создать ссылку...")

        action = menu.exec(global_pos)
        if action == delete_action:
            self.remove_element(element)
        elif action == edit_action:
            self.edit_element(element)
        elif action == align_action:
            self.show_alignment_dialog()
        elif action == link_action:
            # Выделяем элемент и создаем ссылку
            self.select_element(element)
            # Сигнализируем главному окну о необходимости создать ссылку
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            if parent and hasattr(parent, 'create_link_for_element'):
                parent.create_link_for_element(element)

    def edit_element(self, element: CanvasElement):
        """Редактирует элемент"""
        if element.element_type == ElementType.TEXT:
            dialog = QDialog(self)
            dialog.setWindowTitle("Редактирование текста")
            layout = QVBoxLayout(dialog)

            text_edit = QTextEdit()
            text_edit.setPlainText(element.data.get('text', ''))
            layout.addWidget(QLabel("Текст:"))
            layout.addWidget(text_edit)

            # Настройки шрифта
            font_family = QComboBox()
            font_family.addItems(['Arial', 'Times New Roman', 'Courier New', 'Verdana'])
            font_family.setCurrentText(element.data.get('font_family', 'Arial'))
            layout.addWidget(QLabel("Шрифт:"))
            layout.addWidget(font_family)

            font_size = QSpinBox()
            font_size.setRange(8, 72)
            font_size.setValue(element.data.get('font_size', 12))
            layout.addWidget(QLabel("Размер:"))
            layout.addWidget(font_size)

            # Выравнивание
            alignment = QComboBox()
            alignment.addItems(['Слева', 'По центру', 'Справа'])
            current_align = element.data.get('alignment', Qt.AlignLeft)
            if current_align == Qt.AlignCenter:
                alignment.setCurrentIndex(1)
            elif current_align == Qt.AlignRight:
                alignment.setCurrentIndex(2)
            layout.addWidget(QLabel("Выравнивание:"))
            layout.addWidget(alignment)

            # Цвет
            color_btn = QPushButton("Выбрать цвет")
            color_btn.clicked.connect(lambda: self.choose_color(element))
            layout.addWidget(color_btn)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec():
                element.data['text'] = text_edit.toPlainText()
                element.data['font_family'] = font_family.currentText()
                element.data['font_size'] = font_size.value()
                align_map = {0: Qt.AlignLeft, 1: Qt.AlignCenter, 2: Qt.AlignRight}
                element.data['alignment'] = align_map[alignment.currentIndex()]
                self.update()
        elif element.element_type == ElementType.BUTTON:
            dialog = QDialog(self)
            dialog.setWindowTitle("Редактирование кнопки")
            layout = QVBoxLayout(dialog)

            text_edit = QLineEdit(element.data.get('text', 'Кнопка'))
            layout.addWidget(QLabel("Текст:"))
            layout.addWidget(text_edit)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec():
                element.data['text'] = text_edit.text()
                self.update()
        elif element.element_type == ElementType.INPUT:
            dialog = QDialog(self)
            dialog.setWindowTitle("Редактирование поля ввода")
            layout = QVBoxLayout(dialog)

            placeholder_edit = QLineEdit(element.data.get('placeholder', ''))
            layout.addWidget(QLabel("Подсказка:"))
            layout.addWidget(placeholder_edit)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec():
                element.data['placeholder'] = placeholder_edit.text()
                self.update()
        elif element.element_type == ElementType.MENU:
            dialog = QDialog(self)
            dialog.setWindowTitle("Редактирование меню")
            layout = QVBoxLayout(dialog)

            items_text = QTextEdit()
            items = element.data.get('items', ['Пункт 1', 'Пункт 2', 'Пункт 3'])
            items_text.setPlainText('\n'.join(items))
            layout.addWidget(QLabel("Пункты меню (каждый на новой строке):"))
            layout.addWidget(items_text)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec():
                text = items_text.toPlainText()
                element.data['items'] = [line.strip() for line in text.split('\n') if line.strip()]
                self.update()
        elif element.element_type == ElementType.ICON:
            dialog = QDialog(self)
            dialog.setWindowTitle("Редактирование иконки")
            layout = QVBoxLayout(dialog)

            icon_type_combo = QComboBox()
            icon_type_combo.addItems(['default', 'file', 'folder', 'settings'])
            icon_type_combo.setCurrentText(element.data.get('icon_type', 'default'))
            layout.addWidget(QLabel("Тип иконки:"))
            layout.addWidget(icon_type_combo)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec():
                element.data['icon_type'] = icon_type_combo.currentText()
                self.update()

    def choose_color(self, element: CanvasElement):
        """Выбор цвета для элемента"""
        color = QColorDialog.getColor(element.color, self)
        if color.isValid():
            element.color = color
            if element.element_type == ElementType.TEXT:
                element.data['color'] = color.name()
            self.update()

    def show_alignment_dialog(self):
        """Показывает диалог выравнивания"""
        if not self.selected_elements:
            QMessageBox.information(self, "Информация", "Выберите элементы для выравнивания")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Выравнивание элементов")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Выберите тип выравнивания:"))

        align_buttons = QGroupBox("Выравнивание")
        align_layout = QVBoxLayout(align_buttons)

        align_type = None

        def create_align_button(text, align):
            btn = QPushButton(text)
            btn.clicked.connect(lambda: setattr(dialog, 'align_result', align) or dialog.accept())
            align_layout.addWidget(btn)

        create_align_button("По левому краю", AlignmentType.LEFT)
        create_align_button("По правому краю", AlignmentType.RIGHT)
        create_align_button("По верхнему краю", AlignmentType.TOP)
        create_align_button("По нижнему краю", AlignmentType.BOTTOM)
        create_align_button("По центру горизонтально", AlignmentType.CENTER_H)
        create_align_button("По центру вертикально", AlignmentType.CENTER_V)
        create_align_button("По центру", AlignmentType.CENTER)
        create_align_button("Распределить горизонтально", AlignmentType.DISTRIBUTE_H)
        create_align_button("Распределить вертикально", AlignmentType.DISTRIBUTE_V)

        layout.addWidget(align_buttons)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.align_result = None
        if dialog.exec() and hasattr(dialog, 'align_result') and dialog.align_result:
            self.align_elements(self.selected_elements, dialog.align_result)

    def align_elements(self, elements: List[CanvasElement], align_type: AlignmentType):
        """Выравнивает элементы"""
        if len(elements) < 2:
            return

        bounds_list = [e.get_bounds() for e in elements]

        if align_type == AlignmentType.LEFT:
            min_x = min(b.left() for b in bounds_list)
            for element in elements:
                element.position.setX(min_x)
        elif align_type == AlignmentType.RIGHT:
            max_x = max(b.right() for b in bounds_list)
            for element in elements:
                element.position.setX(max_x - element.size.width())
        elif align_type == AlignmentType.TOP:
            min_y = min(b.top() for b in bounds_list)
            for element in elements:
                element.position.setY(min_y)
        elif align_type == AlignmentType.BOTTOM:
            max_y = max(b.bottom() for b in bounds_list)
            for element in elements:
                element.position.setY(max_y - element.size.height())
        elif align_type == AlignmentType.CENTER_H:
            center_x = sum(b.center().x() for b in bounds_list) / len(bounds_list)
            for element in elements:
                element.position.setX(center_x - element.size.width() / 2)
        elif align_type == AlignmentType.CENTER_V:
            center_y = sum(b.center().y() for b in bounds_list) / len(bounds_list)
            for element in elements:
                element.position.setY(center_y - element.size.height() / 2)
        elif align_type == AlignmentType.CENTER:
            center_x = sum(b.center().x() for b in bounds_list) / len(bounds_list)
            center_y = sum(b.center().y() for b in bounds_list) / len(bounds_list)
            for element in elements:
                element.position = QPointF(center_x - element.size.width() / 2,
                                           center_y - element.size.height() / 2)
        elif align_type == AlignmentType.DISTRIBUTE_H:
            xs = sorted([b.left() for b in bounds_list])
            if len(xs) > 2:
                step = (xs[-1] - xs[0]) / (len(xs) - 1)
                sorted_elements = sorted(elements, key=lambda e: e.position.x())
                for i, element in enumerate(sorted_elements):
                    element.position.setX(xs[0] + i * step)
        elif align_type == AlignmentType.DISTRIBUTE_V:
            ys = sorted([b.top() for b in bounds_list])
            if len(ys) > 2:
                step = (ys[-1] - ys[0]) / (len(ys) - 1)
                sorted_elements = sorted(elements, key=lambda e: e.position.y())
                for i, element in enumerate(sorted_elements):
                    element.position.setY(ys[0] + i * step)

        self.update()

    def create_link_dialog(self, element: CanvasElement):
        """Создает диалог для создания ссылки"""
        # Это будет реализовано в MainWindow, так как нужен доступ к списку холстов
        # Временная реализация - элемент уже должен быть выбран
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Фон
        painter.fillRect(self.rect(), QColor(255, 255, 255))

        # Сетка (опционально)
        grid_size = 20
        pen = QPen(QColor(240, 240, 240))
        painter.setPen(pen)
        for x in range(0, self.width(), grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_size):
            painter.drawLine(0, y, self.width(), y)

        # Рисование элементов
        sorted_elements = sorted(self.elements, key=lambda e: e.z_value)
        for element in sorted_elements:
            self.draw_element(painter, element)

        # Рисование текущего элемента
        if self.drawing:
            if self.get_tool() == "line" and len(self.current_points) > 1:
                pen = QPen(QColor(150, 0, 150), 3)
                painter.setPen(pen)
                for i in range(1, len(self.current_points)):
                    painter.drawLine(self.current_points[i - 1], self.current_points[i])
            elif self.current_element:
                self.draw_element(painter, self.current_element)

        # Рисование прямоугольника выделения
        if self.selection_rect:
            pen = QPen(QColor(0, 120, 215), 2, Qt.DashLine)
            painter.setPen(pen)
            brush = QBrush(QColor(0, 120, 215, 30))
            painter.setBrush(brush)
            painter.drawRect(self.selection_rect)

        # Рисование маркеров выделения
        for element in self.selected_elements:
            self.draw_selection_handles(painter, element)

    def draw_element(self, painter: QPainter, element: CanvasElement):
        """Рисует элемент на холсте"""
        pen = QPen(element.color, 3)
        painter.setPen(pen)

        if element.element_type == ElementType.POINT:
            radius = element.data.get('radius', 5)
            painter.drawEllipse(element.position, radius, radius)

        elif element.element_type == ElementType.LINE:
            points = element.data.get('points', [])
            if len(points) > 1:
                for i in range(1, len(points)):
                    painter.drawLine(QPointF(points[i - 1][0], points[i - 1][1]),
                                     QPointF(points[i][0], points[i][1]))

        elif element.element_type == ElementType.STRAIGHT:
            end = element.data.get('end', element.position)
            painter.drawLine(element.position, QPointF(end[0], end[1]) if isinstance(end, tuple) else end)

        elif element.element_type == ElementType.TRIANGLE:
            size = element.size.width()
            center = element.position + QPointF(size / 2, size / 2)
            points = self.regular_polygon(center, size, 3)
            painter.drawPolygon(QPolygonF(points))

        elif element.element_type == ElementType.RECT:
            painter.drawRect(QRectF(element.position, element.size))

        elif element.element_type == ElementType.CIRCLE:
            size = element.size.width()
            painter.drawEllipse(element.position, size, size)

        elif element.element_type == ElementType.PENTAGON:
            center = element.position + QPointF(element.size.width() / 2, element.size.height() / 2)
            points = self.regular_polygon(center, element.size.width(), 5)
            painter.drawPolygon(QPolygonF(points))

        elif element.element_type == ElementType.HEXAGON:
            center = element.position + QPointF(element.size.width() / 2, element.size.height() / 2)
            points = self.regular_polygon(center, element.size.width(), 6)
            painter.drawPolygon(QPolygonF(points))

        elif element.element_type == ElementType.ARROW:
            end = element.data.get('end', element.position)
            end_point = QPointF(end[0], end[1]) if isinstance(end, tuple) else end
            painter.drawLine(element.position, end_point)
            h1, h2 = self.arrow_head(element.position, end_point)
            painter.drawLine(end_point, h1)
            painter.drawLine(end_point, h2)

        elif element.element_type == ElementType.TEXT:
            font = QFont(element.data.get('font_family', 'Arial'), element.data.get('font_size', 12))
            painter.setFont(font)
            color = QColor(element.data.get('color', '#000000'))
            pen.setColor(color)
            painter.setPen(pen)

            text = element.data.get('text', '')
            alignment = element.data.get('alignment', Qt.AlignLeft)

            rect = QRectF(element.position, element.size)
            flags = alignment | Qt.AlignTop | Qt.TextWordWrap

            painter.drawText(rect, flags, text)
            # Рисуем рамку текстового блока
            pen.setColor(QColor(200, 200, 200))
            painter.setPen(pen)
            painter.drawRect(rect)

        elif element.element_type == ElementType.BUTTON:
            rect = QRectF(element.position, element.size)
            # Рисуем кнопку
            brush = QBrush(QColor(240, 240, 240))
            painter.setBrush(brush)
            pen.setColor(QColor(200, 200, 200))
            painter.setPen(pen)
            painter.drawRect(rect)

            # Текст кнопки
            text = element.data.get('text', 'Кнопка')
            font = QFont('Arial', 10)
            painter.setFont(font)
            pen.setColor(QColor(0, 0, 0))
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignCenter, text)

        elif element.element_type == ElementType.INPUT:
            rect = QRectF(element.position, element.size)
            # Рисуем поле ввода
            brush = QBrush(QColor(255, 255, 255))
            painter.setBrush(brush)
            pen.setColor(QColor(200, 200, 200))
            painter.setPen(pen)
            painter.drawRect(rect)

            # Подсказка
            placeholder = element.data.get('placeholder', 'Введите текст')
            font = QFont('Arial', 9)
            painter.setFont(font)
            pen.setColor(QColor(150, 150, 150))
            painter.setPen(pen)
            painter.drawText(rect.adjusted(5, 0, -5, 0), Qt.AlignLeft | Qt.AlignVCenter, placeholder)

        elif element.element_type == ElementType.MENU:
            rect = QRectF(element.position, element.size)
            # Рисуем меню
            brush = QBrush(QColor(245, 245, 245))
            painter.setBrush(brush)
            pen.setColor(QColor(200, 200, 200))
            painter.setPen(pen)
            painter.drawRect(rect)

            # Текст меню
            text = element.data.get('items', ['Меню'])[0] if element.data.get('items') else 'Меню'
            font = QFont('Arial', 10)
            painter.setFont(font)
            pen.setColor(QColor(0, 0, 0))
            painter.setPen(pen)
            painter.drawText(rect.adjusted(5, 0, -20, 0), Qt.AlignLeft | Qt.AlignVCenter, text)

            # Стрелка вниз
            arrow_points = [
                QPointF(rect.right() - 10, rect.center().y() - 3),
                QPointF(rect.right() - 5, rect.center().y() + 2),
                QPointF(rect.right() - 15, rect.center().y() + 2)
            ]
            painter.drawPolygon(QPolygonF(arrow_points))

        elif element.element_type == ElementType.ICON:
            rect = QRectF(element.position, element.size)
            # Рисуем иконку (упрощенная версия)
            icon_type = element.data.get('icon_type', 'default')
            brush = QBrush(QColor(100, 150, 200))
            painter.setBrush(brush)
            pen.setColor(QColor(80, 120, 160))
            painter.setPen(pen)

            icon_symbols = {
                'default': '⚙',
                'file': '📄',
                'folder': '📁',
                'settings': '⚙'
            }
            symbol = icon_symbols.get(icon_type, '⚙')

            painter.drawRect(rect)
            font = QFont('Arial', 16, QFont.Bold)
            painter.setFont(font)
            pen.setColor(QColor(255, 255, 255))
            painter.setPen(pen)
            painter.drawText(rect, Qt.AlignCenter, symbol)

        elif element.element_type == ElementType.IMAGE:
            image_path = element.data.get('image_path', '')
            if image_path and os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                scaled_pixmap = pixmap.scaled(element.size.toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(element.position.toPoint(), scaled_pixmap)
            else:
                # Рисуем заглушку
                rect = QRectF(element.position, element.size)
                pen.setColor(QColor(200, 200, 200))
                painter.setPen(pen)
                painter.drawRect(rect)
                painter.drawText(rect, Qt.AlignCenter, "Изображение")

        elif element.element_type == ElementType.LINK:
            # Рисуем ссылку как специальную иконку
            rect = QRectF(element.position, element.size)
            pen.setColor(QColor(0, 120, 215))
            painter.setPen(pen)
            brush = QBrush(QColor(0, 120, 215, 50))
            painter.setBrush(brush)
            painter.drawRect(rect)
            painter.drawText(rect, Qt.AlignCenter, "→")

    def draw_selection_handles(self, painter: QPainter, element: CanvasElement):
        """Рисует маркеры выделения"""
        bounds = element.get_bounds()
        handles = [
            QPointF(bounds.left(), bounds.top()),
            QPointF(bounds.center().x(), bounds.top()),
            QPointF(bounds.right(), bounds.top()),
            QPointF(bounds.right(), bounds.center().y()),
            QPointF(bounds.right(), bounds.bottom()),
            QPointF(bounds.center().x(), bounds.bottom()),
            QPointF(bounds.left(), bounds.bottom()),
            QPointF(bounds.left(), bounds.center().y())
        ]

        pen = QPen(QColor(0, 120, 215), 2)
        painter.setPen(pen)
        brush = QBrush(QColor(255, 255, 255))
        painter.setBrush(brush)

        for handle in handles:
            painter.drawEllipse(handle, 4, 4)

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        if event.key() == Qt.Key_Delete and self.selected_elements:
            for element in self.selected_elements.copy():
                self.remove_element(element)
        elif event.key() == Qt.Key_Escape:
            self.clear_selection()
        super().keyPressEvent(event)

    def load_image(self, image_path: str) -> Optional[CanvasElement]:
        """Загружает изображение на холст"""
        if not os.path.exists(image_path):
            return None

        pixmap = QPixmap(image_path)
        element = CanvasElement(ElementType.IMAGE, QPointF(50, 50))
        element.size = QSizeF(pixmap.width(), pixmap.height())
        element.data = {'image_path': image_path}
        self.add_element(element)
        return element


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Графический редактор интерфейсов")
        self.setGeometry(100, 100, 1200, 800)

        self.current_tool = "select"
        self.canvases: Dict[str, Canvas] = {}
        self.current_canvas_id = "canvas_1"
        self.canvas_counter = 1

        self.setup_ui()
        self.setup_menu()

        # Создаем первый холст (после инициализации tab_widget и списка холстов)
        self.create_canvas("Холст 1")

        # Обработка кликов по ссылкам на холсте
        for canvas in self.canvases.values():
            # Подключаем обработчик через переопределение mousePressEvent в Canvas
            pass

    def setup_ui(self):
        """Настройка интерфейса"""
        # Центральный виджет с вкладками
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_canvas_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tab_widget)

        # Панель инструментов
        toolbar = QToolBar("Инструменты")
        toolbar.setMovable(False)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)

        # Группы инструментов
        self.add_tool_button(toolbar, "Выделение", "select", True)
        toolbar.addSeparator()

        self.add_tool_button(toolbar, "Точка", "point")
        self.add_tool_button(toolbar, "Кривая", "line")
        self.add_tool_button(toolbar, "Прямая", "straight")
        self.add_tool_button(toolbar, "Стрелка", "arrow")
        toolbar.addSeparator()

        self.add_tool_button(toolbar, "Прямоугольник", "rect")
        self.add_tool_button(toolbar, "Круг", "circle")
        self.add_tool_button(toolbar, "Треугольник", "triangle")
        self.add_tool_button(toolbar, "Пятиугольник", "pentagon")
        self.add_tool_button(toolbar, "Шестиугольник", "hexagon")
        toolbar.addSeparator()

        self.add_tool_button(toolbar, "Текст", "text")
        toolbar.addSeparator()

        self.add_tool_button(toolbar, "Кнопка", "button")
        self.add_tool_button(toolbar, "Поле ввода", "input")
        self.add_tool_button(toolbar, "Меню", "menu")
        self.add_tool_button(toolbar, "Иконка", "icon")
        toolbar.addSeparator()

        self.add_tool_button(toolbar, "Изображение", "image")
        self.add_tool_button(toolbar, "Ссылка", "link")

        # Панель выравнивания
        align_toolbar = QToolBar("Выравнивание")
        self.addToolBar(Qt.RightToolBarArea, align_toolbar)

        align_btn = QPushButton("Выровнять")
        align_btn.clicked.connect(self.show_alignment_dialog)
        align_toolbar.addWidget(align_btn)

        # Список холстов
        self.canvas_list = QListWidget()
        self.canvas_list.setMaximumWidth(200)
        self.canvas_list.itemClicked.connect(self.switch_canvas)

        dock = self.create_dock_widget("Холсты", self.canvas_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def setup_menu(self):
        """Настройка меню"""
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("Файл")
        file_menu.addAction("Новый холст", self.create_new_canvas, QKeySequence.New)
        file_menu.addAction("Открыть проект", self.open_project, QKeySequence.Open)
        file_menu.addAction("Сохранить проект", self.save_project, QKeySequence.Save)
        file_menu.addSeparator()
        file_menu.addAction("Выход", self.close, QKeySequence.Quit)

        # Правка
        edit_menu = menubar.addMenu("Правка")
        edit_menu.addAction("Удалить", lambda: self.get_current_canvas().keyPressEvent(
            type('obj', (object,), {'key': lambda _self: Qt.Key_Delete})()), QKeySequence.Delete)

        # Вид
        view_menu = menubar.addMenu("Вид")
        view_menu.addAction("Список холстов", self.toggle_canvas_list)

    def create_dock_widget(self, title: str, widget: QWidget):
        """Создает dock виджет"""
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        return dock

    def add_tool_button(self, toolbar: QToolBar, name: str, tool_id: str, checked: bool = False):
        """Добавляет кнопку инструмента"""
        action = QAction(name, self)
        action.setCheckable(True)
        action.setChecked(checked and tool_id == self.current_tool)
        action.triggered.connect(lambda checked, t=tool_id: self.select_tool(t))
        toolbar.addAction(action)

        # Подсказка
        tooltips = {
            "select": "Выделение элементов",
            "point": "Точка",
            "line": "Кривая линия",
            "straight": "Прямая линия",
            "arrow": "Стрелка",
            "rect": "Прямоугольник",
            "circle": "Круг",
            "triangle": "Треугольник",
            "pentagon": "Пятиугольник",
            "hexagon": "Шестиугольник",
            "text": "Текст",
            "button": "Кнопка",
            "input": "Поле ввода",
            "menu": "Меню",
            "icon": "Иконка",
            "image": "Изображение",
            "link": "Ссылка на другой холст"
        }
        action.setToolTip(tooltips.get(tool_id, name))

    def select_tool(self, tool_id: str):
        """Выбирает инструмент"""
        self.current_tool = tool_id

        # Обновляем состояние кнопок
        for action in self.findChildren(QAction):
            if action.isCheckable():
                action.setChecked(action.data() == tool_id if hasattr(action, 'data') else False)

        # Если выбран инструмент изображения, открываем диалог
        if tool_id == "image":
            self.load_image_dialog()
        elif tool_id == "link":
            # Для ссылки нужно сначала выбрать элемент
            canvas = self.get_current_canvas()
            if canvas and canvas.selected_elements:
                self.create_link_dialog()
            else:
                QMessageBox.information(self, "Информация",
                                        "Выберите элемент, затем используйте инструмент 'Ссылка' или контекстное меню")
                self.select_tool("select")

    def get_current_tool(self):
        """Возвращает текущий инструмент"""
        return self.current_tool

    def get_current_canvas(self) -> Optional[Canvas]:
        """Возвращает текущий холст"""
        return self.canvases.get(self.current_canvas_id)

    def create_canvas(self, name: str) -> str:
        """Создает новый холст"""
        canvas_id = f"canvas_{self.canvas_counter}"
        self.canvas_counter += 1

        canvas = Canvas(canvas_id, self.get_current_tool)
        self.canvases[canvas_id] = canvas

        # Добавляем вкладку
        index = self.tab_widget.addTab(canvas, name)
        self.tab_widget.setCurrentIndex(index)

        # Добавляем в список
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, canvas_id)
        self.canvas_list.addItem(item)

        self.current_canvas_id = canvas_id
        return canvas_id

    def create_new_canvas(self):
        """Создает новый холст через меню"""
        name = f"Холст {self.canvas_counter}"
        self.create_canvas(name)

    def close_canvas_tab(self, index: int):
        """Закрывает вкладку холста"""
        widget = self.tab_widget.widget(index)
        if widget:
            canvas_id = widget.canvas_id
            # Удаляем из словаря
            if canvas_id in self.canvases:
                del self.canvases[canvas_id]
            # Удаляем из списка
            for i in range(self.canvas_list.count()):
                item = self.canvas_list.item(i)
                if item.data(Qt.UserRole) == canvas_id:
                    self.canvas_list.takeItem(i)
                    break
            # Удаляем вкладку
            self.tab_widget.removeTab(index)

            # Переключаемся на другой холст, если есть
            if self.tab_widget.count() > 0:
                self.tab_widget.setCurrentIndex(0)
                widget = self.tab_widget.currentWidget()
                if widget:
                    self.current_canvas_id = widget.canvas_id

    def on_tab_changed(self, index: int):
        """Обработка смены вкладки"""
        widget = self.tab_widget.widget(index)
        if widget:
            self.current_canvas_id = widget.canvas_id

    def switch_canvas(self, item: QListWidgetItem):
        """Переключается на холст из списка"""
        canvas_id = item.data(Qt.UserRole)
        if canvas_id in self.canvases:
            # Находим вкладку с этим холстом
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if widget and widget.canvas_id == canvas_id:
                    self.tab_widget.setCurrentIndex(i)
                    self.current_canvas_id = canvas_id
                    break

    def load_image_dialog(self):
        """Диалог загрузки изображения"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            canvas = self.get_current_canvas()
            if canvas:
                canvas.load_image(file_path)
                # Возвращаемся к инструменту выделения
                self.select_tool("select")

    def create_link_dialog(self, element: Optional[CanvasElement] = None):
        """Создает диалог для создания ссылки на другой холст"""
        canvas = self.get_current_canvas()
        if not canvas:
            return

        # Если элемент не передан, используем выделенные
        if not element:
            if not canvas.selected_elements:
                QMessageBox.information(self, "Информация", "Выберите элемент для создания ссылки")
                self.select_tool("select")
                return
            elements_to_link = canvas.selected_elements
        else:
            elements_to_link = [element]

        dialog = QDialog(self)
        dialog.setWindowTitle("Создание ссылки")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Выберите целевой холст:"))

        canvas_list = QListWidget()
        for canvas_id, canvas_obj in self.canvases.items():
            if canvas_id != self.current_canvas_id:
                item = QListWidgetItem(f"Холст {canvas_id.split('_')[1]}")
                item.setData(Qt.UserRole, canvas_id)
                canvas_list.addItem(item)

        layout.addWidget(canvas_list)

        # Анимация
        animate_check = QCheckBox("Анимированный переход")
        animate_check.setChecked(True)
        layout.addWidget(animate_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() and canvas_list.currentItem():
            target_canvas_id = canvas_list.currentItem().data(Qt.UserRole)
            animate = animate_check.isChecked()

            # Создаем ссылку для каждого элемента
            for element in elements_to_link:
                element.element_type = ElementType.LINK
                element.data['target_canvas'] = target_canvas_id
                element.data['animate'] = animate
                element.size = QSizeF(30, 30)

            canvas.update()
            self.select_tool("select")
        else:
            self.select_tool("select")

    def create_link_for_element(self, element: CanvasElement):
        """Создает ссылку для конкретного элемента (вызывается из контекстного меню)"""
        self.create_link_dialog(element)

    def show_alignment_dialog(self):
        """Показывает диалог выравнивания"""
        canvas = self.get_current_canvas()
        if canvas:
            canvas.show_alignment_dialog()

    def toggle_canvas_list(self):
        """Переключает видимость списка холстов"""
        # Реализация переключения видимости dock виджета
        pass

    def navigate_to_canvas(self, target_canvas_id: str, animate: bool = True):
        """Переходит на указанный холст с анимацией"""
        if target_canvas_id not in self.canvases:
            return

        # Находим вкладку с целевым холстом
        target_index = -1
        current_index = self.tab_widget.currentIndex()

        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget and widget.canvas_id == target_canvas_id:
                target_index = i
                break

        if target_index == -1:
            return

        if animate and abs(target_index - current_index) > 0:
            # Анимация перехода
            self.animate_tab_transition(current_index, target_index)
        else:
            self.tab_widget.setCurrentIndex(target_index)
            self.current_canvas_id = target_canvas_id

    def animate_tab_transition(self, from_index: int, to_index: int):
        """Анимирует переход между вкладками"""
        # Простая анимация - плавное переключение
        steps = 10
        delay = 20  # мс

        def step_transition(step):
            if step <= steps:
                # Вычисляем промежуточный индекс
                progress = step / steps
                current_idx = int(from_index + (to_index - from_index) * progress)
                if 0 <= current_idx < self.tab_widget.count():
                    self.tab_widget.setCurrentIndex(current_idx)
                QTimer.singleShot(delay, lambda: step_transition(step + 1))
            else:
                # Финальное переключение
                self.tab_widget.setCurrentIndex(to_index)
                widget = self.tab_widget.currentWidget()
                if widget:
                    self.current_canvas_id = widget.canvas_id

        step_transition(1)

    def save_project(self):
        """Сохраняет проект"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        project_data = {
            'canvases': {},
            'current_canvas': self.current_canvas_id
        }

        for canvas_id, canvas in self.canvases.items():
            project_data['canvases'][canvas_id] = {
                'elements': [e.to_dict() for e in canvas.elements],
                'name': self.tab_widget.tabText(self.tab_widget.indexOf(canvas))
            }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Успех", "Проект сохранен")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить проект: {str(e)}")

    def open_project(self):
        """Открывает проект"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть проект", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # Очищаем текущие холсты
            while self.tab_widget.count() > 0:
                self.tab_widget.removeTab(0)
            self.canvases.clear()
            self.canvas_list.clear()

            # Загружаем холсты
            for canvas_id, canvas_data in project_data.get('canvases', {}).items():
                name = canvas_data.get('name', canvas_id)
                canvas = Canvas(canvas_id, self.get_current_tool)

                # Загружаем элементы
                for elem_data in canvas_data.get('elements', []):
                    element = CanvasElement.from_dict(elem_data)
                    canvas.add_element(element)

                self.canvases[canvas_id] = canvas
                index = self.tab_widget.addTab(canvas, name)
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, canvas_id)
                self.canvas_list.addItem(item)

            # Переключаемся на сохраненный холст
            current_id = project_data.get('current_canvas')
            if current_id and current_id in self.canvases:
                for i in range(self.tab_widget.count()):
                    widget = self.tab_widget.widget(i)
                    if widget and widget.canvas_id == current_id:
                        self.tab_widget.setCurrentIndex(i)
                        self.current_canvas_id = current_id
                        break

            QMessageBox.information(self, "Успех", "Проект загружен")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить проект: {str(e)}")

    def mouseDoubleClickEvent(self, event):
        """Обработка двойного клика для редактирования элементов"""
        canvas = self.get_current_canvas()
        if canvas:
            pos = event.position()
            element = canvas.get_element_at(pos)
            if element:
                canvas.edit_element(element)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

