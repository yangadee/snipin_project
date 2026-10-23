from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from core.app_info import AppInfo
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from resources import icon_provider


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ======================================================
        # Header
        # ======================================================
        # header_layout = QHBoxLayout()
        # header_layout.setContentsMargins(0, 0, 0, 0)
        # header_layout.setSpacing(12)

        # title_layout = QVBoxLayout()
        # title_layout.setContentsMargins(0, 0, 0, 0)
        # title_layout.setSpacing(2)

        # title_layout.addWidget(title)
        # title_layout.addWidget(version)

        # header_layout.addLayout(title_layout)
        # header_layout.addStretch()

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # Icon
        icon_label = QLabel()
        icon_label.setPixmap(icon_provider.icon(AppInfo.APPICON).pixmap(64, 64))
        icon_label.setFixedSize(64, 64)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title + version
        title = QLabel(AppInfo.NAME)
        title.setObjectName("AppTitle")
        # font = title.font()
        # font.setPointSize(17)
        # font.setWeight(QFont.Weight.DemiBold)
        # title.setFont(font)
        version = QLabel(f"Version {AppInfo.VERSION}")
        version.setObjectName("AppVersion")
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_layout.addWidget(title)
        title_layout.addWidget(version)

        # Header = icon + title
        header_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)
        self._add_separator(layout)

        # ======================================================
        # Main content
        # ======================================================
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 4, 0, 4)
        content_layout.setSpacing(10)

        # ======================================================
        # Left side: Features
        # ======================================================
        features_widget = QWidget()

        features_layout = QVBoxLayout(features_widget)
        features_layout.setContentsMargins(0, 0, 0, 0)
        features_layout.setSpacing(5)

        features_title = self._section_title("⚙️ Key Features")
        features_layout.addWidget(features_title)
        features_layout.addSpacing(2)

        for feature in AppInfo.FEATURES:
            row = QHBoxLayout()
            row.setContentsMargins(2, 0, 0, 0)
            row.setSpacing(8)

            bullet = QLabel("•")
            bullet.setFixedWidth(10)
            bullet.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
            )

            text = QLabel(str(feature))
            text.setObjectName("featureText")
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            row.addWidget(bullet)
            row.addWidget(text, 1)

            features_layout.addLayout(row)

        features_layout.addStretch(1)

        # ======================================================
        # Center separator
        # ======================================================
        center_separator = QFrame()
        center_separator.setFrameShape(QFrame.Shape.VLine)
        center_separator.setFrameShadow(QFrame.Shadow.Sunken)

        # ======================================================
        # Right side: About this application
        # ======================================================
        info_widget = QWidget()
        info_widget.setMinimumWidth(180)

        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)

        info_layout.addWidget(self._section_title("ℹ️ About This Application"))
        info_layout.addSpacing(2)

        info_form = QFormLayout()
        info_form.setContentsMargins(0, 0, 0, 0)
        info_form.setHorizontalSpacing(18)
        info_form.setVerticalSpacing(8)

        info_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        info_form.addRow("Product", self._value_label(AppInfo.NAME))
        info_form.addRow("Version", self._value_label(AppInfo.VERSION))
        info_form.addRow("Platform", self._value_label(AppInfo.PLATFORM))
        info_layout.addLayout(info_form)
        info_layout.addSpacing(10)
        description = self._value_label(AppInfo.DESCRIPTION)
        description.setWordWrap(True)
        description.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        info_layout.addWidget(description)
        info_layout.addStretch(1)

        # ======================================================
        # Assemble columns
        # ======================================================
        content_layout.addWidget(features_widget, 3)
        content_layout.addWidget(center_separator)
        content_layout.addWidget(info_widget, 2)

        layout.addLayout(content_layout, 1)

        # ======================================================
        # Disclaimer
        # ======================================================
        self._add_separator(layout)

        disclaimer_layout = QVBoxLayout()
        disclaimer_layout.setContentsMargins(0, 0, 0, 0)
        disclaimer_layout.setSpacing(6)

        disclaimer_title = self._section_title("Disclaimer")

        disclaimer_text = QLabel(AppInfo.DISCLAIMER.strip())
        disclaimer_text.setWordWrap(True)
        disclaimer_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        disclaimer_layout.addWidget(disclaimer_title)
        disclaimer_layout.addWidget(disclaimer_text)

        layout.addLayout(disclaimer_layout)

        # ======================================================
        # Footer
        # ======================================================
        layout.addSpacing(4)

        footer = QLabel(f"© {AppInfo.COPYRIGHT}  •  Internal Use Only")
        footer.setObjectName("Footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    def _apply_style(self):
        self.setStyleSheet("""
            QWidget {
                font-size: 12px;
                color: #303030;
            }
            QLabel#AppTitle {
                font-size: 17px;
                font-weight: 600;
            }
            QLabel#AppVersion {
                font-size: 12px;
                color: #707070;
            }
            QLabel#SectionTitle {
                font-size: 14px;
                font-weight: 700;
                color: #303030;
            }
            QLabel#featureText {
                font-size: 14px;
            }
            QLabel#ValueLabel {
                font-size: 14px;
                color: #303030;
            }
            QLabel#Footer {
                font-size: 12px;
                color: #707070;
            }
        """)

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _section_title(text):
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    @staticmethod
    def _value_label(text):
        label = QLabel(str(text))
        label.setObjectName("ValueLabel")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _add_separator(layout):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        layout.addWidget(separator)
