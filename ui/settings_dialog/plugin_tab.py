from __future__ import annotations

from pathlib import Path
import shutil

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class PluginFrame(QFrame):
    enabled_changed = pyqtSignal(str, bool)

    def __init__(
        self,
        plugin_id: str,
        display_name: str,
        description: str,
        hotkey: str | None,
        enabled: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Keep the actual ID separate from the human-readable name.
        self.plugin_id = plugin_id
        self.setObjectName("pluginCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(18)

        # ------------------------------------------------------
        # Left: plugin identity and description
        # ------------------------------------------------------
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)

        self.name_label = QLabel(display_name or plugin_id, self)
        self.name_label.setObjectName("pluginName")
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        title_row.addWidget(self.name_label)

        self.hotkey_label = QLabel(
            f"Hotkey: {hotkey}" if hotkey else "No Hotkey",
            self,
        )
        self.hotkey_label.setObjectName("pluginHotkey")
        self.hotkey_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        title_row.addWidget(self.hotkey_label)
        title_row.addStretch()

        info_layout.addLayout(title_row)

        self.module_label = QLabel(
            description or "No description provided.",
            self,
        )
        self.module_label.setObjectName("pluginDescription")
        self.module_label.setWordWrap(True)
        self.module_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        info_layout.addWidget(self.module_label)

        metadata_row = QHBoxLayout()
        metadata_row.setContentsMargins(0, 5, 0, 0)
        metadata_row.setSpacing(8)

        self.id_label = QLabel(f"ID: {plugin_id}", self)
        self.id_label.setObjectName("pluginMeta")
        self.id_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        metadata_row.addWidget(self.id_label)

        # metadata_row.addWidget(self.hotkey_label)

        metadata_row.addStretch()
        info_layout.addLayout(metadata_row)

        layout.addLayout(info_layout, 1)

        # ------------------------------------------------------
        # Right: activation control
        # Keep the native checkbox indicator for reliable rendering.
        # ------------------------------------------------------
        self.enabled_check = QCheckBox("Enabled", self)
        self.enabled_check.setObjectName("pluginEnabledCheck")
        self.enabled_check.setChecked(enabled)

        layout.addWidget(
            self.enabled_check,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.enabled_check.toggled.connect(
            lambda checked: self.enabled_changed.emit(
                self.plugin_id,
                checked,
            )
        )


class PluginsTab(QWidget):
    """
    Plugin settings page styled to match the Snipin user guide.

    Expected plugin record attributes:
        plugin_id: str
        instance: optional plugin instance with NAME / DESCRIPTION
        enabled: bool

    Expected hotkey mapping:
        hotkeys_data[plugin_id].hotkey_seq
    """

    plugin_enabled_changed = pyqtSignal(str, bool)
    reload_requested = pyqtSignal()
    plugin_added = pyqtSignal(str)

    def __init__(
        self,
        plugins_data,
        hotkeys_data,
        parent: QWidget | None = None,
        plugins_dir: str | Path = "plugins",
    ) -> None:
        super().__init__(parent)

        self.setObjectName("pluginsTab")

        self.plugins_dir = Path(plugins_dir)
        self.plugins = {}
        self.plugin_frames: dict[str, PluginFrame] = {}

        self._build_ui()
        self._apply_style()
        self.refresh_data(plugins_data, hotkeys_data)

    # ==========================================================
    # UI
    # ==========================================================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(16)

        # ------------------------------------------------------
        # Heading
        # ------------------------------------------------------
        heading_row = QHBoxLayout()
        heading_row.setContentsMargins(0, 0, 0, 0)
        heading_row.setSpacing(12)

        heading_text = QVBoxLayout()
        heading_text.setContentsMargins(0, 0, 0, 0)
        heading_text.setSpacing(4)

        title = QLabel("Installed plugins", self)
        title.setObjectName("pluginsTitle")
        heading_text.addWidget(title)

        description = QLabel(
            "Manage extensions and choose which plugins are active.",
            self,
        )
        description.setObjectName("pluginsSubtitle")
        description.setWordWrap(True)
        heading_text.addWidget(description)

        heading_row.addLayout(heading_text, 1)

        self.count_label = QLabel("0 plugins", self)
        self.count_label.setObjectName("pluginsCount")
        heading_row.addWidget(
            self.count_label,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        layout.addLayout(heading_row)

        # ------------------------------------------------------
        # Scrollable cards
        # ------------------------------------------------------
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("pluginsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.plugins_widget = QWidget(self.scroll_area)
        self.plugins_widget.setObjectName("pluginsList")

        self.plugins_layout = QVBoxLayout(self.plugins_widget)
        self.plugins_layout.setContentsMargins(1, 2, 9, 2)
        self.plugins_layout.setSpacing(10)

        self.empty_label = QLabel(
            "No plugins installed yet.\n" "Use Add Plugin to install a Python plugin.",
            self.plugins_widget,
        )
        self.empty_label.setObjectName("pluginsEmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)

        self.plugins_layout.addWidget(self.empty_label)
        self.plugins_layout.addStretch(1)

        self.scroll_area.setWidget(self.plugins_widget)
        layout.addWidget(self.scroll_area, 1)

        # ------------------------------------------------------
        # Bottom actions
        # ------------------------------------------------------
        footer = QFrame(self)
        footer.setObjectName("pluginsFooter")

        button_layout = QHBoxLayout(footer)
        button_layout.setContentsMargins(0, 13, 0, 0)
        button_layout.setSpacing(10)

        self.add_button = QPushButton("Add Plugin...", footer)
        self.add_button.setObjectName("addPluginButton")
        self.add_button.setMinimumHeight(38)
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )

        self.reload_button = QPushButton("Reload Plugins", footer)
        self.reload_button.setObjectName("reloadPluginsButton")
        self.reload_button.setMinimumHeight(38)
        self.reload_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )

        button_layout.addWidget(self.add_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.reload_button)

        layout.addWidget(footer)

        self.add_button.clicked.connect(self._select_plugin_file)
        self.reload_button.clicked.connect(self.reload_requested.emit)

    # ==========================================================
    # Refresh
    # ==========================================================

    def refresh_data(self, plugins_data, hotkeys_data) -> None:
        self.plugins = plugins_data or {}

        # Remove old cards from the layout immediately, then schedule
        # their deletion. This avoids stale cards during rapid refreshes.
        for frame in self.plugin_frames.values():
            self.plugins_layout.removeWidget(frame)
            frame.hide()
            frame.deleteLater()

        self.plugin_frames.clear()

        if isinstance(self.plugins, dict):
            records = list(self.plugins.values())
        else:
            records = list(self.plugins)

        for plugin in records:
            plugin_id = str(getattr(plugin, "plugin_id", "") or "")
            if not plugin_id:
                continue

            instance = getattr(plugin, "instance", None)

            display_name = (
                str(getattr(instance, "NAME", "") or "") if instance is not None else ""
            ) or plugin_id

            description = (
                str(getattr(instance, "DESCRIPTION", "") or "")
                if instance is not None
                else ""
            )

            enabled = bool(getattr(plugin, "enabled", False))

            hotkey = None
            if isinstance(hotkeys_data, dict):
                hotkey_spec = hotkeys_data.get(plugin_id)
                if hotkey_spec is not None:
                    hotkey = getattr(hotkey_spec, "hotkey_seq", None)

            frame = PluginFrame(
                plugin_id=plugin_id,
                display_name=display_name,
                description=description,
                hotkey=str(hotkey).upper() if hotkey else None,
                enabled=enabled,
                parent=self.plugins_widget,
            )
            frame.enabled_changed.connect(self.plugin_enabled_changed.emit)

            # Keep the stretch at the bottom.
            self.plugins_layout.insertWidget(
                self.plugins_layout.count() - 1,
                frame,
            )
            self.plugin_frames[plugin_id] = frame

        count = len(self.plugin_frames)
        self.count_label.setText(
            f"{count} plugin" if count == 1 else f"{count} plugins"
        )
        self.empty_label.setVisible(count == 0)

    # ==========================================================
    # Add plugin
    # ==========================================================

    def _select_plugin_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add Plugin",
            "",
            "Python Plugin (*.py *.pyd)",
        )
        if not file_path:
            return

        source = Path(file_path)
        destination = self.plugins_dir / source.name

        try:
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

            if destination.exists():
                answer = QMessageBox.question(
                    self,
                    "Plugin already exists",
                    f"{source.name} already exists.\n\n" "Replace the existing plugin?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return

            # Avoid copying a file onto itself if the user selects an
            # already-installed plugin from the plugins directory.
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Add Plugin Failed",
                str(exc),
            )
            return

        self.plugin_added.emit(str(destination))
        self.reload_requested.emit()

    # ==========================================================
    # Styling
    # ==========================================================

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget#pluginsTab,
            QWidget#pluginsList,
            QScrollArea#pluginsScrollArea,
            QScrollArea#pluginsScrollArea QWidget#qt_scrollarea_viewport {
                background: transparent;
                border: none;
            }

            QLabel#pluginsTitle {
                color: #192C45;
                font-size: 14px;
                font-weight: 750;
            }

            QLabel#pluginsSubtitle {
                color: #64758B;
                font-size: 12px;
            }

            QLabel#pluginsCount {
                color: #0878D7;
                background: #EAF4FF;
                border-radius: 9px;
                padding: 6px 10px;
                font-size: 14px;
                font-weight: 700;
            }

            QFrame#pluginCard {
                background: #FFFFFF;
                border: 1px solid #DEE8F3;
                border-radius: 12px;
            }

            QFrame#pluginCard:hover {
                border: 1px solid #A9D4F4;
                background: #FCFEFF;
            }

            QLabel#pluginName {
                color: #1D3049;
                font-size: 14px;
                font-weight: 750;
                background: transparent;
            }

            QLabel#pluginDescription {
                color: #64758B;
                font-size: 12px;
                background: transparent;
            }

            QLabel#pluginMeta {
                color: #71839A;
                font-size: 12px;
                background: transparent;
            }

            QLabel#pluginHotkey {
                color: #0878D7;
                background: #EAF4FF;
                border-radius: 6px;
                padding: 4px 7px;
                font-size: 12px;
                font-weight: 700;
            }

            QCheckBox#pluginEnabledCheck {
                color: #344963;
                font-size: 14px;
                font-weight: 650;
                spacing: 7px;
                background: transparent;
            }

            QLabel#pluginsEmptyState {
                color: #73869B;
                background: #FFFFFF;
                border: 1px dashed #C7D8E9;
                border-radius: 12px;
                padding: 26px;
                font-size: 14px;
            }

            QFrame#pluginsFooter {
                background: transparent;
                border-top: 1px solid #DFE8F2;
            }

            QPushButton#addPluginButton {
                color: #FFFFFF;
                background: #0878D7;
                border: 1px solid #0878D7;
                border-radius: 9px;
                padding: 0 14px;
                font-size: 14px;
                font-weight: 700;
            }

            QPushButton#addPluginButton:hover {
                background: #006BC4;
                border-color: #006BC4;
            }

            QPushButton#reloadPluginsButton {
                color: #27415D;
                background: #FFFFFF;
                border: 1px solid #D5E1EE;
                border-radius: 9px;
                padding: 0 14px;
                font-size: 14px;
                font-weight: 650;
            }

            QPushButton#reloadPluginsButton:hover {
                background: #EAF4FF;
                border-color: #A9D4F4;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 9px;
                margin: 2px;
            }

            QScrollBar::handle:vertical {
                background: #C7D7E8;
                border-radius: 4px;
                min-height: 28px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """)


# from pathlib import Path
# import shutil

# from PyQt6.QtCore import Qt, pyqtSignal
# from PyQt6.QtWidgets import (
#     QCheckBox,
#     QFileDialog,
#     QFrame,
#     QHBoxLayout,
#     QLabel,
#     QMessageBox,
#     QPushButton,
#     QScrollArea,
#     QStyle,
#     QVBoxLayout,
#     QWidget,
# )


# class PluginFrame(QFrame):
#     enabled_changed = pyqtSignal(str, bool)

#     def __init__(
#         self,
#         plugin_id: str,
#         module_name: str,
#         hotkey: str | None,
#         enabled: bool,
#         parent=None,
#     ):
#         super().__init__(parent)

#         self.plugin_id = plugin_id

#         self.setFrameShape(QFrame.Shape.StyledPanel)

#         # ======================================================
#         # Main layout
#         # ======================================================
#         layout = QHBoxLayout(self)
#         layout.setContentsMargins(12, 10, 12, 10)
#         layout.setSpacing(12)

#         # ======================================================
#         # Plugin information
#         # ======================================================
#         info_layout = QVBoxLayout()
#         info_layout.setContentsMargins(0, 0, 0, 0)
#         info_layout.setSpacing(3)

#         self.name_label = QLabel(plugin_id)

#         name_font = self.name_label.font()
#         name_font.setBold(True)
#         self.name_label.setFont(name_font)

#         self.module_label = QLabel(module_name)

#         if hotkey:
#             self.hotkey_label = QLabel(f"Hotkey: {hotkey}")
#         else:
#             self.hotkey_label = QLabel("Hotkey: None")

#         info_layout.addWidget(self.name_label)
#         info_layout.addWidget(self.module_label)
#         info_layout.addWidget(self.hotkey_label)

#         # ======================================================
#         # Enabled
#         # ======================================================
#         self.enabled_check = QCheckBox("Enabled")
#         self.enabled_check.setChecked(enabled)

#         layout.addLayout(info_layout, 1)
#         layout.addWidget(self.enabled_check, 0, Qt.AlignmentFlag.AlignVCenter)

#         # ======================================================
#         # Signal
#         # ======================================================
#         self.enabled_check.toggled.connect(
#             lambda checked: self.enabled_changed.emit(self.plugin_id, checked)
#         )


# class PluginsTab(QWidget):
#     """
#     Plugin settings tab.

#     Expected plugin record attributes:
#         plugin_id: str
#         module_name: str
#         hotkey: str | None
#         enabled: bool
#     """

#     plugin_enabled_changed = pyqtSignal(str, bool)
#     reload_requested = pyqtSignal()
#     plugin_added = pyqtSignal(str)

#     def __init__(
#         self,
#         plugins_data,
#         hotkeys_data,
#         parent=None,
#     ):
#         super().__init__(parent)

#         self.plugins_dir = "plugins"
#         self.plugins = {}
#         self.plugin_frames = {}

#         self._build_ui()
#         self.refresh_data(
#             plugins_data,
#             hotkeys_data,
#         )

#     # ==========================================================
#     # UI
#     # ==========================================================

#     def _build_ui(self):
#         layout = QVBoxLayout(self)
#         layout.setContentsMargins(4, 4, 4, 4)
#         layout.setSpacing(10)

#         # ======================================================
#         # Description
#         # ======================================================
#         description = QLabel("Manage installed plugins and their activation status.")
#         description.setWordWrap(True)

#         layout.addWidget(description)
#         layout.addSpacing(4)

#         # ======================================================
#         # Scroll area
#         # ======================================================
#         self.scroll_area = QScrollArea()
#         self.scroll_area.setWidgetResizable(True)
#         self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

#         self.plugins_widget = QWidget()

#         self.plugins_layout = QVBoxLayout(self.plugins_widget)
#         self.plugins_layout.setContentsMargins(0, 0, 0, 0)
#         self.plugins_layout.setSpacing(6)

#         self.plugins_layout.addStretch(1)

#         self.scroll_area.setWidget(self.plugins_widget)

#         layout.addWidget(
#             self.scroll_area,
#             1,
#         )

#         # ======================================================
#         # Bottom buttons
#         # ======================================================
#         button_layout = QHBoxLayout()
#         button_layout.setContentsMargins(0, 2, 0, 0)
#         button_layout.setSpacing(8)

#         self.add_button = QPushButton("Add Plugin...")
#         self.add_button.setMinimumSize(100, 50)
#         self.add_button.setIcon(
#             self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
#         )

#         self.reload_button = QPushButton("Reload Plugins")
#         self.reload_button.setMinimumSize(100, 50)
#         self.reload_button.setIcon(
#             self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
#         )

#         button_layout.addWidget(self.add_button)
#         button_layout.addStretch(1)
#         button_layout.addWidget(self.reload_button)

#         layout.addLayout(button_layout)

#         # ======================================================
#         # Signals
#         # ======================================================
#         self.add_button.clicked.connect(self._select_plugin_file)

#         self.reload_button.clicked.connect(self.reload_requested.emit)

#     # ==========================================================
#     # Refresh
#     # ==========================================================

#     def refresh_data(
#         self,
#         plugins_data,
#         hotkeys_data,
#     ):

#         self.plugins = plugins_data or {}

#         # Remove previous frames
#         for frame in self.plugin_frames.values():
#             frame.deleteLater()

#         self.plugin_frames.clear()

#         if isinstance(self.plugins, dict):
#             records = self.plugins.values()
#         else:
#             records = self.plugins

#         for plugin in records:
#             plugin_name = ""
#             plugin_description = ""
#             plugin_id = getattr(plugin, "plugin_id", "")
#             plugin_instance = getattr(plugin, "instance", "")
#             if plugin_instance:
#                 plugin_name = getattr(plugin_instance, "NAME", "")
#                 plugin_description = getattr(plugin_instance, "DESCRIPTION", "")
#             else:
#                 plugin_name = plugin_id

#             enabled = getattr(plugin, "enabled", False)
#             hotkey = None
#             if isinstance(hotkeys_data, dict):
#                 hotkey_spec = hotkeys_data.get(plugin_id, hotkey)
#                 if hotkey_spec:
#                     hotkey = hotkey_spec.hotkey_seq
#             frame = PluginFrame(
#                 plugin_id=plugin_name,
#                 module_name=plugin_description,
#                 hotkey=hotkey,
#                 enabled=enabled,
#             )

#             frame.enabled_changed.connect(self.plugin_enabled_changed)

#             # Insert before stretch
#             self.plugins_layout.insertWidget(self.plugins_layout.count() - 1, frame)

#             self.plugin_frames[plugin_id] = frame

#     def _select_plugin_file(self):
#         file_path, _ = QFileDialog.getOpenFileName(
#             self, "Add Plugin", "", "Python Plugin (*.py *.pyd)"
#         )
#         if not file_path:
#             return
#         source = Path(file_path)
#         self.plugins_dir.mkdir(parents=True, exist_ok=True)
#         destination = self.plugins_dir / source.name
#         if destination.exists():
#             answer = QMessageBox.question(
#                 self,
#                 "Plugin already exists",
#                 (f"{source.name} already exists.\n\n" "Replace the existing plugin?"),
#                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
#             )
#             if answer != QMessageBox.StandardButton.Yes:
#                 return
#         try:
#             shutil.copy2(source, destination)
#         except Exception as exc:
#             QMessageBox.critical(self, "Add Plugin Failed", str(exc))
#             return
#         print(destination)
#         self.plugin_added.emit(str(destination))
#         self.reload_requested.emit()
