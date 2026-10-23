from __future__ import annotations
import math
from functools import partial
from resources.icon_provider import icon_provider as AppIcon
from PyQt6.QtCore import QPointF, QTimer, Qt, pyqtSignal, QSize, QRectF
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QSizePolicy,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QIcon,
    QPainter,
    QPen,
    QBrush,
    QPixmap,
    QResizeEvent,
)


from .pages import (
    EffectOptionsPage,
    LineOptionsPage,
    NodeOptionsPage,
    PenOptionsPage,
    PluginOptionsPage,
    TextOptionsPage,
    ShapeOptionsPage,
)
from sdk.models import PluginStatus
from ui.annotation.items import EditableTextItem, CustomNode

from ui.models.annotation import ANNOTATION_DATA
from ui.models.tools import Tool, ToolAction, EffectType, EffectShape
from ui.models.tool_state import ToolSpec, ToolState
from ui.models.tool_options import (
    EffectOptions,
    LineOptions,
    NodeOptions,
    ToolOptions,
    PluginOptions,
    ShapeOptions,
    PenOptions,
    TextOptions,
)
from ui.annotation.handlers import (
    TextHandler,
    PenHandler,
    LineHandler,
    NodeHandler,
    ShapeHandler,
    EffectHandler,
)

# Keep custom cursor pixmaps reasonably bounded.
MIN_CURSOR_SIZE = 20
MAX_CURSOR_SIZE = 96

CURSOR_PADDING = 6


def _bounded_cursor_dimension(
    diameter: float,
) -> int:
    return max(
        MIN_CURSOR_SIZE,
        min(
            MAX_CURSOR_SIZE,
            math.ceil(diameter) + CURSOR_PADDING * 2,
        ),
    )


def _contrast_color(color: QColor) -> QColor:
    luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return QColor("#000000") if luminance > 160 else QColor("#FFFFFF")


def arrow_cursor(options: ToolOptions | None = None) -> QCursor:
    return QCursor(Qt.CursorShape.ArrowCursor)


def cross_cursor(options: ToolOptions | None = None) -> QCursor:
    return QCursor(Qt.CursorShape.CrossCursor)


def text_cursor(options: ToolOptions | None = None) -> QCursor:
    return QCursor(Qt.CursorShape.IBeamCursor)


def pen_cursor(options: PenOptions) -> QCursor:
    diameter = max(4, round(options.width))
    padding = 4
    pixmap_size = diameter + padding * 2
    pixmap = QPixmap(pixmap_size, pixmap_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(options.color)
        # if options.highlight:
        #     color.setAlpha(100)
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        painter.setBrush(color)
        painter.drawEllipse(padding, padding, diameter, diameter)
    finally:
        painter.end()
    center = pixmap_size // 2
    return QCursor(pixmap, center, center)


def line_cursor(options) -> QCursor:
    size = 25
    center = size // 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    color = QColor(getattr(options, "color", QColor("#FF0000")))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # White/black outside stroke keeps cursor visible
        # regardless of screenshot background.
        painter.setPen(QPen(_contrast_color(color), 3))
        painter.drawLine(center, 2, center, size - 3)
        painter.drawLine(2, center, size - 3, center)
        painter.setPen(QPen(color, 1))
        painter.drawLine(center, 2, center, size - 3)
        painter.drawLine(2, center, size - 3, center)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(center, center), 2.5, 2.5)

    finally:
        painter.end()
    return QCursor(pixmap, center, center)


def highlight_cursor(options) -> QCursor:
    width = max(
        2.0,
        float(getattr(options, "width", 20.0)),
    )
    color = QColor(getattr(options, "color", "#FFFF00"))
    # Visual highlighter opacity only.
    fill_color = QColor(color)
    fill_color.setAlpha(90)
    diameter = width
    pixmap_size = _bounded_cursor_dimension(diameter)
    center = pixmap_size // 2
    pixmap = QPixmap(pixmap_size, pixmap_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )
        radius = min(diameter / 2.0, center - 3)
        painter.setBrush(fill_color)
        painter.setPen(QPen(color, 1.5))
        painter.drawEllipse(QPointF(center, center), radius, radius)
        # Exact active point
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(center, center), 1.5, 1.5)
    finally:
        painter.end()
    return QCursor(pixmap, center, center)


