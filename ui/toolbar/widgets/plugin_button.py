from PyQt6.QtCore import QRectF, QTimer, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import QStyle, QStyleOptionToolButton, QToolButton

from sdk.models import PluginStatus
from resources import icon_provider


class PluginButton(QToolButton):

    SPIN_INTERVAL_MS = 50
    SPIN_STEP_DEG = 30

    RUNNING_TIMOUT = 10000
    FINISHED_DISPLAY_MS = 2000
    ERROR_DISPLAY_MS = 3000
    CANCELLED_DISPLAY_MS = 1500

    def __init__(
        self,
        plugin_id: str,
        icon: QIcon,
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(parent)

        self.plugin_id = plugin_id

        # --------------------------------------------------------
        # Default state
        # --------------------------------------------------------

        self._default_icon = icon
        self._default_tooltip = tooltip

        self._status = PluginStatus.IDLE

        self.setIcon(self._default_icon)
        self.setToolTip(self._default_tooltip)

        # --------------------------------------------------------
        # Spinner timer
        # --------------------------------------------------------
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(self.SPIN_INTERVAL_MS)
        self._spin_timer.timeout.connect(self._rotate_spinner)

        # --------------------------------------------------------
        # Reset timer
        # --------------------------------------------------------
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self.reset_status)

        self._icons = {
            PluginStatus.RUNNING: QIcon(),
            PluginStatus.FINISHED: QIcon(icon_provider.icon("done")),
            PluginStatus.ERROR: QIcon(icon_provider.icon("failed")),
            PluginStatus.CANCELLED: QIcon(icon_provider.icon("warning")),
        }

    # ============================================================
    # Properties
    # ============================================================

    @property
    def status(self) -> PluginStatus:
        return self._status

    # ============================================================
    # Status
    # ============================================================

    def set_status(self, status: PluginStatus) -> None:
        # Stop anything belonging to previous state
        self._spin_timer.stop()
        self._reset_timer.stop()
        self._status = status
        # --------------------------------------------------------
        # Idle
        # --------------------------------------------------------
        if status == PluginStatus.IDLE:
            self.reset_status()
            return
        # --------------------------------------------------------
        # Running
        # --------------------------------------------------------
        if status == PluginStatus.RUNNING:
            self._spin_angle = 0
            # Hide normal icon because spinner will be painted
            # directly in paintEvent().
            self.setIcon(QIcon())
            self.setToolTip(f"{self._default_tooltip} - Running")
            self._spin_timer.start()
            self._reset_timer.start(self.RUNNING_TIMOUT)
            self.update()
            return
        # --------------------------------------------------------
        # Finished
        # --------------------------------------------------------

        if status == PluginStatus.FINISHED:
            self.setIcon(self._icons[status])
            self.setToolTip(f"{self._default_tooltip} - Finished")
            self._reset_timer.start(self.FINISHED_DISPLAY_MS)
            self.update()
            return

        # --------------------------------------------------------
        # Error
        # --------------------------------------------------------

        if status == PluginStatus.ERROR:
            self.setIcon(self._icons[status])
            self.setToolTip(f"{self._default_tooltip} - Error")
            self._reset_timer.start(self.ERROR_DISPLAY_MS)
            self.update()
            return

        # --------------------------------------------------------
        # Cancelled
        # --------------------------------------------------------

        if status == PluginStatus.CANCELLED:
            self.setIcon(self._icons[status])
            self.setToolTip(f"{self._default_tooltip} - Cancelled")
            self._reset_timer.start(self.CANCELLED_DISPLAY_MS)
            self.update()

    # ============================================================
    # Reset
    # ============================================================

    def reset_status(self) -> None:
        self._spin_timer.stop()
        self._reset_timer.stop()
        self._spin_angle = 0
        self._status = PluginStatus.IDLE
        self.setIcon(self._default_icon)
        self.setToolTip(self._default_tooltip)

    # ============================================================
    # Spinner
    # ============================================================

    def _rotate_spinner(self) -> None:
        self._spin_angle = (self._spin_angle - self.SPIN_STEP_DEG) % 360
        # Trigger repaint only.
        self.update()

    # ============================================================
    # Painting
    # ============================================================
    def mousePressEvent(self, event):
        if self._status == PluginStatus.RUNNING:
            event.accept()
            return

        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        # --------------------------------------------------------
        # Normal button painting
        # --------------------------------------------------------
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        painter = QPainter(self)
        self.style().drawComplexControl(
            QStyle.ComplexControl.CC_ToolButton, option, painter, self
        )
        if self._status != PluginStatus.RUNNING:
            return
        # --------------------------------------------------------
        # Spinner
        # --------------------------------------------------------
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_size = self.iconSize()
        size = min(icon_size.width(), icon_size.height())
        if size <= 0:
            size = 20
        # Slight padding so the pen isn't clipped.
        diameter = size - 4
        x = (self.width() - diameter) / 2
        y = (self.height() - diameter) / 2
        rect = QRectF(x, y, diameter, diameter)
        # pen = QPen(self.palette().color(self.foregroundRole()))
        pen = QPen(QColor("#00AEFF"))
        pen.setWidthF(2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # drawArc uses 1/16 degree units.
        painter.drawArc(rect, self._spin_angle * 16, 270 * 16)
