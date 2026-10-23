from PyQt6.QtWidgets import QWidgetAction, QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import QObject, Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon


class TrayAction(QWidgetAction):
    triggered = pyqtSignal()
    toggled = pyqtSignal(bool)

    def __init__(
        self,
        text: str = "",
        status: str = "",
        icon: QIcon | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._text = text
        self._status = status
        self._icon = QIcon()
        self._checkable = False
        self._checked = False
        self._widget = QWidget()
        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(15)
        # Check mark
        self._check = QLabel()
        self._check.setFixedWidth(20)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Icon
        self._icon_label = QLabel()
        self._icon_label.setFixedWidth(20)
        # self._icon_label.setFixedSize(QSize(18, 18))
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Left text
        self._left = QLabel(text)
        # Right status (this is truly right-aligned)
        self._right = QLabel(status)
        self._right.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._right.setStyleSheet("color: #888;")
        layout.addWidget(self._check)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._left)
        layout.addStretch()  # ← this pushes status to the right
        layout.addWidget(self._right)
        self.setDefaultWidget(self._widget)
        self._widget.mousePressEvent = self._on_click

        self._update_check()
        # Apply
        if icon is not None:
            self.setIcon(icon)
        self._apply_style()
        self._update_leading()

    def _apply_style(self):
        self._widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
                padding: 0px 0px;
                margin: 1px 0px;
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: #e5f1fb;
                color: #0066cc;
            }
        """)

    # ---- Public API ----
    def setText(self, text: str):
        self._text = text
        self._left.setText(text)

    def text(self) -> str:
        return self._text

    def setIcon(self, icon: QIcon):
        if self._checkable:
            return
        self._icon = icon
        self._icon_label.setPixmap(
            icon.pixmap(QSize(20, 20)) if not icon.isNull() else QIcon().pixmap(20, 20)
        )
        self._update_leading()

    def setCheckable(self, checkable: bool):
        self._checkable = checkable
        self._update_check()
        self._update_leading()

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._update_check()
            self.toggled.emit(checked)

    def isChecked(self) -> bool:
        return self._checked

    def setStatus(self, status: str, color: str = "#888"):
        self._status = status
        self._right.setText(status)
        self._right.setStyleSheet(f"color: {color};")

    def status(self) -> str:
        return self._status

    def _update_leading(self):
        # has_icon = not getattr(self, "_icon").isNull()
        if self._checkable:
            self._update_check()
            self._check.show()
            self._icon_label.hide()
        else:
            self._icon_label.show()
            self._check.hide()

    def _update_check(self):
        if not self._checkable:
            self._check.clear()
        else:
            self._check.setText("✓" if self._checked else "")
            self._check.setStyleSheet(
                "color: #2ecc71; font-weight: bold;" if self._checked else ""
            )

    def _on_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._checkable:
                self.setChecked(not self._checked)
            self.triggered.emit()
