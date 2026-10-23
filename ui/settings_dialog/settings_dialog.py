from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from resources import icon_provider
from ui.settings_dialog.user_guide_tab import UserGuideTab

from .hotkey_tab import HotkeysTab
from .about_tab import AboutTab
from .general_tab import GeneralTab
from .plugin_tab import PluginsTab
from PyQt6.QtCore import pyqtSignal, Qt
from utils.system_helper import open_system_file


class _SettingsHeader(QFrame):
    """Draggable header for the frameless settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


# class SettingsDialog(QDialog):
class SettingsDialog(QDialog):
    hotkeys_enabled_requested = pyqtSignal(bool)
    settings_changed = pyqtSignal()

    def __init__(
        self,
        settings_manager,
        controller=None,
        parent=None,
        general_data=None,
        hotkeys_data=None,
        plugins_data=None,
    ):
        super().__init__(parent)

        self.settings_manager = settings_manager
        self.controller = controller

        self.setWindowTitle("Settings")
        self.setObjectName("settingsDialog")
        self.resize(800, 450)
        self.setMinimumSize(700, 400)

        # Set before the window is first shown.
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        all_data = self.settings_manager.data()
        self.builtin_hotkeys = all_data["hotkeys"]

        # ------------------------------------------------------
        # Existing settings pages and connections
        # ------------------------------------------------------
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("settingsTabs")
        self.tabs.tabBar().hide()

        self.general_tab = GeneralTab(general_data)
        self.general_tab.settings_changed.connect(self.on_general_changed)
        self.general_tab.open_log_requested.connect(lambda: open_system_file("app.log"))
        self.general_tab.open_config_requested.connect(open_system_file)

        self.hotkeys_tab = HotkeysTab(self.builtin_hotkeys)
        self.hotkeys_tab.settings_changed.connect(self.on_settings_changed)

        self.plugins_tab = PluginsTab(plugins_data, hotkeys_data)
        self.user_guide = UserGuideTab()
        self.about_tab = AboutTab()

        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.hotkeys_tab, "Hotkeys")
        self.tabs.addTab(self.plugins_tab, "Plugins")
        self.tabs.addTab(self.user_guide, "Guide")
        self.tabs.addTab(self.about_tab, "About")

        # ------------------------------------------------------
        # Existing action buttons
        # ------------------------------------------------------
        self.button_box = QDialogButtonBox(self)

        self.btn_ok = self.button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        self.btn_cancel = self.button_box.addButton(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.btn_apply = self.button_box.addButton(
            "Apply",
            QDialogButtonBox.ButtonRole.ApplyRole,
        )

        self.btn_ok.clicked.connect(self.on_ok)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self.on_apply)
        self.btn_apply.setEnabled(False)

        # ------------------------------------------------------
        # Guide-style dialog layout
        # ------------------------------------------------------
        self._build_ui()
        self._apply_style()

        self.tabs.currentChanged.connect(self._update_navigation)
        self._update_navigation(self.tabs.currentIndex())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        self.shell = QFrame(self)
        self.shell.setObjectName("settingsShell")
        root.addWidget(self.shell)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        # Header
        header = _SettingsHeader(self.shell)
        header.setObjectName("settingsHeader")
        header.setFixedHeight(68)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 18, 12)
        header_layout.setSpacing(12)

        icon = self.windowIcon()
        brand = QLabel(header)
        brand.setObjectName("settingsBrand")
        brand.setFixedSize(40, 40)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setPixmap(icon.pixmap(QSize(40, 40)))
        header_layout.addWidget(brand)

        titles = QVBoxLayout()
        titles.setSpacing(1)

        title = QLabel(QApplication.applicationName() or "SniPin", header)
        title.setObjectName("settingsHeaderTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        titles.addWidget(title)

        subtitle = QLabel("SETTINGS", header)
        subtitle.setObjectName("settingsHeaderSubtitle")
        subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        titles.addWidget(subtitle)

        header_layout.addLayout(titles)
        header_layout.addStretch()

        close_button = QPushButton("✕", header)
        close_button.setObjectName("settingsCloseButton")
        close_button.setFixedSize(34, 34)
        close_button.setToolTip("Close settings")
        close_button.clicked.connect(self.reject)
        header_layout.addWidget(close_button)

        # close_button = QPushButton(header)
        # close_button.setObjectName("settingsCloseButton")
        # close_button.setFixedSize(34, 34)
        # close_button.setIcon(icon_provider.icon("close"))
        # close_button.setIconSize(QSize(34, 34))
        # close_button.setAutoDefault(False)
        # close_button.clicked.connect(self.reject)
        # header_layout.addWidget(close_button)

        shell_layout.addWidget(header)

        # Body
        body = QWidget(self.shell)
        body.setObjectName("settingsBody")

        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget(body)
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(180)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 22, 14, 18)
        sidebar_layout.setSpacing(7)

        caption = QLabel("PREFERENCES", sidebar)
        caption.setObjectName("settingsSidebarCaption")
        sidebar_layout.addWidget(caption)

        self.nav_buttons: list[QPushButton] = []

        for index in range(self.tabs.count()):
            button = QPushButton(
                self.tabs.tabText(index),
                sidebar,
            )
            button.setObjectName("settingsNavButton")
            button.setCheckable(True)
            button.setFixedHeight(42)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.clicked.connect(
                lambda checked=False, page=index: (self.tabs.setCurrentIndex(page))
            )

            sidebar_layout.addWidget(button)
            self.nav_buttons.append(button)

        sidebar_layout.addStretch()

        hint = QLabel("Customize SniPin settings to fit your workflow.", sidebar)
        hint.setObjectName("settingsSidebarHint")
        hint.setWordWrap(True)
        sidebar_layout.addWidget(hint)

        body_layout.addWidget(sidebar)

        # Content and footer
        content = QWidget(body)
        content.setObjectName("settingsContent")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 18)
        content_layout.setSpacing(12)

        self.section_label = QLabel(content)
        self.section_label.setObjectName("settingsSectionLabel")
        content_layout.addWidget(self.section_label)

        content_layout.addWidget(self.tabs, 1)

        footer = QFrame(content)
        footer.setObjectName("settingsFooter")

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 12, 0, 0)
        footer_layout.addStretch()
        footer_layout.addWidget(self.button_box)

        content_layout.addWidget(footer)

        body_layout.addWidget(content, 1)
        shell_layout.addWidget(body, 1)

    def _update_navigation(self, index: int):
        if index < 0:
            return

        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

        self.section_label.setText(self.tabs.tabText(index).upper())

    def refresh_data(
        self,
        general_data=None,
        hotkeys_data=None,
        plugins_data=None,
    ):
        """Refresh tab contents from current application state."""
        all_settings = self.settings_manager.data()

        if general_data is not None:
            self.general_tab.refresh_data(general_data)

        if hotkeys_data is not None:
            self.hotkeys_tab.refresh_data(all_settings.get("hotkeys"))

        if plugins_data is not None:
            self.plugins_tab.refresh_data(
                plugins_data,
                hotkeys_data,
            )

    def on_general_changed(self, *args):
        self.btn_apply.setEnabled(True)

    def on_settings_changed(self, *args):
        self.btn_apply.setEnabled(True)

    def collect_data(self):
        return {
            "hotkeys": self.hotkeys_tab.get_data(),
            "general": self.general_tab.get_data(),
        }

    def validate(self):
        return self.hotkeys_tab.validate()

    def on_apply(self) -> bool:
        """Return True only when settings were applied."""
        if not self.validate():
            return False

        self.settings_manager.set_all(self.collect_data())
        self.btn_apply.setEnabled(False)
        return True

    def on_ok(self):
        if self.btn_apply.isEnabled():
            if not self.on_apply():
                return

        self.settings_changed.emit()
        self.hotkeys_enabled_requested.emit(True)
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)

        self.tabs.setCurrentIndex(0)

        data = self.settings_manager.data()
        self.builtin_hotkeys = data["hotkeys"]
        self.general_settings = data["general"]

        self.refresh_data(
            hotkeys_data=self.builtin_hotkeys,
            general_data=self.general_settings,
        )

        # Refreshing controls should not leave Apply enabled.
        self.btn_apply.setEnabled(False)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog#settingsDialog {
                background: transparent;
            }

            QFrame#settingsShell {
                background: #F6F9FD;
                border: 1px solid #DCE6F1;
                border-radius: 18px;
            }

            QFrame#settingsHeader {
                background: #0878D7;
                border: none;
                border-top-left-radius: 17px;
                border-top-right-radius: 17px;
            }

            QLabel#settingsBrand {
                background: transparent;
                border-radius: 10px;
            }

            QLabel#settingsHeaderTitle {
                color: white;
                font-size: 20px;
                font-weight: 750;
            }

            QLabel#settingsHeaderSubtitle {
                color: #D9ECFF;
                font-size: 12px;
                font-weight: 700;
            }

            QPushButton#settingsCloseButton {
                color: white;
                background: transparent;
                border: none;
                border-radius: 8px;
                font-size: 30px;
                padding-bottom: 2px;
            }

            QPushButton#settingsCloseButton:hover {
                /*background: #FFFFFF30;*/
                color: #ff0000; /*#172944;*/
            }

            QDialogButtonBox QPushButton:disabled {
                color: #9AA8B8;
                background: #EEF2F6;
                border-color: #DFE6EE;
            }

            QWidget#settingsBody {
                background: transparent;
            }

            QWidget#settingsSidebar {
                background: #EDF3FA;
                border-bottom-left-radius: 17px;
            }

            QLabel#settingsSidebarHint {
                color: #73869B;
                background: #E3EDF8;
                border-radius: 10px;
                padding: 5px;
                font-size: 11px;
            }

            QWidget#settingsContent {
                background: #F6F9FD;
                border-bottom-right-radius: 17px;
            }

            QLabel#settingsSidebarCaption {
                color: #778AA1;
                font-size: 12px;
                font-weight: 750;
                padding: 0 10px 9px 10px;
            }

            QPushButton#settingsNavButton {
                color: #344963;
                background: transparent;
                border: none;
                border-radius: 9px;
                padding-left: 13px;
                text-align: left;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton#settingsNavButton:hover {
                background: #DFEBF8;
            }
            QPushButton#settingsNavButton:checked {
                color: #0878D7;
                background: white;
                font-weight: 750;
            }
            /*top right pandel tab name: General...*/
            QLabel#settingsSectionLabel {
                color: #0878D7;
                font-size: 16px;
                font-weight: 750;
            }

            QTabWidget#settingsTabs,
            QTabWidget#settingsTabs::pane {
                background: transparent;
                border: none;
            }

            QFrame#settingsFooter {
                background: transparent;
                border-top: 1px solid #DFE8F2;
            }
            QDialogButtonBox QPushButton {
                min-width: 70px;
                min-height: 25px;
                padding: 4px 10px;
                border: 1px solid #D5E1EE;
                border-radius: 8px;
                background: white;
                color: #27415D;
            }
            QDialogButtonBox QPushButton:hover {
                background: #EAF4FF;
                border-color: #A9D4F4;
            }
            """)


