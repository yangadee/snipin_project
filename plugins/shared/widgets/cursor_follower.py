import sys
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget


class CursorFollower(QWidget):
    """
    A custom overlay widget that displays a localized loading/waiting animation
    adjacent to the global mouse cursor.

    Usage:
        instance.start()
        instance.stop()
    """

    def __init__(self, parent=None, timeout=5000):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.ToolTip
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Optional, additionally prevents Qt mouse events
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(40, 40)
        self.angle = 0
        self.offset_from_cursor = 5
        # Update postion timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(30)

        # Auto close timeout, prevent code bug
        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.stop)

    def update_position(self):
        pos = QCursor.pos()
        x = pos.x() + self.offset_from_cursor
        y = pos.y() + self.offset_from_cursor
        # Keep the indicator inside the cursor's current screen
        screen = QApplication.screenAt(pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            x = min(x, available.right() - self.width() + 1)
            y = min(y, available.bottom() - self.height() + 1)
            x = max(x, available.left())
            y = max(y, available.top())
        self.move(x, y)
        self.angle = (self.angle + 15) % 360
        self.update()

    def start(self, timeout=10000):
        self.show()
        self.raise_()
        self.timer.start(30)
        self.timeout_timer.start(timeout)

    def stop(self):
        self.timer.stop()
        self.timeout_timer.stop()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        pen = QPen(QColor(0, 128, 255, 220))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(-10, -10, 20, 20, 0, 270 * 16)


# # -----------------------------------------
# # TEST EXAMPLE
# # -----------------------------------------
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     cursor_follower = CursorFollower()
#     cursor_follower.show()
#     sys.exit(app.exec())
