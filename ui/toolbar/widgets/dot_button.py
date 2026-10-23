from PyQt6.QtWidgets import QToolButton
from PyQt6.QtGui import QPainter, QColor, QWheelEvent
from PyQt6.QtCore import Qt, QRectF, pyqtSignal


class DotButton(QToolButton):
    """Show the actual dot size, or a capped dot with its pixel value."""

    valueChanged = pyqtSignal(int)

    def __init__(self, label="", tool="", width=3, visual_size=3, parent=None):
        super().__init__(parent)

        self.label = label
        self.tool = tool
        self.dot_size = width
        self.visual_size = visual_size
        self.min_size = 1
        self.max_size = 99
        self.step = 1
        self.setValue(width)
        self.setCheckable(False)
        self.setFixedSize(24, 24)

        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 5px;
                padding: 0px; margin: 0px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 255, 45);
            }
            QPushButton:checked {
                background-color: rgba(0, 120, 255, 180);
                border: 1px solid rgba(180, 220, 255, 220);
            }
        """)

    def value(self):
        return self.dot_size

    def get_size(self):
        return self.dot_size

    def setValue(self, value):
        value = max(self.min_size, min(self.max_size, int(value)))
        if value == self.dot_size:
            return

        self.dot_size = value
        self.visual_size = value
        self.setToolTip(f"Size: {self.dot_size}px\nUse mouse wheel to adjust.")
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        change = self.step if delta > 0 else -self.step
        new_size = max(
            self.min_size,
            min(self.max_size, self.dot_size + change),
        )

        if new_size != self.dot_size:
            self.setValue(new_size)
            self.valueChanged.emit(new_size)

        event.accept()

    def paintEvent(self, event):
        super().paintEvent(event)  # Keep stylesheet hover/checked background.

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = 2
        max_diameter = min(self.width(), self.height()) - 2 * margin
        diameter = min(self.dot_size, max_diameter)
        show_value = self.dot_size >= max_diameter
        dot_rect = QRectF(
            (self.width() - diameter) / 2,
            (self.height() - diameter) / 2,
            diameter,
            diameter,
        )

        painter.setPen(Qt.PenStyle.NoPen)
        dot_color = QColor("white") if self.isChecked() else QColor("black")
        painter.setBrush(dot_color)
        painter.drawEllipse(dot_rect)

        if show_value:
            font = painter.font()
            font.setPixelSize(9)
            font.setBold(True)
            painter.setFont(font)
            text_color = QColor("black") if self.isChecked() else QColor("white")
            painter.setPen(text_color)
            painter.drawText(dot_rect, Qt.AlignmentFlag.AlignCenter, str(self.dot_size))
        painter.end()