def blur_brush_cursor(options) -> QCursor:
    brush_size = max(
        2.0,
        float(
            getattr(
                options,
                "brush_size",
                28.0,
            )
        ),
    )

    pixmap_size = _bounded_cursor_dimension(brush_size)

    center = pixmap_size // 2
    pixmap = QPixmap(pixmap_size, pixmap_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = min(brush_size / 2.0, center - 3)
        painter.setBrush(QColor(180, 180, 180, 45))
        pen = QPen(
            QColor(
                255,
                255,
                255,
                210,
            ),
            1.3,
        )
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(center, center), radius, radius)
        # Exact hotspot
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawLine(center - 3, center, center + 3, center)

        painter.drawLine(center, center - 3, center, center + 3)
    finally:
        painter.end()

    return QCursor(pixmap, center, center)


def blur_rect_cursor(options) -> QCursor:
    return QCursor(Qt.CursorShape.CrossCursor)


def _mosaic_brush_cursor(options) -> QCursor:
    brush_size = max(2.0, float(getattr(options, "brush_size", 28.0)))
    pixmap_size = _bounded_cursor_dimension(brush_size)
    center = pixmap_size // 2
    pixmap = QPixmap(pixmap_size, pixmap_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = min(brush_size / 2.0, center - 3)
        # Semi-transparent interior
        painter.setBrush(QColor(80, 80, 80, 80))
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.drawEllipse(QPointF(center, center), radius, radius)
        # Tiny pixel cue at hotspot
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        cell = 2
        colors = (
            QColor("#D8D8D8"),
            QColor("#8A8A8A"),
            QColor("#505050"),
            QColor("#AAAAAA"),
        )
        locations = ((-cell, -cell), (0, -cell), (-cell, 0), (0, 0))
        for color, (dx, dy) in zip(colors, locations):
            painter.fillRect(center + dx, center + dy, cell, cell, color)
    finally:
        painter.end()
    return QCursor(pixmap, center, center)


def mosaic_brush_cursor(options) -> QCursor:
    brush_size = max(2.0, float(getattr(options, "brush_size", 28.0)))
    pixmap_size = _bounded_cursor_dimension(brush_size)
    center = pixmap_size // 2
    pixmap = QPixmap(pixmap_size, pixmap_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = min(brush_size / 2.0, center - 3)
        # --------------------------------
        # Brush-size circle
        # --------------------------------
        painter.setBrush(QColor(80, 80, 80, 50))
        painter.setPen(QPen(QColor(220, 220, 220, 210), 1.2))
        painter.drawEllipse(QPointF(center, center), radius, radius)
        # --------------------------------
        # Mosaic center cue
        #
        # Grow slowly with brush size.
        # 28px brush -> ~6px mosaic
        # 50px brush -> ~10px mosaic
        # 80px brush -> ~14px mosaic
        # --------------------------------
        mosaic_size = max(4, min(16, round(brush_size * 0.18)))
        # Keep even so center remains symmetrical
        if mosaic_size % 2:
            mosaic_size += 1
        cell = max(2, mosaic_size // 4)
        # Make total grid exactly 4 x 4 cells
        grid_size = cell * 4
        start_x = center - grid_size // 2
        start_y = center - grid_size // 2
        colors = (
            QColor("#D0D0D0"),
            QColor("#909090"),
            QColor("#555555"),
            QColor("#B0B0B0"),
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # 4 x 4 mosaic pattern
        for row in range(4):
            for col in range(4):
                color = colors[(row + col) % len(colors)]
                painter.fillRect(
                    start_x + col * cell, start_y + row * cell, cell, cell, color
                )
    finally:
        painter.end()
    return QCursor(pixmap, center, center)


def mosaic_rect_cursor(options) -> QCursor:
    size = 27
    center = size // 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawLine(center, 1, center, size - 2)
        painter.drawLine(1, center, size - 2, center)
        # Tiny pixel-grid cue
        grid_size = 9
        x = center - grid_size // 2
        y = center - grid_size // 2
        painter.fillRect(x, y, grid_size, grid_size, QColor(30, 30, 30, 220))
        painter.setPen(QColor(255, 255, 255, 220))
        for i in range(0, grid_size + 1, 3):
            painter.drawLine(x + i, y, x + i, y + grid_size)
            painter.drawLine(x, y + i, x + grid_size, y + i)
    finally:
        painter.end()
    return QCursor(pixmap, center, center)


def effect_cursor(options) -> QCursor:
    if options.shape == EffectShape.RECT:
        if options.effect == EffectType.MOSAIC:
            return mosaic_rect_cursor(options)
        return blur_rect_cursor(options)
    # BRUSH
    if options.effect == EffectType.MOSAIC:
        return mosaic_brush_cursor(options)
    return blur_brush_cursor(options)


def node_cursor(options) -> QCursor:
    size = 25
    center = size // 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    color = QColor(getattr(options, "color", "#FF0000"))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#FFFFFF"), 2.5))
        painter.drawLine(center, 2, center, size - 3)
        painter.drawLine(2, center, size - 3, center)
        painter.setPen(QPen(color, 1))
        painter.drawLine(center, 2, center, size - 3)
        painter.drawLine(2, center, size - 3, center)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(center, center), 3, 3)
    finally:
        painter.end()
    return QCursor(pixmap, center, center)


def _make_separator() -> QFrame:
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFixedHeight(20)
    separator.setContentsMargins(0, 2, 0, 2)  # total 24
    return separator


# ============================================================
# Floating toolbar
# ============================================================
class FloatingToolbar(QFrame):
    toolStateChanged = pyqtSignal(object)
    toolSpecChanged = pyqtSignal(object)
    actionRequested = pyqtSignal(object)

    # User clicked the spare "+" position
    addToolRequested = pyqtSignal()
    pluginSelected = pyqtSignal(str)

    # geometry change.
    resized = pyqtSignal()

    def __init__(self, parent=None):
        # require parent for focus
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus  # prevent steal focus from pinview
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # set transparent

        self._settings = None

        # ====================================================
        # STYLE
        # ====================================================
        # hidden Tool.SELECT and define
        self.hidden_tools = {Tool.SELECT}

        self._plugin_page = PluginOptionsPage()  # frequent call.
        self.tool_specs = {
            Tool.SELECT: ToolSpec(
                id=Tool.SELECT,
                name="Select",
                icon=AppIcon.icon("cursor"),
                options=None,
                options_page=None,
                handler=None,
            ),
            Tool.SHAPE: ToolSpec(
                id=Tool.SHAPE,
                name="Rect/Ellipse",
                icon=AppIcon.icon("rect_circle"),
                options=ShapeOptions(),
                options_page=ShapeOptionsPage(),
                handler=ShapeHandler(),
                cursor_factory=cross_cursor,
            ),
            Tool.LINE: ToolSpec(
                id=Tool.LINE,
                name="Line/Arrow",
                icon=AppIcon.icon("arrow_line"),
                options=LineOptions(),
                options_page=LineOptionsPage(),
                handler=LineHandler(),
                cursor_factory=line_cursor,
            ),
            Tool.PEN: ToolSpec(
                id=Tool.PEN,
                name="Pen",
                icon=AppIcon.icon("pen"),
                options=PenOptions(),
                options_page=PenOptionsPage(),
                handler=PenHandler(),
                cursor_factory=pen_cursor,
            ),
            Tool.MARKER: ToolSpec(
                id=Tool.MARKER,
                name="Marker pen",
                icon=AppIcon.icon("marker"),
                options=PenOptions(width=20, opacity=35),
                options_page=PenOptionsPage(),
                handler=LineHandler(),
                cursor_factory=highlight_cursor,
            ),
            Tool.TEXT: ToolSpec(
                id=Tool.TEXT,
                name="Text",
                icon=AppIcon.icon("text"),
                options=TextOptions(),
                options_page=TextOptionsPage(),
                handler=TextHandler(),
                cursor_factory=text_cursor,
            ),
            Tool.NODE: ToolSpec(
                id=Tool.NODE,
                name="number circle",
                icon=AppIcon.icon("node"),
                options=NodeOptions(),
                options_page=NodeOptionsPage(),
                handler=NodeHandler(),
                cursor_factory=node_cursor,
            ),
            Tool.EFFECT: ToolSpec(
                id=Tool.EFFECT,
                name="mosaic/blue",
                icon=AppIcon.icon("mosaic"),
                options=EffectOptions(),
                options_page=EffectOptionsPage(),
                handler=EffectHandler(),
                cursor_factory=effect_cursor,
            ),
            Tool.PLUGIN: ToolSpec(
                id=Tool.PLUGIN,
                name="Plugins",
                icon=AppIcon.icon("plugin"),
                options=PluginOptions(),
                options_page=self._plugin_page,
                handler=None,
            ),
        }
        self.tool_state = None
        self._current_tool = Tool.SELECT
        # user/plugin tool storage
        self._user_tools = {}

        self._build_ui()
        self._connect_ui()
        self.set_tool(self._current_tool)
        self.adjustSize()

    def set_tool_visible(self, tool: Tool, visible: bool):
        button = self._tool_buttons.get(tool)
        if button is None:
            return
        button.setVisible(visible)
        spec = self.tool_specs.get(tool)
        if spec is not None and spec.options_page is not None:
            # Usually don't need to hide page manually,
            # because only active page is displayed.
            pass
        self.adjustSize()

    def set_tool_action_visible(self, action: ToolAction, visible: bool):
        """ """
        button = self.action_buttons.get(action)
        if button is None:
            return
        button.setVisible(visible)
        self.adjustSize()

    def set_plugins(self, infos):
        """
        Set plugin called by ImageView
        """
        if self._plugin_page is not None:
            self._plugin_page.set_plugins(infos)

    def set_plugin_status(
        self,
        plugin_id: str,
        status: PluginStatus,
    ):
        if self._plugin_page is not None:
            self._plugin_page.set_plugin_status(plugin_id, status)

    def set_settings(self, settings):
        self._settings = settings
        for tool, spec in self.tool_specs.items():
            if spec.options is None:
                continue
            self._settings.load_tool_options(tool, spec.options)

    def update_tool_specs(self):
        self.toolSpecChanged.emit(self.tool_specs)

    def sync_options_from_item(self, item):

        data = item.data(ANNOTATION_DATA)
        if data is None:
            return
        tool = data.tool
        spec = self.tool_specs.get(tool)
        if spec is None or spec.options is None:
            return
        options = spec.options
        # print("sync_options_from_item called", options)
        # ==================================================
        # Text
        # ==================================================
        if isinstance(item, EditableTextItem):
            return
            font = item.font()
            if hasattr(options, "font_size"):
                options.font_size = font.pointSizeF()

        # ==================================================
        # Node
        # ==================================================
        elif isinstance(item, CustomNode):
            return
            if hasattr(options, "size"):
                options.size = item.size()
                print(item.size())

        # ==================================================
        # Pen / Line / Arrow / Shape
        # ==================================================
        elif hasattr(item, "pen"):
            pen = item.pen()

            if hasattr(options, "width"):
                options.width = pen.widthF()

        # ==================================================
        # Refresh the visible options page
        # ==================================================
        if spec.options_page is not None:
            spec.options_page.set_options(options)

        # ==================================================
        # Persist
        # ==================================================
        if self._settings is not None:
            self._save_tool_options(tool)

        # # Let ImageView regenerate dynamic cursor
        # self.optionsChanged.emit()

    # ========================================================
    # UI
    # ========================================================
    def _build_ui(self):
        self.setObjectName("FloatingToolbar")
        root = QVBoxLayout(self)
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(1)
        # ----------------------------------------------------
        # First row
        # ----------------------------------------------------
        row1 = QHBoxLayout()
        # row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(1)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(False)
        self.tool_layout = QHBoxLayout()
        self.tool_layout.setSpacing(1)

        self.options_stack = QStackedWidget(self)
        self.options_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

        self.tool_buttons = {}
        self.button_tools = {}
        self.action_buttons = {}
        for tool, spec in self.tool_specs.items():
            if tool in self.hidden_tools:
                continue
            button = self._tool_button(spec.icon, spec.name)
            # button.clicked.connect(lambda _, t=tool: self.set_tool(t))
            self.tool_group.addButton(button, int(tool))
            self.tool_buttons[tool] = button
            self.button_tools[button] = tool  # for set_tool.
            self.tool_layout.addWidget(button)
            self.options_stack.addWidget(spec.options_page)
        self.tool_group.buttonClicked.connect(self._on_tool_button_clicked)

        self.options_stack.adjustSize()
        row1.addLayout(self.tool_layout)

        # ----------------------------------------------------
        # Spare / extension position
        # ----------------------------------------------------
        # self.user_tool_layout = QHBoxLayout()
        # self.user_tool_layout.setSpacing(3)
        # row1.addLayout(self.user_tool_layout)
        # self.btn_add_tool = self._button("+", "Add custom tool")
        # self.btn_add_tool.setObjectName("AddToolButton")
        # row1.addWidget(self.btn_add_tool)

        # ----------------------------------------------------
        # Commands
        # ----------------------------------------------------
        row1.addSpacing(2)
        row1.addWidget(_make_separator())
        row1.addSpacing(2)

        his_btns = [
            (
                AppIcon.icon("undo"),
                "Undo",
                lambda: self.actionRequested.emit(ToolAction.UNDO),
            ),
            (
                AppIcon.icon("redo"),
                "Redo",
                lambda: self.actionRequested.emit(ToolAction.REDO),
            ),
        ]
        for icon, tooltip, callback in his_btns:
            button = self._button(icon, tooltip)
            button.clicked.connect(callback)
            row1.addWidget(button)

        row1.addSpacing(2)
        row1.addWidget(_make_separator())
        row1.addSpacing(2)

        action_btns = {
            ToolAction.CLOSE: ("close2", "Close"),
            ToolAction.PIN: ("pin", "Pin"),
            ToolAction.SAVE: ("save", "Save"),
            ToolAction.COPY: ("copy", "Copy"),
        }

        for tool_action, (icon_name, tooltip) in action_btns.items():
            button = self._button(AppIcon.icon(icon_name), tooltip)
            button.clicked.connect(partial(self.actionRequested.emit, tool_action))
            self.action_buttons[tool_action] = button
            row1.addWidget(button)

        root.addLayout(row1)
        # ----------------------------------------------------
        # Second row: options
        # ----------------------------------------------------
        root.addWidget(self.options_stack)

        # ----------------------------------------------------
        # Stylea
        # ----------------------------------------------------
        self.setStyleSheet("""
            QFrame#FloatingToolbar {
                background: rgba(250, 250, 250, 245);
                border: 1px solid #c8c8c8;
                border-radius: 8px;
            }
            QToolButton {
                background: transparent;
                min-width: 24px; min-height: 24px;
                border: none; border-radius: 6px;
                color: #303030;
                font-size: 16px;
            }
            QToolButton:hover {
                background: rgba(0, 120, 255, 45);
            }
            QToolButton:checked {
                background: rgba(0, 120, 255, 150); /*#dcecff;*/
                color: #0067c0;
            }
            QToolButton:checked:hover {
                background-color: rgba(0, 120, 255, 220);
            }
            QToolButton#AddToolButton {
                color: #777;
                border: 1px dashed #aaa;
            }
            QStackedWidget {
                border-top: 1px solid #e0e0e0;
                background: transparent;
            }
            QStackedWidget > QWidget {
                padding: 0px 0px; /* 上下 4px, 左右 8px */
            }
            """)

    # ========================================================
    # Buttons
    # ========================================================
    def _button(self, icon: QIcon, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon)
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.setFixedSize(24, 24)
        return button

    def _tool_button(self, icon: QIcon, tooltip) -> QToolButton:
        button = self._button(icon, tooltip)
        button.setCheckable(True)
        return button

    # ========================================================
    # Connections
    # ========================================================
    def _connect_ui(self):
        for tool, spec in self.tool_specs.items():
            if spec.options_page is not None:
                spec.options_page.optionsChanged.connect(self._options_changed)

        # For plugin
        spec = self.tool_specs.get(Tool.PLUGIN)
        if spec is not None and spec.options_page is not None:
            spec.options_page.pluginSelected.connect(self.pluginSelected)

        # For user tool
        # self.btn_add_tool.clicked.connect(self.addToolRequested.emit)

    # ========================================================
    # Tool switching
    # ========================================================

    def _on_tool_button_clicked(self, button):
        tool = self.button_tools[button]
        # ----------------------------------
        # Click active tool -> SELECT
        # ----------------------------------
        if tool == self.tool_state.tool:
            self.set_tool(Tool.SELECT)
            return
        self.set_tool(tool)

    def set_tool(self, tool: Tool, **kwargs):
        spec = self.tool_specs[tool]
        # ----------------------------------
        # Update tool buttons
        # ----------------------------------
        for button_tool, button in self.tool_buttons.items():
            button.setChecked(button_tool == tool)

        self.tool_state = ToolState(
            tool=tool,
            options=spec.options,
            **kwargs,
        )
        self._current_tool = tool  # for internal fast lookup.
        self.update_options_page()
        self.toolStateChanged.emit(self.tool_state)

    def update_options_page(self):
        tool = self.tool_state.tool
        spec = self.tool_specs[tool]

        if spec.options_page is None:  # or tool == Tool.SELECT:
            self.options_stack.setVisible(False)
            return
        self.options_stack.setVisible(True)

        self.options_stack.setCurrentWidget(spec.options_page)
        spec.options_page.set_options(spec.options)

    def current_tool(self):
        if not self.tool_state:
            return None
        return self.tool_state.tool

    # ========================================================
    # Property changed
    # ========================================================
    def _options_changed(self):
        spec = self.tool_specs[self.tool_state.tool]
        if spec.options is None:
            return
        self.toolStateChanged.emit(self.tool_state)
        self._save_tool_options(self.current_tool())

    def update_option(self, tool, name, value):
        spec = self.tool_specs[tool]
        if spec.options is None:
            return
        setattr(spec.options, name, value)
        if self.tool_state.tool == tool:
            self.tool_state_changed.emit(self.tool_state)

    def _save_tool_options(self, tool: Tool):
        """
        Save to settings.
        """
        if self._settings is None:
            return
        spec = self.tool_specs[tool]
        if spec is None:
            return
        self._settings.save_tool_options(tool, spec.options)

    # ========================================================
    # User/custom tools
    # ========================================================
    def add_user_tool(self, tool_id: int, text: str, tooltip: str, options=None):
        """
        Example:
            toolbar.add_user_tool(
                100,
                "★",
                "Highlight",
                HighlightOptions())
        """
        if tool_id < Tool.USER_BASE:
            raise ValueError(f"User tool id must be >= {Tool.USER_BASE}")
        if tool_id in self._user_tools:
            raise ValueError(f"Tool id {tool_id} already exists")
        button = self._tool_button(QIcon(), tooltip)
        self.tool_group.addButton(button, tool_id)
        self.user_tool_layout.addWidget(button)
        self._user_tools[tool_id] = {
            "button": button,
            "options": options,
        }
        return button

    # ========================================================
    # External state
    # ========================================================
    def showEvent(self, event):
        """
        Reset node next number in tool_specs.
        Share the same object with scene, dont need emit.
        """
        if self.tool_specs:
            node_handler = self.tool_specs[Tool.NODE].handler
            node_handler.reset_next_number()  # scene also change.

        return super().showEvent(event)

    def set_history_state(self, can_undo, can_redo):
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)

    def keyPressEvent(self, event):
        # ==================================================
        # ESC -> return to SELECT tool
        # ==================================================
        if event.key() == Qt.Key.Key_Escape and self._current_tool != Tool.SELECT:
            self.set_tool(Tool.SELECT)
            event.accept()
            return
        # Acceptable with toolbar -> view.
        if self.parent():
            self.parent().keyPressEvent(event)
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if event.size() != event.oldSize():
            self.resized.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)  # 開啟消除鋸齒
        painter.setBrush(QBrush(QColor(245, 245, 245, 245)))
        painter.setPen(QPen(QColor(180, 180, 180, 220), 1))
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(rect, 10.0, 10.0)
        painter.end()

        super().paintEvent(event)
