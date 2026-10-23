"""
             OverlayController
                    |
              active ImageView
               /          \
          GrabView       PinView
             |              |
         GrabScene       PinScene
               \          /
                 ImageScene
AppController
│
├── HotkeyManager
├── PluginManager
│
└── SnipController
     │
     ├── plugin_manager  ───────────────┐
     │                                  │
     ├── GrabView : ImageView           │
     │      └── GrabScene               │
     │                                  │
     └── PinWindow[]                    │
            └── PinView : ImageView     │
                   └── PinScene         │
                                        │
ImageView <─────────────────────────────┘
"""

import logging

logger = logging.getLogger(__name__)
import time
from collections import deque
from dataclasses import dataclass
from PyQt6.QtCore import (
    QByteArray,
    QObject,
    QPoint,
    QRect,
    QTimer,
    pyqtSignal,
    QBuffer,
    QIODevice,
)
from PyQt6.QtGui import QImage, QGuiApplication, QPixmap
from PyQt6.QtWidgets import QApplication
from core.models import AppContext
from .pin_window_pool import PinWindowPool
from core.screen_grabber import DXScreenGrabber
from core.session_monitor import SessionMonitor
from ui.views.scenes import PinScene
from ui.views import GrabView
from ui.views.pin_window import PinWindow  # decouple from views.
from utils.cursor_helper import capture_system_cursor


@dataclass(slots=True)
class ClosedPin:
    image_data: QByteArray
    position: QPoint
    opacity: float = 1.0

    ## Tobe implement.
    # size: QSize
    # zoom: float = 1.0
    # rotation: int = 0
    # flip_h: bool = False
    # flip_v: bool = False

    @property
    def bytes(self) -> int:
        return self.image_data.size()