# from PyQt6.QtWidgets import (
#     QDialog,
#     QVBoxLayout,
#     QTabWidget,
#     QDialogButtonBox,
# )

# from temp import SettingsGuideShell

# from .hotkey_tab import HotkeysTab
# from .about_tab import AboutTab
# from .general_tab import GeneralTab
# from .plugin_tab import PluginsTab
# from PyQt6.QtCore import pyqtSignal, Qt
# from ui.widgets import CustomMessageBox
# from utils.system_helper import open_system_file


# # from ._ToolsTab import ToolsTab
# class SettingsDialog(QDialog):
#     hotkeys_enabled_requested = pyqtSignal(bool)
#     settings_changed = pyqtSignal()

#     def __init__(
#         self,
#         settings_manager,
#         controller=None,
#         parent=None,
#         general_data=None,
#         hotkeys_data=None,
#         plugins_data=None,
#     ):
#         super().__init__(parent)

#         self.settings_manager = settings_manager
#         self.setWindowTitle("Settings")
#         self.resize(600, 600)
#         # self.setMinimumSize(600, 500)
#         # self.setMaximumSize(600, 600)

#         all_data = self.settings_manager.data()
#         self.builtin_hotkeys = all_data["hotkeys"]

#         layout = QVBoxLayout(self)
#         self.tabs = QTabWidget()
#         self.tabs.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

