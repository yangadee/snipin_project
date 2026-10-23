import os
import re
import math

from PyQt6.QtWidgets import QSystemTrayIcon, QApplication
from PyQt6.QtCore import QRect, QSignalBlocker, QObject, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QPixmap, QPainter, QTextDocument

from sdk.models import PluginCapability
from sdk.plugin_api import PluginAPI
from core.snipin_manager import SnipPinManager
from core.app_info import AppInfo
from core.models import AppContext
from core.capture_cursor_screen import capture_fullscreen_under_cursor

from ui.settings_dialog import SettingsDialog
from ui.widgets import TrayMenu
from utils.system_helper import reload_script
from utils.auto_startup import set_run_on_startup
from utils.setup_logging import set_log_level


from resources.icon_provider import icon_provider
from .settings_manager import SettingsManager
from .hotkey_manager import Win32HotkeyManager
from .plugin_manager import PluginManager
from rapidocr import OcrService

from collections import deque

import logging

logger = logging.getLogger(__name__)


# ============================================================
# HOTKEY BRIDGE
# ============================================================
class HotkeyBridge(QObject):
    area_screenshot_requested = pyqtSignal()
    full_screenshot_requested = pyqtSignal()
    pin_clipboard_requested = pyqtSignal()
    reload_plugins_requested = pyqtSignal()
    restore_last_pin_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    hotkey_requested = pyqtSignal(str)


# ============================================================
# APP CONTROLLER
# ============================================================s


