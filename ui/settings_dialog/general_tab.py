import sys
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QStyleFactory,
    QTabWidget,
    QWidget,
    QLabel,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QPushButton,
    QLineEdit,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
)
from PyQt6.QtGui import QPalette, QColor


class GeneralTab(QWidget):
    settings_changed = pyqtSignal(object, object)
    open_log_requested = pyqtSignal()
    open_config_requested = pyqtSignal(str)
    change_config_requested = pyqtSignal()
    restore_defaults_requested = pyqtSignal()
    help_requested = pyqtSignal()

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)

        self.settings_data = settings or {}
        self._apply_style()
        # ======================================================
        # Main layout
        # ======================================================
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ======================================================
        # Page description
        # ======================================================
        description = QLabel(
            "Configure application behavior, capture options and storage."
        )
        description.setObjectName("PageDescription")
        description.setWordWrap(True)

        layout.addWidget(description)

        # ======================================================
        # General card
        # ======================================================
        general_group = QGroupBox("General")
        general_group.setObjectName("SettingsCard")

        general_layout = QFormLayout(general_group)
        general_layout.setContentsMargins(16, 18, 16, 16)
        general_layout.setHorizontalSpacing(24)
        general_layout.setVerticalSpacing(8)
        general_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        general_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint
        )

        # Startup
        self.run_startup_check = QCheckBox()
        general_layout.addRow("Start with Windows", self.run_startup_check)
        # Logging
        log_widget = QWidget()
        log_widget.setObjectName("TransparentWidget")

        log_layout = QHBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(8)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["Debug", "Info", "Warning", "Error"])
        self.log_level_combo.setMinimumWidth(120)
        self.log_level_combo.setMinimumHeight(24)

        self.open_log_button = QPushButton("Open Log")
        self.open_log_button.setObjectName("SecondaryButton")
        self.open_log_button.setMinimumHeight(24)

        log_layout.addWidget(self.log_level_combo)
        log_layout.addWidget(self.open_log_button)
        log_layout.addStretch()

        general_layout.addRow("Logging", log_widget)

        layout.addWidget(general_group)

        # ======================================================
        # Capture card
        # ======================================================
        capture_group = QGroupBox("Capture")
        capture_group.setObjectName("SettingsCard")

        capture_layout = QFormLayout(capture_group)
        capture_layout.setContentsMargins(16, 18, 16, 16)
        capture_layout.setHorizontalSpacing(24)
        capture_layout.setVerticalSpacing(10)
        capture_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        # capture_layout.setFieldGrowthPolicy(
        #     QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint
        # )

        self.cb_hit_testing = QCheckBox()
        self.cb_hint_panel = QCheckBox()
        self.cb_cursor_magnifier = QCheckBox()
        self.cb_capture_cursor = QCheckBox()
        self.cb_win_mouse_capture = QCheckBox()
        self.cb_win_mouse_capture.setChecked(True)
        self.cb_win_mouse_capture.setEnabled(False)

        capture_layout.addRow("Automatically detect UI elements", self.cb_hit_testing)
        capture_layout.addRow("Show shortcut hint panel", self.cb_hint_panel)
        capture_layout.addRow("Show cursor magnifier", self.cb_cursor_magnifier)
        capture_layout.addRow("Capture system cursor", self.cb_capture_cursor)
        capture_layout.addRow(
            "Enable Winkey + mouse click gesture", self.cb_win_mouse_capture
        )

        # History
        history_widget = QWidget()
        history_widget.setObjectName("TransparentWidget")

        history_layout = QHBoxLayout(history_widget)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(8)

        self.max_stored_pins = QSpinBox()
        self.max_stored_pins.setRange(1, 30)
        self.max_stored_pins.setValue(10)
        # self.max_stored_pins.setStyleSheet("""
        #     QSpinBox::up-button,
        #     QSpinBox::down-button {
        #             width: 20px;}
        #     QSpinBox {
        #         background-color: white;
        #         border: 1px solid #b8bcc4;
        #         border-radius: 5px;
        #         padding: 3px 6px;
        #     }
        #     QSpinBox:hover {
        #         border-color: #8c919a;
        #     }
        #     QSpinBox:focus {
        #         border: 1px solid #4a90e2;
        #     }
        #     QSpinBox::up-button {
        #         subcontrol-origin: border;
        #         subcontrol-position: top right;
        #     }
        #     QSpinBox::down-button {
        #         subcontrol-origin: border;
        #         subcontrol-position: bottom right;
        #     }
        # """)

        # Wider and taller than the original 80 px spin box
        self.max_stored_pins.setFixedWidth(75)
        # self.max_stored_pins.setMinimumHeight(24)

        # history_suffix = QLabel("records")
        # history_suffix.setObjectName("SecondaryText")

        history_layout.addWidget(self.max_stored_pins)
        # history_layout.addWidget(history_suffix)
        history_layout.addStretch()

        capture_layout.addRow("Maximum history pins", history_widget)

        layout.addWidget(capture_group)

        # ======================================================
        # Configuration card
        # ======================================================
        config_group = QGroupBox("Configuration")
        config_group.setObjectName("SettingsCard")

        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(16, 18, 16, 16)
        config_layout.setSpacing(8)

        config_description = QLabel("Location used to store Snipin configuration.")
        config_description.setObjectName("SecondaryText")
        config_description.setWordWrap(True)

        config_layout.addWidget(config_description)

        # Path
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)

        self.config_path_edit = QLineEdit()
        self.config_path_edit.setReadOnly(True)
        self.config_path_edit.setPlaceholderText("Configuration file")
        self.config_path_edit.setMinimumHeight(32)

        self.open_config_button = QPushButton("Open")
        self.open_config_button.setObjectName("SecondaryButton")
        self.open_config_button.setMinimumSize(75, 32)

        self.change_config_button = QPushButton("Change")
        self.change_config_button.setEnabled(False)  # not function yet.
        self.change_config_button.setObjectName("SecondaryButton")
        self.change_config_button.setMinimumSize(75, 32)

        path_layout.addWidget(self.config_path_edit, 1)
        path_layout.addWidget(self.open_config_button)
        path_layout.addWidget(self.change_config_button)

        config_layout.addLayout(path_layout)

        layout.addWidget(config_group)

        # Keep all cards toward the top
        layout.addStretch(1)

        # ======================================================
        # Bottom controls
        # ======================================================
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 2, 0, 0)
        bottom_layout.setSpacing(8)

        self.help_button = QPushButton("?")
        self.help_button.setObjectName("HelpButton")
        self.help_button.setFixedSize(32, 32)
        self.help_button.setToolTip("Help")

        self.restore_defaults_button = QPushButton("Restore Defaults")
        self.restore_defaults_button.setObjectName("SecondaryButton")
        self.restore_defaults_button.setMinimumHeight(32)

        bottom_layout.addWidget(self.help_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.restore_defaults_button)

        layout.addLayout(bottom_layout)

        self.run_startup_check.setProperty("settings_key", "General/run_on_startup")
        self.cb_hit_testing.setProperty("settings_key", "General/hit_testing_enabled")
        self.cb_hint_panel.setProperty("settings_key", "General/hint_panel_enabled")
        self.cb_cursor_magnifier.setProperty(
            "settings_key", "General/cursor_magnifier_enabled"
        )
        self.cb_capture_cursor.setProperty(
            "settings_key", "General/win_mouse_capture_enabled"
        )
        self.max_stored_pins.setProperty("settings_key", "General/max_stored_pins")
        self.log_level_combo.setProperty("settings_key", "General/log_level")

        # ======================================================
        # Connections
        # ======================================================
        for checkbox in (
            self.run_startup_check,
            self.cb_hit_testing,
            self.cb_hint_panel,
            self.cb_cursor_magnifier,
            self.cb_capture_cursor,
        ):
            checkbox.toggled.connect(
                lambda value, widget=checkbox: self._setting_changed(widget, value)
            )

        self.log_level_combo.currentTextChanged.connect(
            lambda value: self._setting_changed(self.log_level_combo, value)
        )
        self.max_stored_pins.valueChanged.connect(
            lambda value: self._setting_changed(self.max_stored_pins, value)
        )

        self.open_log_button.clicked.connect(self.open_log_requested.emit)
        self.open_config_button.clicked.connect(
            lambda: self.open_config_requested.emit(self.config_path_edit.text())
        )
        self.change_config_button.clicked.connect(self.change_config_requested.emit)
        self.restore_defaults_button.clicked.connect(
            self.restore_defaults_requested.emit
        )
        self.help_button.clicked.connect(self.help_requested.emit)

        # ======================================================
        # Initial data
        # ======================================================
        self.refresh_data(self.settings_data)

        # self.setStyleSheet("""
        #     QGroupBox#SettingsCard {
        #         background: #FFFFFF;
        #         border: 1px solid #E4E4E7;
        #         border-radius: 8px;
        #         margin-top: 10px;
        #         font-weight: 600;
        #     }
        #     QGroupBox#SettingsCard::title {
        #         subcontrol-origin: margin;
        #         subcontrol-position: top left;
        #         border-radius: 8px;
        #         left: 12px;
        #         padding: 0 5px;
        #         color: #27272A;
        #         background: #FFFFFF;
        #     }
        #     QCheckBox {
        #         color: #303030;
        #         spacing: 6px;
        #     }

        #     QCheckBox:hover {
        #         color: #0078d4;
        #     }

        #     QCheckBox:checked {
        #         color: #303030;
        #     }

        #     QCheckBox:checked:hover {
        #         color: #0078d4;
        #     }

        #     QComboBox,
        #     QSpinBox,
        #     QLineEdit {
        #         padding-left: 8px;
        #         padding-right: 8px;
        #         background: #FFFFFF;
        #         border: 1px solid #D4D4D8;
        #         border-radius: 6px;
        #         selection-background-color: #2563EB;
        #     }

        #     QComboBox:hover,
        #     QSpinBox:hover,
        #     QLineEdit:hover {
        #         border-color: #A1A1AA;
        #     }

        #     QComboBox:focus,
        #     QSpinBox:focus,
        #     QLineEdit:focus {
        #         border: 1px solid #2563EB;
        #     }

        #     QLineEdit:read-only {
        #         background: #F7F7F8;
        #         color: #52525B;
        #     }

        #     QPushButton#HelpButton {
        #         padding: 0;
        #         border-radius: 15px;
        #         font-weight: 600;
        #     }
        #     QPushButton {
        #         color: #27415D;
        #         background: #FFFFFF;
        #         border: 1px solid #D5E1EE;
        #         border-radius: 8px;
        #         font-size: 12px;
        #         padding-left: 14px;
        #         padding-right: 14px;
        #     }

        #     QPushButton:hover {
        #         background: #EAF4FF;
        #         border-color: #A9D4F4;
        #     }

        # """)

    def _apply_style(self) -> None:
        """
        Apply a fixed light palette/theme to this tab.

        This keeps the settings page visually consistent regardless of the
        Windows light/dark theme while allowing Fusion to draw native
        controls such as the QCheckBox tick.
        """

        self.setStyleSheet("""
            QWidget#GeneralTab {
                /*background-color: #f7f7f8;*/
                color: #303030;
                font-size: 14px;
            }

            /* --------------------------------------------------
            Cards
            -------------------------------------------------- */

            QGroupBox#SettingsCard {
                background-color: transparent;
                color: #303030;
                border: 1px solid #d9dce1;
                border-radius: 7px;
                margin-top: 10px;
                padding-top: 8px;
                font-weight: 600;
            }

            QGroupBox#SettingsCard::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0px 6px;
                background-color: #ffffff;
                color: #303030;
                border: 1px solid #d9dce1;
                border-radius: 4px;
            }

            /* --------------------------------------------------
            Labels
            -------------------------------------------------- */

            QLabel {
                background-color: transparent;
                color: #303030;
            }

            QLabel#PageDescription {
                color: #5f6368;
            }

            QLabel#SecondaryText {
                color: #73777d;
            }

            QWidget#TransparentWidget {
                background-color: transparent;
            }

            /* --------------------------------------------------
            Check boxes

            IMPORTANT:
            Do NOT style QCheckBox::indicator here.

            This allows Fusion to continue drawing the native
            checkbox and tick.
            -------------------------------------------------- */

            QCheckBox {
                background-color: transparent;
                color: #303030;
                spacing: 6px;
            }
            QCheckBox:hover {
                color: #303030;
            }

            QCheckBox:disabled {
                color: #9a9da3;
            }
            QCheckBox::indicator:disabled {
                border-color: #d1d3d4; 
                background-color: #f1f2f3;
            }
            QCheckBox::indicator:checked:disabled {
                background-color: #b0b3b8;
                border-color: #b0b3b8;
            }
            QCheckBox::indicator {
                border: 1px solid #5c5c5c;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #0078d4;
            }
            QCheckBox::indicator:checked {
                border-color: #0078d4;
                background-color: #0078d4;
            }
            /* --------------------------------------------------
            Combo box
            -------------------------------------------------- */

            QComboBox {
                min-height: 24px;
                background-color: #ffffff;
                color: #303030;
                border: 1px solid #b8bcc4;
                border-radius: 5px;
                padding: 2px 24px 2px 7px;
            }
            QComboBox:hover {
                border-color: #8c919a;
            }
            QComboBox:focus {
                border: 1px solid #4a90e2;
            }
            QComboBox:disabled {
                background-color: #f1f1f2;
                color: #9a9da3;
                border-color: #d3d5d9;
            }
            QComboBox::drop-down {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #303030;
                border: 1px solid #b8bcc4;
                selection-background-color: #e8f2ff;
                selection-color: #303030;
                outline: 0;
            }

            /* --------------------------------------------------
            Line edit
            -------------------------------------------------- */

            QLineEdit {
                background-color: #ffffff;
                color: #303030;

                border: 1px solid #b8bcc4;
                border-radius: 5px;

                padding: 4px 7px;

                selection-background-color: #4a90e2;
                selection-color: #ffffff;
            }

            QLineEdit:hover {
                border-color: #8c919a;
            }

            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }

            QLineEdit:disabled {
                background-color: #f1f1f2;
                color: #9a9da3;
                border-color: #d3d5d9;
            }

            /* --------------------------------------------------
            Spin box
            -------------------------------------------------- */

            QSpinBox {
                background-color: #ffffff;
                color: #303030;
                border: 1px solid #b8bcc4;
                border-radius: 5px;
                /*padding: 0px 6px;*/
                padding-left: 5px;
                padding-right: 5px; 
            }

            QSpinBox:hover {
                border-color: #8c919a;
            }

            QSpinBox:focus {
                border: 1px solid #4a90e2;
            }

            QSpinBox:disabled {
                background-color: #f1f1f2;
                color: #9a9da3;
                border-color: #d3d5d9;
            }

            QSpinBox::up-button,
            QSpinBox::down-button {
                width: 20px;
                subcontrol-origin: border; 
            }

            QSpinBox::up-button {
                subcontrol-position: top right;
                right: 2px; 
                top: 2px;
            }

            QSpinBox::down-button {
                subcontrol-position: bottom right;
                right: 2px; 
                bottom: 2px;

            }

            /* --------------------------------------------------
            Secondary buttons
            -------------------------------------------------- */

            QPushButton#SecondaryButton {
                background-color: #ffffff;
                color: #303030;
                border: 1px solid #b8bcc4;
                border-radius: 5px;
                padding: 4px 10px;
            }

            QPushButton#SecondaryButton:hover {
                /*background-color: #f5f7fa;
                border-color: #8c919a;*/
                background: #EAF4FF;
                border-color: #A9D4F4;
            }

            QPushButton#SecondaryButton:pressed {
                background-color: #e9ecf1;
            }

            QPushButton#SecondaryButton:disabled {
                background-color: #f1f1f2;
                color: #9a9da3;
                border-color: #d3d5d9;
            }

            /* --------------------------------------------------
            Help button
            -------------------------------------------------- */

            QPushButton#HelpButton {
                background-color: #ffffff;
                color: #50545a;

                border: 1px solid #b8bcc4;
                border-radius: 16px;

                font-weight: 600;
            }

            QPushButton#HelpButton:hover {
                background-color: #f0f6ff;
                color: #2878c8;
                border-color: #4a90e2;
            }

            QPushButton#HelpButton:pressed {
                background-color: #e2efff;
            }
        """)

    def _setting_changed(self, widget, value):
        key = widget.property("settings_key")
        if not key:
            return

        self.settings_changed.emit(key, value)

    # ==========================================================
    # Data
    # ==========================================================
    def refresh_data(self, settings):
        self.settings_data = settings

        widgets = [
            self.run_startup_check,
            self.cb_hint_panel,
            self.cb_hit_testing,
            self.cb_cursor_magnifier,
            self.cb_capture_cursor,
            self.log_level_combo,
            self.max_stored_pins,
            self.config_path_edit,
        ]

        for widget in widgets:
            widget.blockSignals(True)

        index = self.log_level_combo.findText(settings.get("log_level", "Info"))
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)

        self.run_startup_check.setChecked(settings.get("run_on_startup", False))
        self.cb_hit_testing.setChecked(settings.get("hit_testing_enabled", False))
        self.cb_hint_panel.setChecked(settings.get("hint_panel_enabled", False))
        self.cb_cursor_magnifier.setChecked(
            settings.get("cursor_magnifier_enabled", False)
        )
        self.cb_capture_cursor.setChecked(settings.get("capture_cursor_enabled", False))

        self.max_stored_pins.setValue(settings.get("max_stored_pins", 10))
        self.config_path_edit.setText(settings.get("config_path", "snipin.ini"))

        for widget in widgets:
            widget.blockSignals(False)

    def get_data(self):
        return {
            "run_on_startup": self.run_startup_check.isChecked(),
            "hit_testing_enabled": self.cb_hit_testing.isChecked(),
            "hint_panel_enabled": self.cb_hint_panel.isChecked(),
            "cursor_magnifier_enabled": self.cb_cursor_magnifier.isChecked(),
            "capture_cursor_enabled": self.cb_capture_cursor.isChecked(),
            "win_mouse_capture_enabled": False,
            "max_stored_pins": self.max_stored_pins.value(),
            "log_level": self.log_level_combo.currentText(),
            "config_path": self.config_path_edit.text(),
        }


