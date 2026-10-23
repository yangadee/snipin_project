from PyQt6.QtWidgets import (
    QStyle,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QMessageBox,
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QAction, QKeySequence
from ctypes import wintypes
from utils.key_mapper import KeyMapper
import ctypes


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class HotkeyCaptureEdit_Robust(QLineEdit):
    """
    Uses Qt's standard internal Event Filter to bypass IME blocks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            HotkeyCaptureEdit_Robust {
                background-color: white;
                color: black;
                border: 1px solid #cccccc;
                padding: 3px;
                border-radius: 5px;
            }

            HotkeyCaptureEdit_Robust:focus {
                background-color: #e8f2ff;
                border: 1px solid #80bfff;
            }

            HotkeyCaptureEdit_Robust[hotkeyError="true"] {
                border: 1px solid #cc0000;
                color: #cc0000;
            }

            HotkeyCaptureEdit_Robust:disabled {
                /*background-color: #eeeeee;*/
                /*color: #888888;*/
                background: #EEF2F6;
                border-color: #DFE6EE;
                border: 1px solid #d0d0d0;
            }

            HotkeyCaptureEdit_Robust[hotkeyError="true"]:disabled {
                background-color: #eeeeee;
                color: #888888;
                border: 1px solid #d0d0d0;
            }
        """)

        self.setReadOnly(True)
        self.setPlaceholderText("Press keys...")
        self.installEventFilter(self)

        self.mapper = KeyMapper()
        self._error = False

        # ======================================================
        # Clear hotkey action
        # ======================================================
        self.clear_action = QAction(self)
        self.clear_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)
        )
        self.clear_action.setToolTip("Clear hotkey")
        self.addAction(self.clear_action, QLineEdit.ActionPosition.TrailingPosition)
        self.clear_action.triggered.connect(self.clear)

        # # Only show X when a hotkey exists
        # self.textChanged.connect(lambda text: self.clear_action.setVisible(bool(text)))
        # self.clear_action.setVisible(bool(self.text()))

    def focusInEvent(self, event):
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

    def set_error(self, error: bool):
        """Set highlight when hotkey is not available."""
        self._error = error

        self.setProperty("hotkeyError", error)

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def eventFilter(self, obj, event):
        """
        Intercepts Qt UI events before they are consumed by the widget.
        Guaranteed to catch all key presses cleanly.
        """
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            # Ctrl, Shift, Alt
            if key in (
                Qt.Key.Key_Control,
                Qt.Key.Key_Shift,
                Qt.Key.Key_Alt,
                Qt.Key.Key_Meta,  # Windows  Meta
                Qt.Key.Key_Super_L,  # Left Windows Key (LWIN)
                Qt.Key.Key_Super_R,  # Right Windows Key (RWIN)
            ):
                return True  # Consume to prevent standard behavior

            # Ctrl, Shift, Alt）
            combo_parts = []
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                combo_parts.append("Ctrl")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                combo_parts.append("Shift")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                combo_parts.append("Alt")
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                combo_parts.append("Win")  # 完美輸出 "Win" 字串

            # Process F1~F12, Backtick
            key_text = QKeySequence(key).toString()

            # correct Qt turn "~" to "QuoteLeft"
            if key == Qt.Key.Key_QuoteLeft:
                key_text = "QuoteLeft"
            elif key == Qt.Key.Key_Escape:
                key_text = "Escape"

            # convert to hotkey sequence（e.g：Ctrl+Shift+F1）
            if key_text:
                combo_parts.append(key_text)
                final_string = "+".join(combo_parts)
                self.setText(final_string)
                # self.setFocus()
                # self.clearFocus()

            return True

        # Pass other's action
        return super().eventFilter(obj, event)


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QMessageBox,
)


