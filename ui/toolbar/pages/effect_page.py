from resources import icon_provider
from ui.models.tools import EffectShape, EffectType
from .base import OptionsPage
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtCore import QSignalBlocker
from ..widgets import CompactSlider, DotButton


# ============================================================
# Mosaic options
# ============================================================
class EffectOptionsPage(OptionsPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None
        self.start()

        self.effect_blur = self._make_button(icon_provider.icon("blur"), "Blur")
        self.shape_rect = self._make_button(icon_provider.icon("rect"), "Rect")
        self.brush_size = DotButton()
        self.brush_size.setCheckable(True)

        btn_group = QButtonGroup(self)
        btn_group.setExclusive(True)
        btn_group.addButton(self.brush_size)
        btn_group.addButton(self.shape_rect)

        self.layout.addWidget(self.brush_size)
        self.layout.addWidget(self.shape_rect)
        self.layout.addWidget(self.separator)
        self.layout.addWidget(self.effect_blur)
        self.layout.addWidget(self.separator)

        self.strength = CompactSlider()
        self.strength.setRange(1, 10)
        self.strength.setFixedSize(40, 24)
        self.layout.addWidget(self.strength)
        self.finish()
        self.brush_size.valueChanged.connect(self._changed)
        self.brush_size.clicked.connect(self._changed)
        self.strength.valueChanged.connect(self._changed)
        self.shape_rect.clicked.connect(self._changed)
        self.effect_blur.clicked.connect(self._changed)

    def set_options(self, options):
        self.options = options
        blockers = [
            QSignalBlocker(self.brush_size),
            QSignalBlocker(self.strength),
            QSignalBlocker(self.shape_rect),
            QSignalBlocker(self.effect_blur),
        ]
        self.brush_size.setValue(int(options.brush_size))
        self.strength.setValue(int(options.strength))
        self.shape_rect.setChecked(options.shape == EffectShape.RECT)
        self.brush_size.setChecked(options.shape == EffectShape.BRUSH)
        self.effect_blur.setChecked(options.effect == EffectType.BLUR)

    def _changed(self, *_):
        if not self.options:
            return

        _shape = EffectShape.RECT if self.shape_rect.isChecked() else EffectShape.BRUSH
        _effect = EffectType.BLUR if self.effect_blur.isChecked() else EffectType.MOSAIC
        self.options.effect = _effect
        self.options.shape = _shape
        self.options.brush_size = self.brush_size.value()
        self.options.strength = self.strength.value()
        self.optionsChanged.emit()