class SnipPinManager(QObject):
    hotkey_triggered = pyqtSignal()

    def __init__(self, context: AppContext, parent=None):
        super().__init__(parent)
        self.context = context
        self._settings = self.context.settings
        # Create Grabber and Grabview.
        self._grabber = DXScreenGrabber()

        # session monitor for window locks.
        self.session_monitor = SessionMonitor()
        self.session_monitor.unlocked.connect(self.on_session_unlock)

        pixmap, _ = self._grabber.grab_all()  # Warm up grabber
        self._grab_view = GrabView(pixmap=pixmap, context=context)
        self._grab_view.createPinRequested.connect(self._create_pin)

        self._pin_window_pool = PinWindowPool(factory=self._new_pin_window)

        self.closed_pins: deque[ClosedPin] = deque()
        self.max_stored_pins = 10
        self.max_stored_pin_bytes = 200 * 1024 * 1024
        self._closed_pin_bytes = 0

    def start_snip(self) -> None:
        if not self._grab_view:
            return
        if not self._grab_view.isHidden():
            # Capturing...exit.
            return
        pixmap, virtual_rect = self._grabber.grab_all()
        if self._settings.capture_cursor_enabled:
            self.frozen_cursor = capture_system_cursor()
        else:
            self.frozen_cursor = None
        self._grab_view.set_capture(
            pixmap=pixmap,
            virtual_rect=virtual_rect,
            frozen_cursor=self.frozen_cursor,
        )

        # Fix bug: grab view focus lost.
        # Close active popup.
        popup = QApplication.activePopupWidget()
        if popup is not None:
            popup.close()

        # for w in QApplication.topLevelWidgets():
        #     if isinstance(w, FloatingToolbar):
        #         w.hide()
        #         print(w)

        self._grab_view.show()
        self._grab_view.raise_()
        QTimer.singleShot(0, self._grab_view.activateWindow)

    def cancel_snip(self) -> None:
        self._grab_view.hide()
        self._grab_view.reset_selection()

    def get_screen_center_pos(self, rect: QRect):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QPoint(100, 100)
        screen_rect = screen.availableGeometry()
        x = screen_rect.x() + (screen_rect.width() - rect.width()) // 2
        y = screen_rect.y() + (screen_rect.height() - rect.height()) // 2
        return QPoint(x, y)

    def close_all_pins(self):
        self._pin_window_pool.close_all()

    def set_toolbar_plugins(self) -> None:
        self._grab_view.set_toolbar_plugins()

    # ===============================================
    # Traces Callbacks
    # ===============================================
    def on_session_unlock(self):
        """
        On window locked.
        """
        if self._grabber:
            self._grabber.invalidate()

    def reset_grab_view(self):
        """
        API call to set grab_view to None to re-construct.
        And after session unlock.
        """
        if self._grabber:
            self._grabber.invalidate()
        if self._grab_view.isVisible():
            self.cancel_snip()

    def _new_pin_window(self) -> PinWindow:
        """
        create new pin window for window pool factory
        Called only when the pool creates a new window.
        """
        pin = PinWindow(context=self.context)  # Keep existing constructor.
        pin.closed.connect(self._pin_closed)  # saved the closed pin.
        # pin.destroyed.connect(lambda: print(pin, "is destroyed"))
        return pin

    def _create_pin(self, pin_scene, global_pos) -> PinWindow:
        # pin = PinWindow(scene=pin_scene, context=self.context)
        # pin = PinWindow(context=self.context)
        pin = self._pin_window_pool.acquire()
        pin.attach_scene(pin_scene)

        # pin.move(global_pos - QPoint(pin.SHADOW_SIZE, pin.SHADOW_SIZE))
        pin.show()
        pin.move_view_to_global(global_pos)
        pin.raise_()
        pin.show_toolbar()
        QTimer.singleShot(0, pin.activateWindow)

        # logger.info(
        #     "window pool active: %s / idle %s",
        #     self._pin_window_pool.active_count,
        #     self._pin_window_pool.idle_count,
        # )

        return pin

    def _pin_closed(self, pin):
        # ----------------------------------
        # Save closed pin
        # ----------------------------------
        self._store_closed_pin(pin)
        # logger.info(
        #     "window pool active: %s / idle %s",
        #     self._pin_window_pool.active_count,
        #     self._pin_window_pool.idle_count,
        # )

    def create_pin_from_pixmap(self, pixmap, pos=None):
        """
        API function
        Create pin from pixmap and set global position if available.
        """
        if pixmap.isNull():
            return None
        if pos is None:
            # pos = QCursor.pos()
            pos = self.get_screen_center_pos(pixmap.rect())
        pin_scene = PinScene(pixmap)
        return self._create_pin(pin_scene, pos)

    def _store_closed_pin(self, pin):
        view = pin.pin_view
        image = view.render_image()
        if image.isNull():
            return
        data = _image_to_png_data(image)
        if data.isEmpty():
            return
        image_pos = view.viewport().mapToGlobal(QPoint(0, 0))
        record = ClosedPin(
            image_data=data,
            position=QPoint(image_pos),
            opacity=pin.windowOpacity(),
            # zoom=getattr(pin.pin_view, "_zoom", 1.0),
            # rotation=getattr(pin.pin_view, "_rotation", 0),
            # flip_h=getattr(pin.pin_view, "_flip_h", False),
            # flip_v=getattr(pin.pin_view, "_flip_v", False),
        )
        self.closed_pins.append(record)
        self._closed_pin_bytes += record.bytes

        self._trim_closed_pins()
        # print(
        #     f"Closed pins: {len(self.closed_pins)} / size (MB):",
        #     self._closed_pin_bytes / 1_000_000,
        # )

    def _trim_closed_pins(self):
        """
        Ensure the stored size is under control.
        """
        self.max_stored_pins = self._settings.max_stored_pins
        if self.max_stored_pins < 1:
            self.max_stored_pins = 10  # default

        while (
            len(self.closed_pins) > self.max_stored_pins
            or self._closed_pin_bytes > self.max_stored_pin_bytes
        ):
            oldest = self.closed_pins.popleft()
            self._closed_pin_bytes -= oldest.bytes

    def reopen_last_closed_pin(self):
        if not self.closed_pins:
            return
        record = self.closed_pins.pop()
        self._closed_pin_bytes -= record.bytes
        self._repin_record(record)

    def _repin_record(self, record: ClosedPin):
        image = _image_from_png_data(record.image_data)
        if image.isNull():
            return None
        # ----------------------------------
        # Create PinScene
        # ----------------------------------
        pin_scene = PinScene(pixmap=QPixmap.fromImage(image))
        # ----------------------------------
        # Create PinWindow
        # ----------------------------------
        pin = self._create_pin(pin_scene, record.position)
        # ----------------------------------
        # Restore window/view state
        # ----------------------------------
        pin.setWindowOpacity(record.opacity)
        # view = pin.view
        # view._zoom = record.zoom
        # view._rotation = record.rotation
        # view._flip_h = record.flip_h
        # view._flip_v = record.flip_v
        # view._update_view_transform()
        return pin

    def shutdown(self):
        """
        Release all resources owned by SnipPinManager.
        """

        # Release grabber resources.
        if self._grabber is not None:
            self._grabber.close()

        # Close grab overlay.
        if self._grab_view:
            self._grab_view.close()
            self._grab_view = None

        if self.session_monitor:
            self.session_monitor.stop()

        self._pin_window_pool.shutdown()


# =================================================
# Image Encode/decode helpers
# =================================================
def _image_to_png_data(image: QImage) -> QByteArray:
    if image.isNull():
        return QByteArray()
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        return QByteArray()
    try:
        if not image.save(buffer, "PNG"):
            return QByteArray()
    finally:
        buffer.close()
    return data


def _image_from_png_data(data: QByteArray) -> QImage:
    image = QImage()
    if data.isEmpty():
        return image
    image.loadFromData(data, "PNG")
    return image


# if __name__ == "__main__":
#     import sys
#     from PyQt6.QtWidgets import QApplication

#     def main():
#         app = QApplication(sys.argv)
#         app.setQuitOnLastWindowClosed(False)
#         controller = SnipPinManager()
#         # controller.start_capture()

#         sys.exit(app.exec())

#     main()
