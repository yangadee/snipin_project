from PyQt6.QtWidgets import QToolButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QWheelEvent


class SizeButton(QToolButton):
    valueChanged = pyqtSignal(int)

    def __init__(self, size: int = 5, tool_name: str = "", parent=None):
        super().__init__(parent)

        self.tool_name = tool_name
        self.min_size = 1
        self.max_size = 99
        self.step = 1
        self.current_size = max(self.min_size, min(self.max_size, int(size)))

        self.setFixedSize(24, 24)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        self.setStyleSheet("""
            QToolButton {
                background-color: rgba(0, 120, 255, 150);
                border: 1px solid rgba(180, 220, 255, 220);
                border-radius: 5px;
                padding: 0px;
                color: white;
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: rgba(0, 120, 255, 210);
            }
        """)

        self._update_text()

    def _update_text(self):
        self.setText(str(self.current_size))
        self.setToolTip(f"Size: {self.current_size}px\nUse mouse wheel to adjust.")

    def setValue(self, value: int):
        value = max(self.min_size, min(self.max_size, int(value)))
        if value == self.current_size:
            return

        self.current_size = value
        self._update_text()
        self.valueChanged.emit(value)

    def value(self) -> int:
        return self.current_size

    def set_size(self, size: int):
        self.setValue(size)

    def get_size(self) -> int:
        return self.value()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        change = self.step if delta > 0 else -self.step
        self.setValue(self.current_size + change)
        event.accept()
