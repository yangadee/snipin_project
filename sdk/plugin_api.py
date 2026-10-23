from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QSystemTrayIcon
from PyQt6.QtGui import QPixmap
from .models import PluginRecord
from uuid import uuid4


class PluginAPI(QObject):
    """
    Simple API wrapper around AppController.

    PluginAPI can access controller internally,
    but plugins only see selected public API.
    """

    def __init__(self, controller):
        self._controller = controller

    # -----------------------------
    # Dynamic controller variables
    # -----------------------------
    @property
    def icons(self):
        return self._controller.icon_provider

    @property
    def overlays(self):
        return self._controller.overlays

    @property
    def viewers(self):
        return self._controller.viewers

    @property
    def ocr_service(self):
        return self._controller.ocr_service

    @property
    def current_session(self):
        return self._controller.session

    @property
    def plugins(self) -> dict[str, PluginRecord]:
        return self._controller.plugin_manager.plugins

    # @property
    # def hotkeys(self):
    #     return self._controller.hotkey_manager.hotkeys

    # -----------------------------
    # Safe helper methods
    # -----------------------------
    def register_pin_editor(self, viewer):
        self._controller.register_pin_editor(viewer)

    def recognize_pixmap(self, pixmap, callback):
        if self._controller.ocr is None:
            callback("", "OCR engine is not available")
            return
        print("recognize_pixmap was called")
        return self._controller.ocr.recognize_pixmap(pixmap, callback=callback)

    def recognize_image(self, image, callback):
        """
        support both Qimage and Qpixmap
        """
        if self._controller.ocr is None:
            callback("", "OCR engine is not available")
            return
        return self._controller.ocr.recognize_image(image, callback=callback)

    def create_pin_from_pixmap(self, pixmap: QPixmap, pos: any = None):
        return self._controller.snipin_manager.create_pin_from_pixmap(
            pixmap=pixmap, pos=pos
        )

    def viewer_request_plugin(self, viewer, plugin_id):
        self._controller.on_viewer_request_plugin(viewer, plugin_id)

    def register_hotkey(self, hotkey_id, hotkey_seq, owner, callback):
        """
        register_hotkey API
        Returns HotkeySpec on success, None on failure.
        args:
            hotkey_id=str,
            hotkey_seq=str,
            ownwer=str,
            callback=callable,
        return:
            spec if success
            None if failed.
        """
        return self._controller.hotkey_manager.register_hotkey(
            hotkey_id, hotkey_seq, owner, callback
        )

    def unregister_hotkey(self, hotkey_str: str) -> bool:
        return self._controller.hotkey_manager.unregister_hotkey(hotkey_str)

    def unregister_hotkey_id(self, hotkey_id: str) -> bool:
        return self._controller.hotkey_manager.unregister_hotkey_id(hotkey_id)

    def show_notification(
        self,
        title: str = "",
        message: str = "",
        icon_type=QSystemTrayIcon.MessageIcon.Information,
    ):
        self._controller.show_notification(title, message, icon_type)
