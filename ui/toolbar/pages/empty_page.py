from .base import OptionsPage
from PyQt6.QtWidgets import QLabel


# ============================================================
# Empty / Select options
# ============================================================
class EmptyOptionsPage(OptionsPage):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        label = QLabel(text)
        label.setStyleSheet("color: #777;")
        self.layout.addWidget(label)
        self.finish()