#         layout.addWidget(self.tabs)
#         self.general_tab = GeneralTab(general_data)
#         self.general_tab.settings_changed.connect(self.on_general_changed)
#         self.general_tab.open_log_requested.connect(lambda: open_system_file("app.log"))
#         self.general_tab.open_config_requested.connect(open_system_file)

#         self.hotkeys_tab = HotkeysTab(self.builtin_hotkeys)
#         self.hotkeys_tab.settings_changed.connect(self.on_settings_changed)
#         self.plugins_tab = PluginsTab(plugins_data, hotkeys_data)
#         self.hotkeys_tab.settings_changed.connect(self.on_general_changed)
#         self.AboutTab = AboutTab()

#         self.tabs.addTab(self.general_tab, "General")
#         self.tabs.addTab(self.hotkeys_tab, "Hotkeys")
#         self.tabs.addTab(self.plugins_tab, "Plugins")
#         self.tabs.addTab(self.AboutTab, "About")

#         self.button_box = QDialogButtonBox()
#         self.btn_ok = self.button_box.addButton(QDialogButtonBox.StandardButton.Ok)
#         self.btn_cancel = self.button_box.addButton(
#             QDialogButtonBox.StandardButton.Cancel
#         )
#         self.btn_apply = self.button_box.addButton(
#             "Apply", QDialogButtonBox.ButtonRole.ApplyRole
#         )

