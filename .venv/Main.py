import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar, QVBoxLayout,
    QLabel, QFileDialog, QMenu, QMessageBox, QTabWidget, QDialog,
    QDialogButtonBox, QCheckBox, QListWidget, QListWidgetItem, QDockWidget,
    QColorDialog, QTextEdit, QSpinBox, QComboBox,
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QAction, QBrush, QKeySequence, QPixmap, QFont,
)
from PySide6.QtCore import (
    Qt, QPointF, QRectF, QSizeF, QTimer, Signal, QObject, QPoint
)
import sys
import json
from enum import Enum
from typing import List, Dict, Optional


class ElementType(Enum):
    """Типы элементов на холсте"""
    RECT = "rect"
    IMAGE = "image"
    TEXT = "text"


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
        type_str = data.get('type', 'rect')
        try:
            et = ElementType(type_str)
        except ValueError:
            et = ElementType.RECT
        element = CanvasElement(
            et,
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
        self.background_color = QColor(255, 255, 255)

    def set_background_color(self, color: QColor):
        """Устанавливает цвет фона холста."""
        self.background_color = QColor(color)
        self.update()

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
        # Проверяем сверху вниз по слоям
        for element in sorted(self.elements, key=lambda e: e.z_value, reverse=True):
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

    def get_next_z_value(self) -> int:
        """Возвращает новый слой поверх всех элементов."""
        if not self.elements:
            return 0
        return max(e.z_value for e in self.elements) + 1

    def update_rect_from_points(self, element: CanvasElement, p1: QPointF, p2: QPointF):
        """Обновляет геометрию прямоугольника по двум точкам."""
        x = min(p1.x(), p2.x())
        y = min(p1.y(), p2.y())
        w = abs(p2.x() - p1.x())
        h = abs(p2.y() - p1.y())
        element.position = QPointF(x, y)
        element.size = QSizeF(max(1.0, w), max(1.0, h))

    def resize_selected_element(self, cursor_pos: QPointF):
        """Изменяет размер выделенного прямоугольника за маркер."""
        element = self.selected_elements[0]
        bounds = element.get_bounds()
        left, top, right, bottom = bounds.left(), bounds.top(), bounds.right(), bounds.bottom()
        min_size = 10.0

        if self.resize_handle in [0, 6, 7]:
            left = min(cursor_pos.x(), right - min_size)
        if self.resize_handle in [2, 3, 4]:
            right = max(cursor_pos.x(), left + min_size)
        if self.resize_handle in [0, 1, 2]:
            top = min(cursor_pos.y(), bottom - min_size)
        if self.resize_handle in [4, 5, 6]:
            bottom = max(cursor_pos.y(), top + min_size)

        element.position = QPointF(left, top)
        element.size = QSizeF(right - left, bottom - top)
        element.changed.emit()

    def mousePressEvent(self, event):
        pos = event.position()
        tool = self.get_tool()

        if event.button() == Qt.LeftButton:
            if tool == "select":
                element = self.get_element_at(pos)
                if element and len(self.selected_elements) == 1 and element in self.selected_elements:
                    self.resize_handle = self.get_resize_handle(pos, element.get_bounds())
                if element:
                    self.select_element(element, event.modifiers() & Qt.ControlModifier)
                    if self.resize_handle is None:
                        self.dragging = True
                        self.drag_start = pos
                else:
                    self.clear_selection()
                    self.selection_start = pos
                    self.selection_rect = QRectF(pos, QSizeF(0, 0))
            elif tool == "rect":
                self.start_point = pos
                self.drawing = True
                self.current_element = CanvasElement(ElementType.RECT, pos)
                self.current_element.z_value = self.get_next_z_value()
                self.current_element.data = {}
                self.update_rect_from_points(self.current_element, self.start_point, pos)
            elif tool == "text":
                self.start_point = pos
                self.drawing = True
                self.current_element = CanvasElement(ElementType.TEXT, pos)
                self.current_element.z_value = self.get_next_z_value()
                self.current_element.color = QColor(30, 30, 30)
                self.current_element.data = {
                    "text": "Текст",
                    "font_family": "Segoe UI",
                    "font_size": 14,
                }
                self.update_rect_from_points(self.current_element, self.start_point, pos)

        if event.button() == Qt.RightButton:
            element = self.get_element_at(pos)
            if element:
                self.show_context_menu(element, event.globalPos())

    def mouseDoubleClickEvent(self, event):
        """Текст — редактирование; ссылка — переход по двойному щелчку."""
        if event.button() == Qt.LeftButton:
            pos = event.position()
            element = self.get_element_at(pos)
            if element and element.element_type == ElementType.TEXT:
                self.edit_text_element(element)
                return
            if element and element.data.get("target_canvas"):
                target_canvas_id = element.data.get("target_canvas")
                animate = element.data.get("animate", True)
                parent = self.parent()
                while parent and not isinstance(parent, QMainWindow):
                    parent = parent.parent()
                if parent and hasattr(parent, "navigate_to_canvas"):
                    parent.navigate_to_canvas(target_canvas_id, animate)
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        tool = self.get_tool()

        if tool == "select" and self.resize_handle is not None and len(self.selected_elements) == 1:
            self.resize_selected_element(pos)
            self.update()
        elif tool == "select" and self.dragging and self.drag_start and self.selected_elements:
            delta = pos - self.drag_start
            for element in self.selected_elements:
                element.move(delta)
            self.drag_start = pos
            self.update()
        elif tool == "select" and self.selection_start:
            self.selection_rect = QRectF(self.selection_start, pos).normalized()
            self.update()
        elif self.drawing and self.current_element and self.start_point:
            self.update_rect_from_points(self.current_element, self.start_point, pos)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            tool = self.get_tool()

            if tool == "select" and self.selection_start:
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
                self.resize_handle = None
            elif self.drawing:
                if self.current_element and self.current_element.size.width() >= 5 and self.current_element.size.height() >= 5:
                    self.add_element(self.current_element)
                self.current_element = None
                self.drawing = False
                self.update()

    def edit_text_element(self, element: CanvasElement):
        """Диалог редактирования текстового блока."""
        if element.element_type != ElementType.TEXT:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Редактирование текста")
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(element.data.get("text", ""))
        layout.addWidget(QLabel("Текст:"))
        layout.addWidget(text_edit)
        font_family = QComboBox()
        font_family.addItems(
            ["Segoe UI", "Arial", "Times New Roman", "Courier New", "Consolas", "Verdana"]
        )
        fam = element.data.get("font_family", "Segoe UI")
        i = font_family.findText(fam)
        if i >= 0:
            font_family.setCurrentIndex(i)
        else:
            font_family.insertItem(0, fam)
            font_family.setCurrentIndex(0)
        layout.addWidget(QLabel("Шрифт:"))
        layout.addWidget(font_family)
        font_size = QSpinBox()
        font_size.setRange(6, 96)
        font_size.setValue(int(element.data.get("font_size", 14)))
        layout.addWidget(QLabel("Размер:"))
        layout.addWidget(font_size)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            element.data["text"] = text_edit.toPlainText()
            element.data["font_family"] = font_family.currentText()
            element.data["font_size"] = font_size.value()
            element.changed.emit()
            self.update()

    def show_context_menu(self, element: CanvasElement, global_pos: QPoint):
        """Показывает контекстное меню для элемента"""
        menu = QMenu(self)
        delete_action = menu.addAction("Удалить")
        color_action = None
        replace_image_action = None
        edit_text_action = None
        text_color_action = None
        if element.element_type == ElementType.RECT and not element.data.get("target_canvas"):
            menu.addSeparator()
            color_action = menu.addAction("Цвет заливки...")
        elif element.element_type == ElementType.IMAGE:
            menu.addSeparator()
            replace_image_action = menu.addAction("Другое изображение...")
        elif element.element_type == ElementType.TEXT:
            menu.addSeparator()
            edit_text_action = menu.addAction("Редактировать текст...")
            text_color_action = menu.addAction("Цвет текста...")
        menu.addSeparator()
        link_action = menu.addAction("Создать ссылку...")
        clear_link_action = menu.addAction("Убрать ссылку")
        menu.addSeparator()
        up_action = menu.addAction("Слой выше")
        down_action = menu.addAction("Слой ниже")
        top_action = menu.addAction("На передний план")
        bottom_action = menu.addAction("На задний план")

        action = menu.exec(global_pos)
        if action == delete_action:
            self.remove_element(element)
        elif edit_text_action is not None and action == edit_text_action:
            self.edit_text_element(element)
        elif text_color_action is not None and action == text_color_action:
            c = QColorDialog.getColor(element.color, self, "Цвет текста")
            if c.isValid():
                element.color = c
                element.changed.emit()
                self.update()
        elif color_action is not None and action == color_action:
            c = QColorDialog.getColor(element.color, self, "Цвет заливки")
            if c.isValid():
                element.color = c
                element.changed.emit()
                self.update()
        elif replace_image_action is not None and action == replace_image_action:
            path, _ = QFileDialog.getOpenFileName(
                self, "Выберите изображение", "",
                "Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
            )
            if path:
                pm = QPixmap(path)
                if not pm.isNull():
                    element.data["image_path"] = path
                    element.changed.emit()
                    self.update()
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось загрузить файл изображения.")
        elif action == link_action:
            self.select_element(element)
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            if parent and hasattr(parent, 'create_link_for_element'):
                parent.create_link_for_element(element)
        elif action == clear_link_action:
            element.data.pop("target_canvas", None)
            element.data.pop("animate", None)
            self.update()
        elif action in (up_action, down_action, top_action, bottom_action):
            self.select_element(element)
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            if not parent:
                return
            if action == up_action and hasattr(parent, "move_layer_up"):
                parent.move_layer_up()
            elif action == down_action and hasattr(parent, "move_layer_down"):
                parent.move_layer_down()
            elif action == top_action and hasattr(parent, "move_layer_to_top"):
                parent.move_layer_to_top()
            elif action == bottom_action and hasattr(parent, "move_layer_to_bottom"):
                parent.move_layer_to_bottom()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Фон
        painter.fillRect(self.rect(), self.background_color)

        # Рисование элементов
        sorted_elements = sorted(self.elements, key=lambda e: e.z_value)
        for element in sorted_elements:
            self.draw_element(painter, element)

        # Рисование текущего элемента
        if self.drawing and self.current_element:
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
        rect = QRectF(element.position, element.size)

        if element.element_type == ElementType.IMAGE:
            path = element.data.get("image_path", "")
            if path and os.path.isfile(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    scaled = pix.scaled(
                        rect.size().toSize(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    painter.fillRect(rect, QColor(245, 245, 245))
                    x = rect.x() + (rect.width() - scaled.width()) / 2
                    y = rect.y() + (rect.height() - scaled.height()) / 2
                    painter.drawPixmap(QPointF(x, y), scaled)
                    painter.setPen(QPen(QColor(80, 80, 80), 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(rect)
                    if element.data.get("target_canvas"):
                        painter.fillRect(rect, QColor(0, 120, 215, 90))
                        painter.setPen(QPen(Qt.white))
                        painter.drawText(rect, Qt.AlignCenter, "->")
                    return
            painter.fillRect(rect, QColor(230, 230, 230))
            painter.setPen(QPen(QColor(160, 160, 160), 1))
            painter.drawText(rect, Qt.AlignCenter, "Нет изображения")
            painter.drawRect(rect)
            return

        if element.element_type == ElementType.TEXT:
            font = QFont(
                element.data.get("font_family", "Segoe UI"),
                int(element.data.get("font_size", 14)),
            )
            painter.setFont(font)
            painter.setPen(QPen(element.color, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawText(
                rect,
                int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap),
                element.data.get("text", ""),
            )
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            painter.drawRect(rect)
            if element.data.get("target_canvas"):
                painter.fillRect(rect, QColor(0, 120, 215, 85))
                painter.setPen(QPen(Qt.white))
                painter.drawText(rect, Qt.AlignCenter, "->")
            return

        # Прямоугольник — заливка
        if element.data.get("target_canvas"):
            fill = QColor(0, 120, 215, 200)
            pen = QPen(QColor(0, 70, 140), 2)
        else:
            fill = QColor(element.color)
            fill.setAlpha(255)
            pen = QPen(element.color.darker(130), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRect(rect)
        if element.data.get("target_canvas"):
            painter.setPen(QPen(Qt.white))
            painter.drawText(rect, Qt.AlignCenter, "->")

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
        self.add_tool_button(toolbar, "Прямоугольник", "rect")
        toolbar.addSeparator()
        self.add_tool_button(toolbar, "Текст", "text")
        toolbar.addSeparator()
        self.add_tool_button(toolbar, "Изображение", "image")
        toolbar.addSeparator()
        self.add_tool_button(toolbar, "Ссылка", "link")

        layers_toolbar = QToolBar("Слои")
        self.addToolBar(Qt.TopToolBarArea, layers_toolbar)
        up_action = QAction("Выше", self)
        up_action.triggered.connect(self.move_layer_up)
        layers_toolbar.addAction(up_action)
        down_action = QAction("Ниже", self)
        down_action.triggered.connect(self.move_layer_down)
        layers_toolbar.addAction(down_action)
        top_action = QAction("Наверх", self)
        top_action.triggered.connect(self.move_layer_to_top)
        layers_toolbar.addAction(top_action)
        bottom_action = QAction("Вниз", self)
        bottom_action.triggered.connect(self.move_layer_to_bottom)
        layers_toolbar.addAction(bottom_action)

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
        view_menu.addAction("Цвет фона холста...", lambda: self.change_canvas_background_color())

    def create_dock_widget(self, title: str, widget: QWidget):
        """Создает dock виджет"""
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        return dock

    def add_tool_button(self, toolbar: QToolBar, name: str, tool_id: str, checked: bool = False):
        """Добавляет кнопку инструмента"""
        action = QAction(name, self)
        action.setCheckable(True)
        action.setData(tool_id)
        action.setChecked(checked and tool_id == self.current_tool)
        action.triggered.connect(lambda checked, t=tool_id: self.select_tool(t))
        toolbar.addAction(action)

        # Подсказка
        tooltips = {
            "select": "Выделение элементов",
            "rect": "Прямоугольник",
            "text": "Текст — протяните рамку, двойной клик для правки",
            "image": "Вставить изображение с компьютера",
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

        if tool_id == "link":
            # Для ссылки нужно сначала выбрать элемент
            canvas = self.get_current_canvas()
            if canvas and canvas.selected_elements:
                self.create_link_dialog()
            else:
                QMessageBox.information(self, "Информация",
                                        "Выберите элемент, затем используйте инструмент 'Ссылка' или контекстное меню")
                self.select_tool("select")
        elif tool_id == "image":
            self.load_image_dialog()

    def load_image_dialog(self):
        """Добавляет на холст изображение с диска."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        canvas = self.get_current_canvas()
        if not path or not canvas:
            self.select_tool("select")
            return
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить файл изображения.")
            self.select_tool("select")
            return
        max_w, max_h = 480.0, 360.0
        w, h = float(pix.width()), float(pix.height())
        scale = min(1.0, max_w / w, max_h / h)
        el = CanvasElement(ElementType.IMAGE, QPointF(60, 60))
        el.size = QSizeF(w * scale, h * scale)
        el.data = {"image_path": path}
        el.z_value = canvas.get_next_z_value()
        canvas.add_element(el)
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
        if self.tab_widget.count() <= 1:
            QMessageBox.information(self, "Информация", "Должен остаться минимум один холст")
            return
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

    def _selected_elements(self) -> List[CanvasElement]:
        canvas = self.get_current_canvas()
        if not canvas:
            return []
        return canvas.selected_elements

    def _normalize_z_values(self, canvas: Canvas):
        ordered = sorted(canvas.elements, key=lambda e: e.z_value)
        for idx, element in enumerate(ordered):
            element.z_value = idx

    def move_layer_up(self):
        canvas = self.get_current_canvas()
        selected = self._selected_elements()
        if not canvas or not selected:
            return
        self._normalize_z_values(canvas)
        ordered = sorted(canvas.elements, key=lambda e: e.z_value)
        for element in sorted(selected, key=lambda e: e.z_value, reverse=True):
            idx = ordered.index(element)
            if idx < len(ordered) - 1:
                above = ordered[idx + 1]
                element.z_value, above.z_value = above.z_value, element.z_value
                ordered[idx], ordered[idx + 1] = ordered[idx + 1], ordered[idx]
        canvas.update()

    def move_layer_down(self):
        canvas = self.get_current_canvas()
        selected = self._selected_elements()
        if not canvas or not selected:
            return
        self._normalize_z_values(canvas)
        ordered = sorted(canvas.elements, key=lambda e: e.z_value)
        for element in sorted(selected, key=lambda e: e.z_value):
            idx = ordered.index(element)
            if idx > 0:
                below = ordered[idx - 1]
                element.z_value, below.z_value = below.z_value, element.z_value
                ordered[idx], ordered[idx - 1] = ordered[idx - 1], ordered[idx]
        canvas.update()

    def move_layer_to_top(self):
        canvas = self.get_current_canvas()
        selected = self._selected_elements()
        if not canvas or not selected:
            return
        top_z = max((e.z_value for e in canvas.elements), default=-1)
        for element in sorted(selected, key=lambda e: e.z_value):
            top_z += 1
            element.z_value = top_z
        self._normalize_z_values(canvas)
        canvas.update()

    def move_layer_to_bottom(self):
        canvas = self.get_current_canvas()
        selected = self._selected_elements()
        if not canvas or not selected:
            return
        for element in selected:
            element.z_value -= 10000
        self._normalize_z_values(canvas)
        canvas.update()

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
                element.data['target_canvas'] = target_canvas_id
                element.data['animate'] = animate

            canvas.update()
            self.select_tool("select")
        else:
            self.select_tool("select")

    def create_link_for_element(self, element: CanvasElement):
        """Создает ссылку для конкретного элемента (вызывается из контекстного меню)"""
        self.create_link_dialog(element)

    def change_canvas_background_color(self, canvas: Optional[Canvas] = None):
        """Диалог выбора цвета фона текущего (или переданного) холста."""
        canvas = canvas or self.get_current_canvas()
        if not canvas:
            return
        c = QColorDialog.getColor(canvas.background_color, self, "Цвет фона холста")
        if c.isValid():
            canvas.set_background_color(c)

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
                'name': self.tab_widget.tabText(self.tab_widget.indexOf(canvas)),
                'background_color': canvas.background_color.name(QColor.NameFormat.HexArgb),
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

                bg = canvas_data.get('background_color')
                if bg:
                    col = QColor(bg)
                    if col.isValid():
                        canvas.background_color = col

                self.canvases[canvas_id] = canvas
                index = self.tab_widget.addTab(canvas, name)
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, canvas_id)
                self.canvas_list.addItem(item)

                try:
                    suffix = int(canvas_id.split("_")[1])
                    self.canvas_counter = max(self.canvas_counter, suffix + 1)
                except Exception:
                    pass

            # Переключаемся на сохраненный холст
            current_id = project_data.get('current_canvas')
            if current_id and current_id in self.canvases:
                for i in range(self.tab_widget.count()):
                    widget = self.tab_widget.widget(i)
                    if widget and widget.canvas_id == current_id:
                        self.tab_widget.setCurrentIndex(i)
                        self.current_canvas_id = current_id
                        break
            elif self.tab_widget.count() > 0:
                self.tab_widget.setCurrentIndex(0)
                widget = self.tab_widget.currentWidget()
                if widget:
                    self.current_canvas_id = widget.canvas_id
            else:
                self.create_canvas("Холст 1")

            QMessageBox.information(self, "Успех", "Проект загружен")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить проект: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

