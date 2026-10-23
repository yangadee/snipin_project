from resources import icon_provider
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtCore import QSignalBlocker
from .base import OptionsPage
from ..widgets import ColorPalette, CompactSlider, DotButton


# ============================================================
# Pen / Line options
# ============================================================
class PenOptionsPage(OptionsPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None
        self.start()  # make center
        self.width = DotButton()  # DotSizeButton()
        self.width.setFixedWidth(24)
        self.width.setCheckable(True)
        self.width.setChecked(True)
        # Make it always checked.
        btn_group = QButtonGroup(self)
        btn_group.setExclusive(True)
        btn_group.addButton(self.width)

        self.layout.addWidget(self.width)
        self.layout.addSpacing(4)
        self.layout.addWidget(self.separator)

        self.opacity = CompactSlider()
        self.opacity.setRange(1, 100)
        self.opacity.setFixedSize(40, 24)
        self.layout.addWidget(self.opacity)

        self.layout.addWidget(self.separator)

        self.color = ColorPalette()
        self.color.setFixedHeight(24)
        self.layout.addWidget(self.color)

        self.finish()
        self.color.color_selected.connect(self._changed)
        self.width.valueChanged.connect(self._changed)
        self.opacity.valueChanged.connect(self._changed)

    def set_options(self, options):
        self.options = options
        blockers = [
            QSignalBlocker(self.color),
            QSignalBlocker(self.width),
            QSignalBlocker(self.opacity),
        ]
        self.color.setColor(options.color)
        self.width.setValue(options.width)
        self.opacity.setValue(options.opacity)

    def _changed(self, *_):
        if not self.options:
            return
        self.options.color = self.color.color()
        self.options.width = self.width.get_size()
        self.options.opacity = self.opacity.value()
        self.optionsChanged.emit()
