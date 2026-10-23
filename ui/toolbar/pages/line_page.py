from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtCore import QSignalBlocker
from resources import icon_provider
from ui.models.tools import LineType
from .base import OptionsPage
from ..widgets import ColorPalette, DotButton


# ============================================================
# Line options
# ============================================================
class LineOptionsPage(OptionsPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None

        self.start()  # make align center.

        self.width = DotButton()
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
        self._arrow_type = self._make_button(
            icon_provider.icon("arrow"),
            "<b>Arrow</b><br><span style='color: #888888;'>Hold Shift for Straight</span>",
        )
        self._line_type = self._make_button(
            icon_provider.icon("line"),
            "<b>Line</b><br><span style='color: #888888;'>Hold Shift for Straight</span>",
        )
        btn_group = QButtonGroup(self)
        btn_group.setExclusive(True)
        btn_group.addButton(self._arrow_type)
        btn_group.addButton(self._line_type)

        self.layout.addWidget(self._line_type)
        self.layout.addWidget(self._arrow_type)

        self.layout.addWidget(self.separator)

        self.color = ColorPalette()
        self.color.setFixedHeight(24)
        self.layout.addWidget(self.color)

        self.finish()
        self.color.color_selected.connect(self._changed)
        self.width.valueChanged.connect(self._changed)
        btn_group.buttonClicked.connect(self._changed)

    def set_options(self, options):
        self.options = options
        blockers = [
            QSignalBlocker(self.color),
            QSignalBlocker(self.width),
            QSignalBlocker(self._line_type),
            QSignalBlocker(self._arrow_type),
        ]
        self.color.setColor(options.color)
        self.width.setValue(options.width)
        self._line_type.setChecked(options.line_type == LineType.LINE)
        self._arrow_type.setChecked(options.line_type == LineType.ARROW)

    def _changed(self, *_):
        if not self.options:
            return
        if self._line_type.isChecked():
            line_type = LineType.LINE

        elif self._arrow_type.isChecked():
            line_type = LineType.ARROW
        else:
            return
        self.options.color = self.color.color()
        self.options.width = self.width.get_size()
        self.options.line_type = line_type
        self.optionsChanged.emit()
