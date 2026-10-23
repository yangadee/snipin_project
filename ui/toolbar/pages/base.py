from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget
from PyQt6.QtCore import QSize, pyqtSignal


# ============================================================
# Base options page
# ============================================================
class OptionsPage(QWidget):
    optionsChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 2, 4, 2)
        self.layout.setSpacing(1)

    @property
    def separator(self):
        return self._make_separator()

    def add_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("color: #555;")
        self.layout.addWidget(label)

    def start(self):
        self.layout.addStretch()

    def finish(self):
        self.layout.addStretch()

    def set_options(self, *arg):
        return

    def _make_button(self, icon, tooltip):
        button = QToolButton()
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setFixedSize(24, 24)
        return button

    def _make_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedHeight(20)
        separator.setContentsMargins(0, 2, 0, 2)  # total 24
        return separator