class HotkeysTab(QWidget):
    settings_changed = pyqtSignal(object, str)
    key_bindings_requested = pyqtSignal()

    def __init__(self, hotkeys_dict, parent=None):
        super().__init__(parent)

        self.hotkeys_data = hotkeys_dict
        self.editors = {}
        self.status_labels = {}
        self._hotkey_tester = None

        # ======================================================
        # Main layout
        # ======================================================
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # ======================================================
        # Description
        # ======================================================
        info = QLabel("Click a field, then press the shortcut you want.")
        info.setWordWrap(True)

        layout.addWidget(info)
        layout.addSpacing(4)
        # ======================================================
        # Hotkey form
        # ======================================================
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.addLayout(form)

        # ======================================================
        # Hotkey rows
        # ======================================================
        for action_id, hotkey_text in hotkeys_dict.items():
            # --------------------------------------------------
            # Label
            # --------------------------------------------------
            label_text = action_id.replace("_", " ").title()

            label = QLabel(label_text)
            label.setMinimumWidth(150)

            # --------------------------------------------------
            # Editor
            # --------------------------------------------------
            editor = HotkeyCaptureEdit_Robust()
            editor.setText(hotkey_text)
            editor.setEnabled(False)

            editor.setMinimumWidth(220)
            editor.setMinimumHeight(30)

            # --------------------------------------------------
            # Status
            # --------------------------------------------------
            status = QLabel("✓")
            status.setFixedWidth(24)
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status.setStyleSheet("""
                color: #22A447;
                font-size: 16px;
                font-weight: 600;
                """)

            # --------------------------------------------------
            # Field
            # --------------------------------------------------
            field_widget = QWidget()
            field_layout = QHBoxLayout(field_widget)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(8)
            field_layout.addWidget(editor, 1)
            field_layout.addWidget(status)
            form.addRow(label, field_widget)

            # --------------------------------------------------
            # Store
            # --------------------------------------------------
            self.editors[action_id] = editor
            self.status_labels[action_id] = status

            # --------------------------------------------------
            # Signal
            # --------------------------------------------------
            editor.textChanged.connect(
                lambda text, aid=action_id, e=editor: self._on_hotkey_changed(
                    aid,
                    e,
                    text,
                )
            )

        # ======================================================
        # Spacer
        # ======================================================
        layout.addStretch(1)

        # ======================================================
        # Bottom controls
        # ======================================================
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 2, 0, 0)

        self.key_bindings_button = QPushButton("Key Bindings")
        self.key_bindings_button.setMinimumSize(120, 50)
        bottom_layout.addWidget(self.key_bindings_button)
        bottom_layout.addStretch(1)
        layout.addLayout(bottom_layout)
        # ======================================================
        # Signals
        # ======================================================
        self.key_bindings_button.clicked.connect(self.on_key_bindings_requested)

        # ======================================================
        # Initial validation
        # ======================================================
        self._update_all_status()
        self._apply_style()

    def on_key_bindings_requested(self):
        self.key_bindings_requested.emit()
        self.key_bindings_button.setEnabled(False)
        for editor in self.editors.values():
            editor.setEnabled(True)

    def _on_hotkey_changed(self, action_id, editor, text):
        self._update_all_status()
        self.settings_changed.emit(editor, text)

    def set_hotkey_tester(self, callback):
        """Set callback: callback(hotkey_seq) -> (ok, message)."""
        self._hotkey_tester = callback

    def _update_hotkey_status(
        self,
        action_id,
        hotkey,
    ):
        status = self.status_labels[action_id]

        if not hotkey:
            status.setText("")
            status.setToolTip("No hotkey assigned")
            return

        # ----------------------------------------------
        # Duplicate check inside the settings dialog
        # ----------------------------------------------
        data = self.get_data()

        duplicate = sum(value == hotkey for value in data.values()) > 1

        if duplicate:
            status.setText("✕")
            status.setStyleSheet("color: #d13438; font-weight: bold;")
            status.setToolTip("Duplicate hotkey")
            return

        # ----------------------------------------------
        # Ask HotkeyManager test service
        # ----------------------------------------------
        if self._hotkey_tester is not None:
            ok, message = self._hotkey_tester(hotkey)
            if not ok:
                status.setText("✕")
                status.setStyleSheet("color: #d13438; font-weight: bold;")
                status.setToolTip(message)
                return

        # ----------------------------------------------
        # Everything OK
        # ----------------------------------------------
        status.setText("✓")
        status.setStyleSheet("color: #22a447; font-weight: bold;")
        status.setToolTip("Hotkey available")

    def _update_all_status(self):
        for action_id, editor in self.editors.items():
            self._update_hotkey_status(
                action_id,
                editor.text(),
            )

    def refresh_data(self, new_hotkeys_dict):
        self.hotkeys_data = new_hotkeys_dict
        for action_id, editor in self.editors.items():
            if action_id in new_hotkeys_dict:
                latest_text = new_hotkeys_dict[action_id]
                editor.blockSignals(True)
                editor.setText(latest_text)
                editor.setEnabled(False)
                editor.blockSignals(False)
        self.key_bindings_button.setEnabled(True)
        self._update_status_icons()

    def _update_status_icons(self):
        """
        ✓ valid
        ✕ duplicate
        blank for empty hotkey
        """

        data = self.get_data()
        # Count hotkey usage
        counts = {}
        for hotkey in data.values():
            hotkey = hotkey.strip()
            if hotkey:
                counts[hotkey] = counts.get(hotkey, 0) + 1

        # Update indicators
        for action_id, hotkey in data.items():
            status = self.status_labels[action_id]
            hotkey = hotkey.strip()
            if not hotkey:
                status.setText("✕")
                status.setStyleSheet("""
                    QLabel {
                        color: #d13438;
                        font-size: 16px;
                        font-weight: bold;
                    }
                    """)
                status.setToolTip("Duplicate hotkey")

            else:
                status.setText("✓")
                status.setStyleSheet("""
                    QLabel {
                        color: #22a447;
                        font-size: 16px;
                        font-weight: bold;
                    }
                    """)
                status.setToolTip("Hotkey is valid")

    def get_data(self):
        hotkeys = {}
        for action_id, editor in self.editors.items():
            hotkeys[action_id] = editor.text()

        return hotkeys

    def validate(self):
        data = self.get_data()
        reverse = {}
        duplicates = []
        for action_id, hotkey in data.items():
            if not hotkey:
                continue
            if hotkey in reverse:
                duplicates.append((reverse[hotkey], action_id, hotkey))
            else:
                reverse[hotkey] = action_id
        if duplicates:
            msg = "Duplicated hotkeys found:\n\n"
            for first, second, hotkey in duplicates:
                msg += f"{hotkey} -> {first} / {second}\n"
            QMessageBox.warning(self, "Duplicate Hotkeys", msg)
            return False
        return True

    def _apply_style(self):
        self.setStyleSheet("""
            QWidget#HotkeysTab {
                color: #303030;
                font-size: 14px;
            }
            QPushButton {
                min-width: 70px;
                min-height: 30px;
                padding: 4px 10px;
                border: 1px solid #D5E1EE;
                border-radius: 8px;
                background: white;
                color: #27415D;
            }
            QPushButton:hover {
                background: #EAF4FF;
                border-color: #A9D4F4;
            }
            """)
