from resources import icon_provider
from ui.toolbar.widgets.color_palette import ColorPalette
from ui.toolbar.widgets.dot_button import DotButton
from ui.toolbar.widgets.size_button import SizeButton

from .base import OptionsPage
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QSignalBlocker


# ============================================================
# Text options
# ============================================================
class TextOptionsPage(OptionsPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None
        self.start()  # align center.

        self.font_size = SizeButton()
        self.font_size.setChecked(True)
        self.layout.addWidget(self.font_size)

        self.layout.addWidget(self.separator)

        self.color = ColorPalette()
        self.layout.addWidget(self.color)

        self.finish()
        self.color.colorChanged.connect(self._changed)
        self.font_size.valueChanged.connect(self._changed)

    def set_options(self, options):
        self.options = options
        blockers = [
            QSignalBlocker(self.color),
            QSignalBlocker(self.font_size),
        ]

        self.color.setColor(options.color)
        self.font_size.setValue(int(options.font_size))

    def _changed(self, *_):
        if not self.options:
            return
        self.options.color = self.color.color()
        self.options.font_size = self.font_size.value()
        self.optionsChanged.emit()