class SnipAppController(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        logger.debug("Snipin Initializing....")
        self.app = QApplication.instance()

        self.app.setStyleSheet(  # type: ignore
            "QToolTip { color: #ffffff; background-color: #2a2a2a; border: 1px solid white; }"
        )  # Set global dark-themed style for all tooltips

        # =============================================
        # Variable for overlay / Pinviewer
        # =============================================
        self.overlay = None
        self.viewers = []
        self.current_viewer = None
        # store interested image (copy/pin/saved)
        self.closed_pin_image_queue = deque(maxlen=10)

        # =============================================
        # Plugin API
        # =============================================
        self.plugin_api = PluginAPI(self)
        self.plugin_manager = PluginManager(api=self.plugin_api)

        # =============================================
        # HOTKEYS
        # =============================================
        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.hotkey_requested.connect(self._handle_hotkey)
        self.hotkey_manager = Win32HotkeyManager()
        self._hotkey_suspended = False
        self._hotkey_enabled = True
        self._hotkeys_enabled_before_settings = None
        self._hotkeys_suspended_before_settings = None

        # initial
        self.settings_dialog = None

        self.plugins_init()
        self.settings_config_init()
        self.ocr_service_init()
        self.tray_menu_init()

        # Initialize for API.
        self.icon_provider = icon_provider
        self.clipboard = QApplication.clipboard()  # warm up Qclipboard obj (singleton)

        # Apply configs
        self.hotkey_configs = {}
        self.general_settings = {}
        self.plugins_settings = {}

        self.apply_settings_from_manager()

        # --------------------------------
        # Shared application context
        # --------------------------------
        self.context = AppContext(
            plugins=self.plugin_manager,
            hotkeys=self.hotkey_manager,
            settings=self.settings_manager,
        )
        # =============================================
        # SNIP & PIN MANAGER
        # =============================================

        self.snipin_manager = SnipPinManager(self.context)

        # ======================================================
        # Screen changed detection
        # ======================================================
        app.screenAdded.connect(self.on_screen_added)
        app.screenRemoved.connect(self.on_screen_change)

        for screen in QApplication.screens():
            screen.geometryChanged.connect(self.on_screen_change)

        if self.tray:
            self.tray.show_notification(
                f"{AppInfo.NAME} {AppInfo.VERSION}",
                "Tool is running successfully in the background.",
            )

    # ======================================================
    # Screen changed detection
    # ======================================================
    def on_screen_added(self, screen):
        screen.geometryChanged.connect(self.on_screen_change)
        self.on_screen_change()

    def on_screen_change(self, *_):
        """
        Callback for screen layout (add, remove,...) or geometry changes.
        """
        self._last_saved_selection = QRect()
        self.snipin_manager.reset_grab_view()

    def settings_config_init(self):
        # ========================================================
        # Settings Manager
        # ========================================================
        self.settings_manager = SettingsManager()
        self._create_settings_dialog()

    def _create_settings_dialog(self):
        """
        Pre-create settings dialog with force WinId hwnd.
        """
        self.settings_dialog = SettingsDialog(
            settings_manager=self.settings_manager,
            controller=self,
            general_data=self.settings_manager.get_general(),
            hotkeys_data=self.hotkey_manager.hotkeys,
            plugins_data=self.plugin_manager.plugins,
        )
        self._connect_settings_dialog()
        self.settings_dialog.grab()  # return pixmap for warming dialog.
        self.settings_dialog.winId()  # Force get winId.
        self.settings_dialog.hide()

    def _connect_settings_dialog(self):
        dialog = self.settings_dialog
        dialog.settings_changed.connect(self.apply_settings_from_manager)
        dialog.hotkeys_enabled_requested.connect(self.set_global_hotkeys_enabled)
        dialog.finished.connect(self._on_settings_closed)

        # Hotkeys
        dialog.hotkeys_tab.key_bindings_requested.connect(
            lambda: self.set_global_hotkeys_enabled(False)
        )
        dialog.hotkeys_tab.set_hotkey_tester(self.is_hotkey_available)
        # Plugins
        # dialog.plugins_tab.plugin_enabled_changed.connect(self.on_plugin_enabled_changed)
        dialog.plugins_tab.reload_requested.connect(self.reload_plugins)

    def show_settings(self):
        # Already open -> just bring it forward
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        self._hotkeys_enabled_before_settings = self._hotkey_enabled
        self._hotkeys_suspended_before_settings = self._hotkey_suspended

        if self.settings_dialog is None:
            self._create_settings_dialog()
        else:
            self.settings_dialog.refresh_data(
                general_data=self.settings_manager.get_general(),
                hotkeys_data=self.hotkey_manager.hotkeys,
                plugins_data=self.plugin_manager.plugins,  # dynamics
            )
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _on_settings_closed(self, result):
        # Restore exact previous states
        if self._hotkeys_enabled_before_settings:
            self.set_global_hotkeys_enabled(True)
        else:
            self.set_global_hotkeys_enabled(False)

        # self.set_hotkeys_suspended(self._hotkeys_suspended_before_settings)

        # Clear snapshots afterward
        self._hotkeys_enabled_before_settings = None
        self._hotkeys_suspended_before_settings = None

    def tray_menu_init(self):
        """Tray Menu setup"""
        self.tray = TrayMenu(self)
        self.tray.snapshot_requested.connect(self.capture_area)
        self.tray.close_pins_requested.connect(self.close_all_pins)
        self.tray.hotkeys_enabled_changed.connect(self.set_global_hotkeys_enabled)
        self.tray.hotkeys_suspended_changed.connect(self.set_hotkeys_suspended)
        # self.tray.settings_dialog_requested.connect(self.settings_dialog.exec)
        self.tray.settings_dialog_requested.connect(self.show_settings)
        self.tray.exit_requested.connect(self.exit_app)
        self.tray.pluginSelected.connect(self.plugin_manager.execute_plugin)
        self.tray.hotkeys_suspended_action.setChecked(self._hotkey_suspended)
        self.tray.hotkeys_enabled_action.setChecked(self._hotkey_enabled)

        infos = self.plugin_manager.plugin_infos_for(PluginCapability.TRAY)
        self.tray.set_plugin_actions(infos=infos)
        self.tray.show()

    def ocr_service_init(self):
        """For OCR service init"""
        self.ocr_service = OcrService()
        self.ocr_service.initialized.connect(
            lambda: logger.debug("[OCR] OCR Engine initialized successfully!")
        )
        self.ocr_service.failed.connect(lambda: logger.error("OCR initial failed"))

    def plugins_init(self):
        """Builtin and Dynamic plugins init"""
        # # Load builtin plugins -> nuitka will compile it.
        # for cls in BUILTIN_PLUGIN_CLASSES:
        #     self.plugin_manager.register_plugin(cls)

        # Load dynamic plugins -> nuitka won't compile
        self.plugin_manager.load_dynamic_plugins("plugins")
        logger.info(
            "[Plugins] %s plugin(s) are loaded!", len(self.plugin_manager.plugins)
        )

    # End init

    # ========================================================
    # HELPER / CALLBACKS from External (API)
    # ========================================================
    def apply_hotkeys_suspended(self, suspended: bool) -> None:
        self.hotkey_manager.set_hotkeys_suspended(suspended)
        self._hotkey_suspended = suspended

    def register_core_hotkeys(self):
        """
        Register for new hotkeys and update if hotkeys exist.
        """
        for hotkey_id, config in self.hotkey_configs.items():
            if hotkey_id in self.hotkey_manager.hotkeys:
                self.hotkey_manager.update_hotkey(
                    hotkey_id=hotkey_id,
                    hotkey_seq=config["sequence"],
                )
            else:
                self.hotkey_manager.register_hotkey(
                    hotkey_id=hotkey_id,
                    hotkey_seq=config["sequence"],
                    owner="core",
                    callback=config["callback"],
                )

    def unregister_core_hotkeys(self):
        try:
            self.hotkey_manager.unregister_hotkey_owner("core")
        except Exception as e:
            logger.error("Failed to stop hotkeys: %s", str(e)[:100])
        self.hotkey_suspended = False

    def is_hotkey_available(self, hotkey_sq):
        """
        wrapper funciton for is_hotkey_available()
        """
        return self.hotkey_manager.is_hotkey_available(hotkey_sq)

    # ========================================================
    #
    # ========================================================
    def screen_center_pos_for_pixmap(self, pixmap):
        screen = QApplication.primaryScreen()
        if screen is None:
            return QPoint(100, 100)
        screen_rect = screen.availableGeometry()
        pixmap_size = pixmap.deviceIndependentSize().toSize()
        x = screen_rect.x() + (screen_rect.width() - pixmap_size.width()) // 2
        y = screen_rect.y() + (screen_rect.height() - pixmap_size.height()) // 2
        return QPoint(x, y)

    def _convert_clipboard_to_pixmap_(self, mime_data) -> QPixmap:
        if mime_data.hasHtml():
            text_content = mime_data.html()
        elif mime_data.hasText():
            text_content = mime_data.text()
        else:
            print("No text data")
            return QPixmap()
        # 2.
        doc = QTextDocument()
        doc.setDefaultStyleSheet("body, p, div { white-space: pre-wrap; }")
        if mime_data.hasHtml():
            html_text = mime_data.html()
            html_text = html_text.replace("\r\n", "<br>").replace("\n", "<br>")
            doc.setHtml(html_text)
        elif mime_data.hasText():
            raw_text = mime_data.text()
            html_ready_text = raw_text.replace("\r\n", "<br>").replace("\n", "<br>")
            doc.setHtml(html_ready_text)
        else:
            return QPixmap()
        # 3.
        size = doc.size().toSize()
        pixmap = QPixmap(size)
        pixmap.fill(QApplication.palette().window().color())
        # 4.
        painter = QPainter(pixmap)
        doc.drawContents(painter)
        painter.end()
        return pixmap

    def convert_clipboard_to_pixmap(
        self,
        mime_data,
        max_width: int = 1000,
    ) -> QPixmap | None:

        if not mime_data.hasHtml() and not mime_data.hasText():
            logger.info("Neither mime Html nor mime Text data")
            return None
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        if mime_data.hasHtml():
            html_text = mime_data.html()

            # QTextDocument may not paint a standalone <br> line using
            # the parent block's inherited background.
            #
            # Convert only standalone <br> tags into an actual block,
            # without searching for or hardcoding any background color.
            html_text = re.sub(
                r"(?i)<br\s*/?>",
                "<div><br></div>",
                html_text,
            )
            doc.setHtml(html_text)
        else:
            doc.setPlainText(mime_data.text())
        doc.adjustSize()
        if doc.size().width() > max_width:
            doc.setTextWidth(max_width)
        doc_size = doc.size()
        width = max(1, math.ceil(doc_size.width()))
        height = max(1, math.ceil(doc_size.height()))
        pixmap = QPixmap(QSize(width, height))
        if pixmap.isNull():
            logger.error("Failed to create pixmap: %s x %s", width, height)
            return None
        pixmap.fill(QApplication.palette().window().color())
        painter = QPainter(pixmap)
        if not painter.isActive():
            logger.error("Failed to activate QPainter")
            return None
        doc.drawContents(painter)
        painter.end()
        return pixmap

    # ========================================================
    # IMPLEMENTS FUNCS / HOTKEYS CALLBACKS
    # ========================================================
    def _handle_hotkey(self, hotkey_id: str):
        callback = getattr(self, hotkey_id, None)
        if callable(callback):
            callback()
        else:
            logger.warning("Callback method not found for core hotkey '%s'.", hotkey_id)

    def restore_pin(self):
        self.snipin_manager.reopen_last_closed_pin()
        return

    def capture_fullscreen(self):
        pixmap, pos = capture_fullscreen_under_cursor()

        if pixmap.isNull():
            return
        self.snipin_manager.create_pin_from_pixmap(pixmap, pos=None)

    def pin_clipboard(self):
        mime_data = self.clipboard.mimeData()
        pixmap = QPixmap()
        # ====================================================
        # CASE 1: Clipboard has image data
        # ====================================================
        if mime_data.hasImage():
            clip_pixmap = self.clipboard.pixmap()
            if not clip_pixmap.isNull():
                pixmap = clip_pixmap

        # ====================================================
        # CASE 2: Clipboard has file URL(s)
        # Example: copy image file from Explorer
        # ====================================================
        if pixmap.isNull() and mime_data.hasUrls():
            for url in mime_data.urls():
                if not url.isLocalFile():
                    continue
                file_path = url.toLocalFile()
                if not os.path.isfile(file_path):
                    continue
                candidate = QPixmap(file_path)
                if not candidate.isNull():
                    pixmap = candidate
                    break

        # ====================================================
        # CASE 3: Clipboard text is text
        # "Pixmap is null but clipboard contains text data. Retrying/Falling back..."
        # ====================================================
        if pixmap.isNull() and (mime_data.hasText() or mime_data.hasHtml()):
            pixmap = self.convert_clipboard_to_pixmap(mime_data)

        # ====================================================
        # NO VALID IMAGE
        # ====================================================
        if pixmap.isNull():
            if self.tray:
                self.tray.show_notification(
                    "No Image in Clipboard",
                    "Clipboard does not contain an image.",
                    QSystemTrayIcon.MessageIcon.Warning,
                )
            return
        # CREATE PIN by snip pin manager.
        self.snipin_manager.create_pin_from_pixmap(pixmap)

    def capture_area(self):
        # logger.info("==========Starting new area snipshot==========")
        self.snipin_manager.start_snip()

    def close_all_pins(self):
        self.snipin_manager.close_all_pins()

    def _refresh_plugin_ui(self) -> None:
        self.settings_dialog.refresh_data(
            general_data=self.settings_manager.get_general(),
            hotkeys_data=self.hotkey_manager.hotkeys,
            plugins_data=self.plugin_manager.plugins,
        )
        self.tray.set_plugin_actions(
            self.plugin_manager.plugin_infos_for(PluginCapability.TRAY)
        )
        self.snipin_manager.set_toolbar_plugins()

    def reload_plugins(self):
        plugins = self.plugin_manager.plugins.copy()  # cached before remove.
        # ----------------------------------------------
        # Unload Plugin
        # ----------------------------------------------
        for plugin_id, _ in plugins.items():
            try:
                success = self.plugin_manager.unload_plugin(plugin_id)
                if success is False:
                    logger.error(f"Unregister plugin {plugin_id} failed.")
            except Exception as e:
                logger.error(f"unregister plugin {plugin_id} failed: {str(e)[:100]}")
        # ----------------------------------------------
        # Dynamic load plugins
        # ----------------------------------------------
        try:
            self.plugin_manager.load_dynamic_plugins("plugins")
        except Exception:
            logger.error(f"Failed during Loading plugins!")
            self._refresh_plugin_ui()
            self.tray.show_notification(
                "Reload Plugins",
                f"Unload plugin(s) failed",
                QSystemTrayIcon.MessageIcon.Warning,
            )
            return False
        logger.info(
            "[Plugins] %s plugin(s) are loaded!", len(self.plugin_manager.plugins)
        )
        self._refresh_plugin_ui()
        self.tray.show_notification(
            "Reload Plugins",
            f"Load finished, {len(self.plugin_manager.plugins)} plugin(s) loaded!",
        )
        return True

    def reopen_app(self):
        return reload_script()

    # ========================================================
    # CLEANUP
    # ========================================================

    def on_viewer_destroyed(self, viewer):
        if viewer in self.viewers:
            self.viewers.remove(viewer)

    def exit_app(self):
        # Close and clear all viewers
        for viewer in list(self.viewers):
            if hasattr(viewer, "force_real_close"):
                viewer.force_real_close = True
            viewer.close()
        self.viewers.clear()

        # Clear all hotkeys
        if hasattr(self, "hotkeys") and self.hotkey_manager:
            self.hotkey_manager.unregister_all()
            self.hotkey_manager = None

        # Hide system tray icon to avoid ghost icon in Windows
        if hasattr(self, "tray") and self.tray:
            self.tray.shutdown()
            self.tray = None

        self.app.quit()

    # ====================================================
    # APPLY SETTINGS
    # ====================================================
    def apply_settings_from_manager(self):
        self.plugins_settings = self.settings_manager.get_plugins_settings()

        self.apply_general_settings()
        self.apply_hotkeys_settings()

    def apply_general_settings(self):
        self.general_settings = self.settings_manager.get_general()
        run_on_startup = self.general_settings.get("run_on_startup", False)
        # win_mouse_capture_enabled = self.general_settings.get(
        #     "win_mouse_capture_enabled", True
        # )
        log_level = self.general_settings.get("log_level", "Info")
        if log_level:
            set_log_level(log_level)

        succecced = set_run_on_startup(run_on_startup)
        if not succecced:
            logger.error("Enable run on start up failed.")

    def apply_hotkeys_settings(self):
        self.build_hotkey_configs()
        self.register_core_hotkeys()

    def build_hotkey_configs(self):
        """
        Get hotkeys settings from settings manager.
        build hotkey_configs(hotkey_id,hotkey_seq,callback).
        callback name should exact name of hotkey_id.
        """
        core_hotkeys = self.settings_manager.get_hotkeys()
        self.hotkey_configs = {}
        for hotkey_id, hotkey_seq in core_hotkeys.items():
            # callback is to send pyqtsignal
            callback = lambda hotkey_id=hotkey_id: (
                self.hotkey_bridge.hotkey_requested.emit(hotkey_id)
            )
            if not callable(callback):
                logger.warning(
                    "Callback method not found for core hotkey '%s'.", hotkey_id
                )
                continue
            self.hotkey_configs[hotkey_id] = {
                "sequence": hotkey_seq,
                "callback": callback,
            }
        self.tray.set_actions_shortcuts(core_hotkeys)

    ######## END SETTINGS CONFIG

    # ====================================================
    # Tray menu calls
    # ====================================================
    def set_hotkeys_suspended(self, suspended: bool):
        """
        interface between hotkey_manager and tray_menu
        """
        if suspended:
            self.tray.set_tooltip("Snipin Suspended")
        else:
            self.tray.set_tooltip("Snipin Enabled")
        # Synchronize tray checkbox
        blocker = QSignalBlocker(self.tray.hotkeys_suspended_action)
        self.tray.hotkeys_suspended_action.setChecked(suspended)
        self.apply_hotkeys_suspended(suspended)
        self._hotkey_suspended = suspended

    # Enable/Disable GLOBAL hotkeys
    def set_global_hotkeys_enabled(self, enabled: bool = True):
        """ """
        total, succeeded = 0, 0
        for _, spec in self.hotkey_manager.hotkeys.items():
            total += 1
            if enabled:
                if self.hotkey_manager.enable_hotkey_spec(spec=spec):
                    succeeded += 1
            else:
                if self.hotkey_manager.disable_hotkey_spec(spec=spec):
                    succeeded += 1
        QSignalBlocker(self.tray.hotkeys_enabled_action)
        self.tray.hotkeys_enabled_action.setChecked(enabled)
        self._hotkey_enabled = enabled

    # ====================================================
    # API calls
    # ====================================================
    def on_viewer_request_plugin(self, viewer, plugin_id):
        self.plugin_manager.execute_plugin(plugin_id, viewer)

    def shutdown(self):
        """
        Safe shutdown app, connected to app.quit()
        """
        for manager in (self.plugin_manager, self.hotkey_manager, self.snipin_manager):
            shutdown = getattr(manager, "shutdown", None)
            if callable(shutdown):
                shutdown()
        logger.info("Application shut down OK.")
