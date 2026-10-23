from resources import icon_provider
from ui.models.tools import ShapeType
from .base import OptionsPage
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from ..widgets import ColorPalette, CompactSlider, DotButton


# ============================================================
# Shape options
# ============================================================
class ShapeOptionsPage(OptionsPage):
    shapeTypeChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = None
        self.start()
        # self.add_label("Width")
        self.width = DotButton()  # DotSizeButton()  # QSpinBox()
        self.width.setCheckable(True)
        self.layout.addWidget(self.width)

        self.fill = self._make_button(icon_provider.icon("fill_up"), "Fill shape")
        self.fill.setCheckable(True)
        self.layout.addWidget(self.fill)

        fill_btn_group = QButtonGroup(self)
        fill_btn_group.setExclusive(True)
        fill_btn_group.addButton(self.width)
        fill_btn_group.addButton(self.fill)

        self.layout.addWidget(self.separator)
        self._shape_rect = self._make_button(
            icon_provider.icon("rect"),
            "Rectangle<br><span style='color: #888888;'>Hold Shift for Square</span>",
        )
        self._shape_ellipse = self._make_button(
            icon_provider.icon("ellipse"),
            "Ellipse<br><span style='color: #888888;'>Hold Shift for Circle</span>",
        )
        btn_group = QButtonGroup(self)
        btn_group.setExclusive(True)
        btn_group.addButton(self._shape_rect)
        btn_group.addButton(self._shape_ellipse)

        self.layout.addWidget(self._shape_rect)
        self.layout.addWidget(self._shape_ellipse)
        self.layout.addWidget(self.separator)

        self.opacity = CompactSlider()
        self.opacity.setToolTip("Opacity (%)")
        self.opacity.setRange(1, 100)
        self.opacity.setFixedSize(40, 24)
        self.layout.addWidget(self.opacity)

        self.layout.addWidget(self.separator)

        self.color = ColorPalette()
        self.layout.addWidget(self.color)

        self.finish()
        self.color.colorChanged.connect(self._changed)
        # self.width.valueChanged.connect(self._changed)
        # self.fill.toggled.connect(self._changed)
        self.opacity.valueChanged.connect(self._changed)
        btn_group.buttonClicked.connect(self._changed)
        fill_btn_group.buttonClicked.connect(self._mode_clicked)

    def _mode_clicked(self, button):
        if self.options is None:
            return
        old_fill = self.options.fill
        new_fill = button is self.fill and not old_fill
        if new_fill == old_fill:
            return
        if not new_fill:
            self.width.setChecked(True)

        # Save the opacity of the mode we're leaving.
        if old_fill:
            self.options.fill_opacity = self.opacity.value()
        else:
            self.options.opacity = self.opacity.value()

        blocker = QSignalBlocker(self.opacity)
        self.opacity.setValue(
            self.options.fill_opacity if new_fill else self.options.opacity
        )
        del blocker
        self._changed()

    def set_options(self, options):
        self.options = options
        blockers = [
            QSignalBlocker(self.color),
            QSignalBlocker(self.width),
            QSignalBlocker(self.fill),
            QSignalBlocker(self.fill),
            QSignalBlocker(self.opacity),
            QSignalBlocker(self._shape_rect),
        ]
        self.color.setColor(options.color)
        self.width.setValue(options.width)
        self.shape_type = options.shape
        (self.fill if options.fill else self.width).setChecked(
            True
        )  # prevent both start as false
        self.opacity.setValue(options.fill_opacity if options.fill else options.opacity)
        self._shape_ellipse.setChecked(self.options.shape == ShapeType.ELLIPSE)
        self._shape_rect.setChecked(self.options.shape == ShapeType.RECT)

    def _changed(self, *_):
        if not self.options:
            return
        _shape_type = (
            ShapeType.ELLIPSE if self._shape_ellipse.isChecked() else ShapeType.RECT
        )
        self.options.shape = _shape_type
        self.options.color = self.color.color()
        self.options.width = self.width.get_size()
        self.options.fill = self.fill.isChecked()
        self.options.fill_color = self.color.color()  # self.fill_color.color()
        if self.options.fill:
            self.options.fill_opacity = self.opacity.value()
        else:
            self.options.opacity = self.opacity.value()
        self.optionsChanged.emit()
