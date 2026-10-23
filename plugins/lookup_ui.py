# nuitka-project: --module
# nuitka-project: --output-dir=.\plugins
## nuitka-project: --no-pyi-file
# nuitka-project: --remove-output
# nuitka-project: --jobs=32

## nuitka-project: --include-module=core.plugins_core.plugin_base

## nuitka-project: --include-module=core.plugins_core.findit_worker

# usage: "python -m nuitka plugins/ocr_findit.py" from "MAIN DIR"

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import QApplication

from sdk.models import PluginContext, PluginStatus
from sdk.plugin_base import PluginBase
from plugins.shared.helpers import preprocess_ocr_text, send_ctrl_c
from plugins.shared.widgets import FinditSAPUI

import ctypes

from PyQt6.QtCore import QTimer

user32 = ctypes.WinDLL("user32", use_last_error=True)

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_ALT = 0x12

VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LALT = 0xA4
VK_RALT = 0xA5

MODIFIER_KEYS = (
    VK_LSHIFT,
    VK_RSHIFT,
    VK_LCONTROL,
    VK_RCONTROL,
    VK_LALT,
    VK_RALT,
)
KEYEVENTF_KEYUP = 0x0002


def is_key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def get_modifiers_down() -> tuple[int, ...]:
    return tuple(vk for vk in MODIFIER_KEYS if is_key_down(vk))


class LookupUI(PluginBase):
    NAME = "FindIt & SAP lookup"
    DESCRIPTION = "Scan image, extract text, and search via UI"
    ICON = "search"
    VERSION = "1.3.2"
    DEFAULT_HOTKEY = "Ctrl+W"
    CAPABILITIES = {"image", "tray", "hotkey"}

    def initialize(self, api):
        self.api = api
        self.viewer_pos = QPoint()
        self.clipboard = QApplication.clipboard()
        self.popup_ui = FinditSAPUI()
        self._callback = None
        self._view = None

        # In __init__:
        self._clipboard_timeout = QTimer()
        self._clipboard_timeout.setSingleShot(True)
        self._clipboard_timeout.timeout.connect(self.stop_clipboard_wait)
        self._last_text = None
        self.clipboard.dataChanged.connect(self.clipboard_ready_callback)
        self._waiting_clipboard = False

    def run(
        self,
        context: PluginContext | None = None,
        *args,
        **kwargs,
    ):
        # Called by tray or hotkey
        if context is None:
            # hwnd = user32.GetForegroundWindow()
            # if hwnd:
            #     user32.SetForegroundWindow(hwnd)
            #     user32.SetFocus(hwnd)
            modifiers_down = self.get_down_modifiers()
            self.force_release_modifiers(modifiers_down)
            self.wait_for_clipboard_text()
            return

        if context.source.lower() == "tray":
            self.show_popup()
            # self.popup_ui.show()
            return
        # Call by viewer.
        callback = context.callback
        self._view = context.view

        try:
            if callable(callback):
                self._callback = callback
                self._callback(PluginStatus.RUNNING)

            image = context.copy_image()
            if image.isNull():
                # context.show_status("No image available")
                if self._callback:
                    self._callback(PluginStatus.CANCELLED)
                return
            self.api.ocr_service.recognize_image(image, self.ocr_ready_callback)

        except Exception:
            if self._callback:
                self._callback(PluginStatus.ERROR)
            raise

    @staticmethod
    def get_down_modifiers():
        """Return list of currently pressed modifier virtual keys"""
        down = []
        for vk in MODIFIER_KEYS:
            if user32.GetAsyncKeyState(vk) & 0x8000:
                down.append(vk)
        return down

    @staticmethod
    def force_release_modifiers(modifiers=None):
        """Force release the given modifiers (or all if None)"""
        if modifiers is None:
            modifiers = MODIFIER_KEYS
        for vk in modifiers:
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def wait_for_clipboard_text(self):
        self._waiting_clipboard = True
        # self._last_text = self.clipboard.text()
        QTimer.singleShot(100, send_ctrl_c)
        self._clipboard_timeout.start(1000)

    def stop_clipboard_wait(self):
        self._clipboard_timeout.stop()
        self._waiting_clipboard = False
        if not self.popup_ui.isVisible():
            self.show_popup("", QCursor.pos())

    def clipboard_ready_callback(self):
        if not self._waiting_clipboard:
            return
        text = self.clipboard.text().strip()
        if not text:
            return
        self._last_text = text
        self._waiting_clipboard = False
        self.show_popup(text, QCursor.pos())

    def ocr_ready_callback(self, ocr_text, *_):
        if not ocr_text:
            if self._callback:
                self._callback(PluginStatus.CANCELLED)
            return
        corrected_ocr_text = preprocess_ocr_text(ocr_text)
        self.show_popup(corrected_ocr_text, QCursor.pos())
        if self._callback:
            self._callback(PluginStatus.FINISHED)
        self._view.close_self()

    def show_popup(self, text="", global_pos=None):
        if not self.popup_ui:
            return
        if text:
            self.popup_ui.set_query(text)

        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        rect = screen.availableGeometry()
        # Center popup on this screen
        x = rect.center().x() - self.popup_ui.width() // 2
        y = rect.center().y() - self.popup_ui.height() // 2

        # if global_pos is None:
        #     cursor_pos = QCursor.pos()
        #     screen = (
        #         QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        #     )
        #     rect = screen.availableGeometry()
        #     # Center popup on this screen
        #     x = rect.center().x() - self.popup_ui.width() // 2
        #     y = rect.center().y() - self.popup_ui.height() // 2
        # else:
        #     screen = (
        #         QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        #     )
        #     rect = screen.availableGeometry()
        #     # Start at requested global position
        #     x = global_pos.x()
        #     y = global_pos.y()
        #     # Keep entire popup inside that screen
        #     x = min(max(x, rect.left()), rect.right() - self.popup_ui.width() + 1)
        #     y = min(max(y, rect.top()), rect.bottom() - self.popup_ui.height() + 1)

        self.popup_ui.move(x, y)
        self.popup_ui.show()
        self.popup_ui.activateWindow()
        self.popup_ui.setFocus()

    def cleanup(self):
        if self.popup_ui:
            self.popup_ui.shutdown()
        return super().cleanup()
