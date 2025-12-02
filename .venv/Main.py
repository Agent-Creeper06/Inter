from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar
)
from PySide6.QtGui import QPainter, QPen, QColor, QAction, QCursor, QPolygonF
from PySide6.QtCore import Qt, QPointF
from math import sin, cos, pi, atan2
import sys


class Canvas(QWidget):
    def __init__(self, get_tool_callback):
        super().__init__()
        self.get_tool = get_tool_callback

        self.points = []          #Точки кривой линии
        self.lines = []           #Список завершённых кривых линий

        self.straight_start = None #Начало прямой линии
        self.straight_end = None #Конец прямой линии
        self.straight_lines = []

        self.triangle_start = None  #Начало треугольника
        self.triangle_end = None  #Конец треугоньника
        self.triangles = []

        self.rect_start = None #Начало прямоугольника
        self.rect_end = None #Конец прямоугольника
        self.rectangles = []

        self.circle_start = None #Начало круга
        self.circle_end = None #Конец круга
        self.circles = []

        self.pentagon_start = None #Начало пентагона
        self.pentagon_end = None #Конец пентагона
        self.pentagons = []

        self.hexagon_start = None #Начало хекса
        self.hexagon_end = None #Конец хекса
        self.hexagons = []

        self.arrow_start = None #Начало стрелки
        self.arrow_end = None #Конец стрелки
        self.arrows = []

        self.drawing = False
        self.setMinimumSize(800, 600)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        tool = self.get_tool()
        pos = event.position()

        #Кривая линия
        if tool == "line":
            self.drawing = True
            self.points = [pos]
            self.update()
            return

        #Прямая линия
        elif tool == "straight":
            self.straight_start = pos
            self.straight_end = pos
            self.drawing = True
            self.update()
            return

        #Треугольник
        elif tool == "triangle":
            self.triangle_start = pos
            self.triangle_end = pos
            self.drawing = True
            self.update()


        #Прямоугольник
        elif tool == "rect":
            self.rect_start = pos #Верхний левый угол
            self.rect_end = pos #Нижний правый угол
            self.drawing = True
            self.update()
            return

        #Круг
        elif tool == "circle":
            self.circle_start = pos
            self.circle_end = pos
            self.drawing = True
            self.update()

        #Пентагон
        elif tool == "pentagon":
            self.pentagon_start = pos
            self.pentagon_end = pos
            self.drawing = True
            self.update()

        #Хекс
        elif tool == "hexagon":
            self.hexagon_start = pos
            self.hexagon_end = pos
            self.drawing = True
            self.update()

        #Стрелка
        elif tool == "arrow":
            self.arrow_start = pos
            self.arrow_end = pos
            self.drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        tool = self.get_tool()
        pos = event.position()

        #Для кривой линии
        if tool == "line" and self.drawing:
            self.points.append(pos)
            self.update()

        #Для прямой линии
        if tool == "straight" and self.drawing and self.straight_start:
            self.straight_end = pos
            self.update()
            return

        #Для треугольника
        elif tool == "triangle" and self.drawing and self.triangle_start:
            self.triangle_end = pos
            self.update()

        #Для прямоугольника
        elif tool == "rect" and self.drawing and self.rect_start:
            self.rect_end = pos
            self.update()
            return

        #Для круга
        elif tool == "circle" and self.drawing and self.circle_start:
            self.circle_end = pos
            self.update()

        #Для пентагона
        elif tool == "pentagon" and self.drawing and self.pentagon_start:
            self.pentagon_end = pos
            self.update()

        #Для хекса
        elif tool == "hexagon" and self.drawing and self.hexagon_start:
            self.hexagon_end = pos
            self.update()

        #Для стрелки
        elif tool == "arrow" and self.drawing and self.arrow_start:
            self.arrow_end = pos
            self.update()

    def mouseReleaseEvent(self, event):
        tool = self.get_tool()
        pos = event.position()
        if event.button() != Qt.LeftButton:
            return

        if tool == "line" and self.drawing:
            self.drawing = False

            # сохраняем завершённую линию
            if len(self.points) > 1:
                self.lines.append(self.points.copy())  # сохраняем копию
            self.points = []
            self.update()

        if tool == "straight" and self.drawing:
            self.drawing = False
            self.straight_lines.append((self.straight_start, pos))
            self.straight_start = None
            self.straight_end = None
            self.update()
            return

        elif tool == "triangle" and self.drawing and self.triangle_start:
            self.drawing = False

            #Создаём правильный треугольник
            start = self.triangle_start
            end = self.triangle_end

            size = min(abs(end.x() - start.x()), abs(end.y() - start.y()))
            x0 = start.x()
            y0 = start.y()

            #Вершины равностороннего треугольника
            p1 = QPointF(x0, y0 + size)  #Левый нижний
            p2 = QPointF(x0 + size / 2, y0)  #Верхний
            p3 = QPointF(x0 + size, y0 + size)  #Правый нижний

            self.triangles.append([p1, p2, p3])
            self.triangle_start = None
            self.triangle_end = None
            self.update()

        elif tool == "rect" and self.drawing and self.rect_start:
            self.drawing = False
            self.rectangles.append((self.rect_start, pos))
            self.rect_start = None
            self.rect_end = None
            self.update()
            return

        elif tool == "circle" and self.drawing and self.circle_start:
            self.drawing = False
            start = self.circle_start
            end = self.circle_end

            size = min(abs(end.x() - start.x()), abs(end.y() - start.y()))
            x0 = start.x()
            y0 = start.y()
            self.circles.append((x0, y0, size))
            self.circle_start = None
            self.circle_end = None
            self.update()

        elif tool == "pentagon" and self.drawing and self.pentagon_start:
            self.drawing = False
            start = self.pentagon_start
            end = self.pentagon_end

            size = min(abs(end.x() - start.x()), abs(end.y() - start.y()))
            self.pentagons.append((start, size))
            self.pentagon_start = None
            self.pentagon_end = None
            self.update()

        elif tool == "hexagon" and self.drawing and self.hexagon_start:
            self.drawing = False
            start = self.hexagon_start
            end = self.hexagon_end

            size = min(abs(end.x() - start.x()), abs(end.y() - start.y()))
            self.hexagons.append((start, size))
            self.hexagon_start = None
            self.hexagon_end = None
            self.update()

        elif tool == "arrow" and self.drawing and self.arrow_start:
            self.drawing = False
            start = self.arrow_start
            end = self.arrow_end
            self.arrows.append((start, end))
            self.arrow_start = None
            self.arrow_end = None
            self.update()

            # Многоугольник
            def regular_polygon(center, size, sides):
                cx, cy = center.x(), center.y()
                radius = size / 2
                points = []
                for i in range(sides):
                    angle = 2 * pi * i / sides - pi / 2  # верхняя вершина наверху
                    x = cx + radius * cos(angle)
                    y = cy + radius * sin(angle)
                    points.append(QPointF(x, y))
                return points

    #Наконечник стрелки
    def arrowHead(self, start, end, size=30):
        angle = atan2(end.y() - start.y(), end.x() - start.x())

        # два угла по сторонам от основной линии (30°)
        left = angle + pi - pi / 6
        right = angle + pi + pi / 6

        p1 = QPointF(
            end.x() + size * cos(left),
            end.y() + size * sin(left)
        )
        p2 = QPointF(
            end.x() + size * cos(right),
            end.y() + size * sin(right)
        )

        return p1, p2

    def regularPolygon(self, center, size, sides):
        cx, cy = center.x(), center.y()
        radius = size / 2
        points = []
        for i in range(sides):
            angle = 2 * pi * i / sides - pi / 2  # верхняя вершина наверху
            x = cx + radius * cos(angle)
            y = cy + radius * sin(angle)
            points.append(QPointF(x, y))
        return points

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(QColor(150, 0, 150))
        pen.setWidth(3)
        painter.setPen(pen)
        tool = self.get_tool()

        #Сохранение кривой линии
        for line in self.lines:
            for i in range(1, len(line)):
                painter.drawLine(line[i - 1], line[i])

        #Текущая кривая линия
        for i in range(1, len(self.points)):
            painter.drawLine(self.points[i - 1], self.points[i])

        #Сохранение прямой линии
        for s, e in self.straight_lines:
            painter.drawLine(s, e)

        #Предпросмотр прямой линии
        if self.get_tool() == "straight" and self.drawing and self.straight_start and self.straight_end:
            painter.drawLine(self.straight_start, self.straight_end)

        #Готовый треугольник
        for tri in self.triangles:
            if len(tri) == 3:
                poly = QPolygonF(tri)
                painter.drawPolygon(poly)

        #Предпросмотр равностороннего треугольника
        if tool == "triangle" and self.drawing and self.triangle_start and self.triangle_end:
            start = self.triangle_start
            end = self.triangle_end
            size = min(abs(end.x() - start.x()), abs(end.y() - start.y()))
            x0 = start.x()
            y0 = start.y()

            p1 = QPointF(x0, y0 + size)
            p2 = QPointF(x0 + size / 2, y0)
            p3 = QPointF(x0 + size, y0 + size)
            painter.drawPolygon(QPolygonF([p1, p2, p3]))

        #Готовый прямоугольник
        for start, end in self.rectangles:
            x = min(start.x(), end.x())
            y = min(start.y(), end.y())
            w = abs(end.x() - start.x())
            h = abs(end.y() - start.y())
            painter.drawRect(x, y, w, h)

        #Предпросмотр прямоуголника
        tool = self.get_tool()
        if tool == "rect" and self.drawing and self.rect_start and self.rect_end:
            x = min(self.rect_start.x(), self.rect_end.x())
            y = min(self.rect_start.y(), self.rect_end.y())
            w = abs(self.rect_end.x() - self.rect_start.x())
            h = abs(self.rect_end.y() - self.rect_start.y())
            painter.drawRect(x, y, w, h)

        #Сохранённые круги
        for x0, y0, size in self.circles:
            painter.drawEllipse(x0, y0, size, size)

        #Предпросмотр круга
        if tool == "circle" and self.drawing and self.circle_start and self.circle_end:
            start = self.circle_start
            end = self.circle_end
            size = min(abs(end.x() - start.x()), abs(end.y() - start.y()))
            painter.drawEllipse(start.x(), start.y(), size, size)

        #Сохранённый пентагон
        for start, size in self.pentagons:
            center = QPointF(start.x() + size / 2, start.y() + size / 2)
            points = self.regularPolygon(center, size, 5)
            painter.drawPolygon(QPolygonF(points))

        #Предпросмотр пентагона
        if tool == "pentagon" and self.drawing and self.pentagon_start and self.pentagon_end:
            size = min(abs(self.pentagon_end.x() - self.pentagon_start.x()),
                       abs(self.pentagon_end.y() - self.pentagon_start.y()))
            center = QPointF(self.pentagon_start.x() + size / 2, self.pentagon_start.y() + size / 2)
            points = self.regularPolygon(center, size, 5)
            painter.drawPolygon(QPolygonF(points))

        #Сохранённый хекс
        for start, size in self.hexagons:
            center = QPointF(start.x() + size / 2, start.y() + size / 2)
            points = self.regularPolygon(center, size, 6)
            painter.drawPolygon(QPolygonF(points))

        #Предпросмотр хекса
        if tool == "hexagon" and self.drawing and self.hexagon_start and self.hexagon_end:
            size = min(abs(self.hexagon_end.x() - self.hexagon_start.x()),
                       abs(self.hexagon_end.y() - self.hexagon_start.y()))
            center = QPointF(self.hexagon_start.x() + size / 2, self.hexagon_start.y() + size / 2)
            points = self.regularPolygon(center, size, 6)
            painter.drawPolygon(QPolygonF(points))

        #Сохранённые стрелки
        for start, end in self.arrows:
            painter.drawLine(start, end)
            h1, h2 = self.arrowHead(start, end)
            painter.drawLine(end, h1)
            painter.drawLine(end, h2)

        #Предпросмотр стрелки
        if tool == "arrow" and self.drawing and self.arrow_start and self.arrow_end:
            start = self.arrow_start
            end = self.arrow_end
            painter.drawLine(start, end)
            h1, h2 = self.arrowHead(start, end)
            painter.drawLine(end, h1)
            painter.drawLine(end, h2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Inter")
        self.setGeometry(200, 200, 900, 600)

        self.current_tool = "line"

        #Панель инструментов
        toolbar = QToolBar("Инструменты")
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        self.add_tool_button(toolbar, "Кривая линия", "line")
        self.add_tool_button(toolbar, "Прямая линия", "straight")
        self.add_tool_button(toolbar, "Прямоугольник", "rect")
        self.add_tool_button(toolbar, "Треугольник", "triangle")
        self.add_tool_button(toolbar, "Пятиугольник", "pentagon")
        self.add_tool_button(toolbar, "Шестиугольник", "hexagon")
        self.add_tool_button(toolbar, "Круг", "circle")
        self.add_tool_button(toolbar, "Стрелка", "arrow")

        #Холст
        self.canvas = Canvas(self.get_current_tool)
        self.setCentralWidget(self.canvas)

    def add_tool_button(self, toolbar: QToolBar, name: str, tool_id: str):
        action = QAction(name, self)
        action.setCheckable(True)

        if tool_id == self.current_tool:
            action.setChecked(True)

        action.triggered.connect(lambda checked, t=tool_id: self.select_tool(t))
        toolbar.addAction(action)

    def select_tool(self, tool_id):
        self.current_tool = tool_id
        print("Инструмент изменён на:", tool_id)

        #Cнять выделение со всех
        for action in self.findChildren(QAction):
            action.setChecked(action.text().lower() == tool_id)

    def get_current_tool(self):
        return self.current_tool


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