#         self.btn_ok.clicked.connect(self.on_ok)
#         self.btn_cancel.clicked.connect(self.reject)
#         self.btn_apply.clicked.connect(self.on_apply)
#         self.btn_apply.setEnabled(False)
#         self.btn_cancel.setFocus()

#         layout.addWidget(self.button_box)
#         self.tabs.setFocus()
#         # self.adjustSize()
#         self._settings_shell = SettingsGuideShell(
#             dialog=self,
#             tabs=self.tabs,
#             button_box=self.button_box,
#         )

#     def refresh_data(
#         self,
#         general_data=None,
#         hotkeys_data=None,
#         plugins_data=None,
#     ):
#         """Refresh tab contents from current application state."""
#         all_settings = self.settings_manager.data()
#         if general_data is not None:
#             self.general_tab.refresh_data(general_data)

#         if hotkeys_data is not None:
#             self.hotkeys_tab.refresh_data(all_settings.get("hotkeys"))

#         if plugins_data is not None:
#             self.plugins_tab.refresh_data(plugins_data, hotkeys_data)

#     def on_general_changed(self, combo, text):
#         self.btn_apply.setEnabled(True)
#         self.btn_apply.setFocus()

#     def on_settings_changed(self, editor, hotkey_sq):
#         self.btn_apply.setEnabled(True)
#         self.btn_apply.setFocus()

#     def collect_data(self):
#         return {
#             "hotkeys": self.hotkeys_tab.get_data(),
#             # "plugins": self.tools_tab.get_data(),
#             "general": self.general_tab.get_data(),
#         }

#     def validate(self):
#         return self.hotkeys_tab.validate()

#     def on_apply(self):
#         if not self.validate():
#             return
#         data = self.collect_data()
#         self.settings_manager.set_all(data)
#         self.btn_apply.setEnabled(False)

#     def on_ok(self):
#         """
#         Call apply() to save new settings.
#         Request to update the changed hotkeys with new settings.
#         """
#         if self.btn_apply.isEnabled():
#             self.on_apply()
#         # Only apply on OK button
#         self.settings_changed.emit()
#         self.hotkeys_enabled_requested.emit(True)
#         self.accept()

#     def reject(self):
#         super().reject()  # Pass execution chain upstream to complete window deletion

#     # =========================================================================
#     # AUTOMATIC HOTKEY TOGGLE TRAPS
#     # =========================================================================
#     def showEvent(self, event):
#         super().showEvent(event)
#         self.tabs.setCurrentIndex(0)
#         self.builtin_hotkeys = self.settings_manager.data()["hotkeys"]
#         self.general_settings = self.settings_manager.data()["general"]
#         self.refresh_data(
#             hotkeys_data=self.builtin_hotkeys, general_data=self.general_settings
#         )
#         self.tabs.setFocus()

#     def hideEvent(self, event):
#         """
#         Request to enable all the Disable hotkeys,
#         enable hotkeys will be skipped.
#         """
#         # self.hotkeys_enabled_requested.emit(True)
#         super().hideEvent(event)