# ============================================
# TEST CODE
# ============================================
class SnipastePreferences(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Snipaste Preferences")
        self.setFixedSize(450, 580)

        self.init_ui()

        self.setStyleSheet("""
            QDialog {
                background: #F7F8FA;
                color: #202124;
                font-size: 13px;
            }
            QWidget {
                color: #202124;
                font-size: 13px;
            }
            QWidget#TransparentWidget {
                background: transparent;
            }
            QLabel#PageTitle {
                font-size: 22px;
                font-weight: 600;
                color: #18181B;
            }
            QLabel#PageDescription,
            QLabel#SecondaryText {
                color: #71717A;
                font-size: 12px;
            }
            QGroupBox#SettingsCard {
                background: #FFFFFF;
                border: 1px solid #E4E4E7;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: 600;
            }
            QGroupBox#SettingsCard::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 5px;
                color: #27272A;
                background: #FFFFFF;
            }
            QCheckBox {
                spacing: 8px;
                min-height: 24px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }

            QComboBox,
            QSpinBox,
            QLineEdit {
                min-height: 30px;
                padding-left: 8px;
                padding-right: 8px;
                background: #FFFFFF;
                border: 1px solid #D4D4D8;
                border-radius: 6px;
                selection-background-color: #2563EB;
            }

            QComboBox:hover,
            QSpinBox:hover,
            QLineEdit:hover {
                border-color: #A1A1AA;
            }

            QComboBox:focus,
            QSpinBox:focus,
            QLineEdit:focus {
                border: 1px solid #2563EB;
            }

            QLineEdit:read-only {
                background: #F7F7F8;
                color: #52525B;
            }

            QPushButton {
                min-height: 30px;

                padding-left: 14px;
                padding-right: 14px;

                background: #FFFFFF;

                border: 1px solid #D4D4D8;
                border-radius: 6px;

                color: #27272A;
            }

            QPushButton:hover {
                background: #F4F4F5;
                border-color: #A1A1AA;
            }

            QPushButton:pressed {
                background: #E4E4E7;
            }

            QPushButton#HelpButton {
                min-width: 30px;
                max-width: 30px;

                padding: 0;

                border-radius: 15px;

                font-weight: 600;
            }
            
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        tab_widget = QTabWidget()
        self.snip_tab = GeneralTab()

        tab_widget.addTab(self.snip_tab, "Snip")  # 傳入封裝後的對象
        tab_widget.setCurrentIndex(1)
        main_layout.addWidget(tab_widget)
        # bottom_layout = QHBoxLayout()
        # bottom_layout.addStretch()
        # self.btn_restore = QPushButton("Restore Defaults")
        # bottom_layout.addWidget(self.btn_restore)
        # main_layout.addLayout(bottom_layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    app.setStyle(QStyleFactory.create("Fusion"))
    prefs = SnipastePreferences()
    prefs.show()
    sys.exit(app.exec())
