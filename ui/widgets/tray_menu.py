import ctypes
import logging
from typing import Iterable

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from sdk.models import PluginContext, PluginInfo
from resources.icon_provider import icon_provider as AppIcon
from core.app_info import AppInfo
from ui.widgets.tray_action import TrayAction

user32 = ctypes.windll.user32


class Action(QAction):
    def setText(self, text: str) -> None:
        super().setText(text)
        super().setStatusTip(text)

    # def setStatusTip(self, status_tip: str | None = None) -> None:
    #     # If not explicitly provided, use action text
    #     super().setStatusTip(self.text() if status_tip is None else status_tip)
    def setStatus(self, status: str) -> None:
        self.setText(f"{self.text().split(chr(9))[0]}\t{status}")


class TrayMenu(QObject):
    """
    Manager class for the system tray icon and its context menu.
    Inherits from QObject to bind its lifecycle to the QApplication instance,
    which completely prevents the 'click 1 time and disappear' GC bug.
    """

    snapshot_requested = pyqtSignal()
    close_pins_requested = pyqtSignal()
    # Emits True when registered, False when unregistered
    hotkeys_enabled_changed = pyqtSignal(bool)
    # Emits True when paused/suppressed, False when active
    hotkeys_suspended_changed = pyqtSignal(bool)
    settings_dialog_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    pluginSelected = pyqtSignal(object, object)

    def __init__(self, snip_controller, context=None, parent=None):
        super().__init__(parent)
        app = QApplication.instance()
        if app:
            self.app_icon = app.windowIcon()
        else:  # Fallback: Use standard OS system icon
            self.app_icon = self.tray_icon.style().standardIcon(
                self.tray_icon.style().StandardPixmap.SP_ComputerIcon
            )
        self.snip_controller = snip_controller  # Reference to the central controller
        self.context = context
        self._plugin = self.context.plugins if self.context else None
        self._plugin_actions: list[QAction] = []

        self.tray_icon = QSystemTrayIcon(self)
        if not self.app_icon.isNull():
            self.tray_icon.setIcon(self.app_icon)

        self.tray_icon.setToolTip(f"{AppInfo.NAME} - Version {AppInfo.VERSION}")
        self.create_tray_menu()
        # self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def _create_tray_menu(self):
        """Creates the right-click context menu and keeps references to actions."""
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                padding: 5px; 
            }
            QMenu::separator {
                height: 1px;   
                background-color: #DCDCDC;  
                /* top-bottom left-right ; */
                margin: 3px 10px;
            }
        """)

        # Let controller determine the action's callback
        self.snip_action = TrayAction(
            "Snip screen", "", AppIcon.icon("snip"), self.tray_menu
        )
        self.snip_action.triggered.connect(self.handle_snip_click)
        # self.snip_action.triggered.connect(self.snapshot_requested)

        self.close_pins_action = TrayAction(
            "Close active pins", "", None, self.tray_menu
        )
        self.close_pins_action.triggered.connect(self.close_pins_requested)

        # Emits True when enable(registered), False when disable(un-register)
        self.hotkeys_enabled_action = TrayAction(
            "Enable hotkeys", "", None, self.tray_menu
        )
        self.hotkeys_enabled_action.setCheckable(True)
        self.hotkeys_enabled_action.toggled.connect(self.hotkeys_enabled_changed)

        # Emits True when paused/suppressed, False when active
        self.hotkeys_suspended_action = TrayAction(
            "Suspend hotkeys", "", None, self.tray_menu
        )
        self.hotkeys_suspended_action.setCheckable(True)
        self.hotkeys_suspended_action.toggled.connect(self.hotkeys_suspended_changed)

        settings_action = TrayAction(
            "Preference", "", AppIcon.icon("settings"), self.tray_menu
        )
        settings_action.triggered.connect(self.settings_dialog_requested)

        # About
        about_action = TrayAction("About", "", AppIcon.icon("about"), self.tray_menu)
        about_action.triggered.connect(self.show_about)

        # Add 'Exit' action
        self._quit_action = TrayAction("Quit", "", AppIcon.icon("quit"), self.tray_menu)
        self._quit_action.triggered.connect(self.exit_requested)

        # stack
        self.tray_menu.addAction(self.snip_action)
        self.tray_menu.addAction(self.close_pins_action)
        self.tray_menu.addSeparator()
        # Plugin reserved
        self._plugin_separator = self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.hotkeys_enabled_action)
        self.tray_menu.addAction(self.hotkeys_suspended_action)
        # Helpers.
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(settings_action)
        self.tray_menu.addAction(about_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self._quit_action)

        # Bind the built menu to the tray object
        self.tray_icon.setContextMenu(self.tray_menu)


    def create_tray_menu(self):
        """Creates the right-click context menu and keeps references to actions."""
        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                padding: 5px;
            }
            QMenu::icon {
                vertical-align: middle;
                position: relative;
                /* top-bottom left-right ; */
                margin: 2px 7px;
            }
            QMenu::separator {
                height: 1px;
                background-color: #DCDCDC;
                /* top-bottom left-right ; */
                margin: 3px 10px;
            }
            QMenu::item {
                /* top right down left ; */
                padding: 2px 15px 2px 15px;
                border-radius: 4px;
                margin: 2px 0px;
            }
            QMenu::item:selected {
                background-color: #e5f1fb;
                color: #0066cc;
            }
            QMenu::indicator {
                width: 18px;
                left: 6px;
            }

        """)

        # Let controller determine the action's callback
        self.snip_action = Action(AppIcon.icon("snip"), "Snip screen", self.tray_menu)
        # self.snip_action.setShortcut("F1")
        self.snip_action.triggered.connect(self.handle_snip_click)
        # self.snip_action.triggered.connect(self.snapshot_requested)

        self.close_pins_action = Action("Close all pins", self.tray_menu)
        self.close_pins_action.triggered.connect(self.close_pins_requested)

        # Emits True when enable(registered), False when disable(un-register)
        self.hotkeys_enabled_action = Action("Enable hotkeys", self.tray_menu)
        self.hotkeys_enabled_action.setCheckable(True)
        self.hotkeys_enabled_action.triggered.connect(self.hotkeys_enabled_changed)

        # Emits True when paused/suppressed, False when active
        self.hotkeys_suspended_action = Action("Suspend hotkeys", self.tray_menu)
        self.hotkeys_suspended_action.setCheckable(True)
        self.hotkeys_suspended_action.triggered.connect(self.hotkeys_suspended_changed)

        settings_action = Action(AppIcon.icon("settings"), "Preference", self)
        settings_action.triggered.connect(self.settings_dialog_requested)

        # About
        about_action = Action(AppIcon.icon("about"), "About", self.tray_menu)
        about_action.triggered.connect(self.show_about)

        # Add 'Exit' action
        self._quit_action = Action(AppIcon.icon("quit"), "Quit", self.tray_menu)
        self._quit_action.triggered.connect(self.exit_requested)

        self.tray_menu.addAction(self.snip_action)
        self.tray_menu.addAction(self.close_pins_action)
        self.tray_menu.addSeparator()
        # Plugin
        self._plugin_separator = self.tray_menu.addSeparator()

        self.tray_menu.addAction(self.hotkeys_enabled_action)
        self.tray_menu.addAction(self.hotkeys_suspended_action)

        # Helpers.
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(settings_action)
        self.tray_menu.addAction(about_action)

        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self._quit_action)

        # self.tray_menu.aboutToShow.connect(self.refresh_tray_menu)
        # Bind the built menu to the tray object
        self.tray_icon.setContextMenu(self.tray_menu)

    def handle_snip_click(self):
        self.close_menu_and_overflow()
        QTimer.singleShot(100, lambda: self.snapshot_requested.emit())

    def close_menu_and_overflow(self):
        """
        Close menu and overlay (e.g before snip.)
        """
        self.tray_menu.close()
        try:
            hwnd_overflow = user32.FindWindowW(
                "TopLevelWindowForOverflowXamlIsland", None
            )
            if not hwnd_overflow:
                hwnd_overflow = user32.FindWindowW("NotifyIconOverflowWindow", None)
            if hwnd_overflow:
                ctypes.windll.user32.ShowWindow(hwnd_overflow, 0)  # SW_HIDE
        except Exception as e:
            logging.warning("[Tray] Hide overflow failed!")

    def set_plugin_actions(self, infos: Iterable[PluginInfo]) -> None:
        # infos = list(infos)  # Also works if the manager returns a generator.
        for action in self._plugin_actions:
            self.tray_menu.removeAction(action)
            action.deleteLater()
        self._plugin_actions.clear()
        self._plugin_separator.setVisible(bool(infos))
        for info in infos:
            action = Action(AppIcon.icon(info.icon), info.name, self.tray_menu)
            action.setStatus(info.hotkey.lower().title())
            # action = TrayAction(
            #     info.name,
            #     info.hotkey.lower().title(),
            #     AppIcon.icon(info.icon),
            #     self.tray_menu,
            # )
            action.triggered.connect(
                lambda checked=False, pid=info.plugin_id: self.pluginSelected.emit(
                    pid, PluginContext(source="tray")
                )
            )
            self.tray_menu.insertAction(self._plugin_separator, action)
            self._plugin_actions.append(action)

    @pyqtSlot(QSystemTrayIcon.ActivationReason)
    def on_tray_activated(self, reason):
        """
        Handles mouse interaction with the system tray icon.
        Allows users to instantly trigger a snip session via left-click/double-click.
        """
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.tray_menu.popup(QSystemTrayIcon.geometry(self.tray_icon).center())
            self.tray_menu.activateWindow()
            # self.snapshot_requested.emit()

    def show_about(self):
        # QMessageBox.about(
        #     None,
        #     f"About {AppInfo.NAME}",
        #     AppInfo.about_text(),
        # )
        msg = QMessageBox()
        msg.setWindowTitle(f"About {AppInfo.NAME}")
        msg.setText(AppInfo.about_text())
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setIconPixmap(QApplication.windowIcon().pixmap(64, 64))
        msg.setStyleSheet("""
            QMessageBox QPushButton {
                color: #303030;
            }
        """)

        msg.exec()

    # ==========================================
    # Public call
    # ==========================================
    def show_notification(self, title: str, message: str, icon=None):
        if icon is None:
            icon = self.app_icon

        if self.tray_icon:
            self.tray_icon.showMessage(title, message, icon, 1000)

    def set_tooltip(self, tooltip_str: str = ""):
        self.tray_icon.setToolTip(tooltip_str)

    def set_actions_shortcuts(self, config_dict):
        """
        Set shortcut for actions
        """
        new_snip_key = config_dict.get("capture_area", "")
        self.snip_action.setStatus(new_snip_key)

    def set_pin_status(self, status):
        """
        Set pin status for actions
        """
        self.close_pins_action.setStatus(status)
        return

    def show(self):
        """
        Public method to safely display the tray icon to the OS taskbar.
        """
        if self.tray_icon:
            self.tray_icon.show()

    def shutdown(self):
        """
        Safely hides the tray icon, disconnects OS signals,
        and schedules C++ memory destruction.
        """
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon.setContextMenu(None)
            try:
                self.tray_icon.activated.disconnect()
            except TypeError:
                pass
            self.tray_icon.deleteLater()
            self.tray_icon = None

    # def refresh_tray_menu(self):
    #     print("Force reset traymenu")
    #     current_qss = self.tray_menu.styleSheet()
    #     self.tray_menu.setStyleSheet("")
    #     self.tray_menu.setStyleSheet(current_qss)
    #     for action in self.tray_menu.actions():
    #         action.changed.emit()
    #     self.tray_menu.updateGeometry()
    #     self.tray_menu.adjustSize()
