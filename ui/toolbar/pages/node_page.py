from resources import icon_provider
from ui.models.tools import NodeShape
from .base import OptionsPage
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtCore import QSignalBlocker
from ..widgets import ColorPalette, SizeButton


# ============================================================
# Node options
# ============================================================
class NodeOptionsPage(OptionsPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None
        self.start()  # align center.

        self.size = SizeButton()
        self.size.setChecked(True)
        self.layout.addWidget(self.size)

        self.layout.addWidget(self.separator)

        self._shape_rect = self._make_button(icon_provider.icon("rect"), "rect")
        self._shape_hexagon = self._make_button(
            icon_provider.icon("hexagon"), "hexagon"
        )
        self._shape_circle = self._make_button(icon_provider.icon("circle"), "circle")
        btn_group = QButtonGroup(self)
        btn_group.setExclusive(True)
        btn_group.addButton(self._shape_rect)
        btn_group.addButton(self._shape_hexagon)
        btn_group.addButton(self._shape_circle)

        self.layout.addWidget(self._shape_rect)
        self.layout.addWidget(self._shape_hexagon)
        self.layout.addWidget(self._shape_circle)

        self.layout.addWidget(self.separator)

        self.color = ColorPalette()
        self.layout.addWidget(self.color)

        self.finish()
        self.color.colorChanged.connect(self._changed)
        self.size.valueChanged.connect(self._changed)
        btn_group.buttonClicked.connect(self._changed)

    def set_options(self, options):
        self.options = options
        blockers = [
            QSignalBlocker(self.color),
            QSignalBlocker(self.size),
            QSignalBlocker(self._shape_rect),
            QSignalBlocker(self._shape_hexagon),
            QSignalBlocker(self._shape_circle),
        ]
        self.color.setColor(options.color)
        self.size.setValue(int(options.size))
        self._shape_rect.setChecked(options.shape == NodeShape.RECT)
        self._shape_hexagon.setChecked(options.shape == NodeShape.HEXAGON)
        self._shape_circle.setChecked(options.shape == NodeShape.CIRCLE)

    def _changed(self, *_):
        if self.options is None:
            return

        if self._shape_circle.isChecked():
            node_shape = NodeShape.CIRCLE

        elif self._shape_hexagon.isChecked():
            node_shape = NodeShape.HEXAGON

        elif self._shape_rect.isChecked():
            node_shape = NodeShape.RECT

        else:
            return

        self.options.color = self.color.color()
        self.options.shape = node_shape
        self.options.size = self.size.value()

        self.optionsChanged.emit()
