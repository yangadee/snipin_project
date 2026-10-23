from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class UserGuideTab(QWidget):
    """Compact, read-only guide designed for the Snipin settings dialog."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("userGuideTab")
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 4)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("guideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        content = QWidget(scroll)
        content.setObjectName("guideContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 10, 12)
        layout.setSpacing(12)

        # title = QLabel("Quick guide", content)
        # title.setObjectName("guideTitle")
        # layout.addWidget(title)

        intro = QLabel(
            "Capture, annotate, pin, and look up content without "
            "leaving your workflow.",
            content,
        )
        intro.setObjectName("guideIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._section("CAPTURE & ANNOTATE", content))
        layout.addWidget(
            self._card(
                content,
                "Snip and mark up",
                "Start with your configured snip hotkey. Select an area, "
                "then use the toolbar to draw, add text, or highlight details.",
                badge="BASIC SNIP",
            )
        )

        layout.addWidget(
            self._card(
                content,
                "Pin to windows",
                "Pin a captured image to keep it visible while working "
                "in other windows.",
                badge="PIN",
            )
        )

        layout.addWidget(self._section("IMAGE SCAN / OCR", content))

        layout.addWidget(
            self._card(
                content,
                "Copy recognized text",
                "Snip an area containing text, use OCR to recognize, then copy the "
                "recognized text to the clipboard for use in any application.",
                badge="OCR → CLIPBOARD",
            )
        )

        layout.addWidget(
            self._card(
                content,
                "Lookup based on image scan recognized reference",
                "Snip a screen area and use OCR to recognize an internal reference, "
                "Search for a service order, material 12NC, procedure name, "
                "procedure ID, or AIR ID...",
                badge="OCR → FINDIT & SAP LOOKUP",
                accent="purple",
            )
        )
        layout.addWidget(self._section("HOTKEY LOOKUPS", content))
        layout.addWidget(
            self._card(
                content,
                "Lookup based on Selected text + Hotkey (Ctrl+W)",
                "Seletect interesting text and recognize an internal reference, "
                "Search for a service order, material 12NC, procedure name, "
                "procedure ID, or AIR ID...",
                badge="HOTKEY (CTRL+W) → FINDIT & SAP LOOKUP",
            )
        )

        layout.addWidget(self._section("QUICK MOUSE GESTURES", content))

        gesture_row = QWidget(content)
        gesture_layout = QHBoxLayout(gesture_row)
        gesture_layout.setContentsMargins(0, 0, 0, 0)
        gesture_layout.setSpacing(10)

        gesture_layout.addWidget(
            self._card(
                gesture_row,
                "Win + left drag",
                "Hold Win and drag with the left mouse button " "to snip on the fly.",
                badge="QUICK SNIP",
            ),
            1,
        )
        gesture_layout.addWidget(
            self._card(
                gesture_row,
                "Win + right drag",
                "Hold Win and drag with the right mouse button "
                "to search ASML internal content.",
                badge="QUICK SEARCH",
                accent="purple",
            ),
            1,
        )

        layout.addWidget(gesture_row)

        note = QLabel(
            "Hotkeys and available plugin actions depend on your "
            "Snipin configuration.",
            content,
        )
        note.setObjectName("guideNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        scroll.setWidget(content)

    @staticmethod
    def _section(text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("guideSection")
        return label

    @staticmethod
    def _card(
        parent: QWidget,
        title: str,
        description: str,
        *,
        badge: str,
        accent: str = "blue",
    ) -> QFrame:
        card = QFrame(parent)
        card.setObjectName("guideCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(5)

        badge_label = QLabel(badge, card)
        badge_label.setObjectName(
            "guideBadgePurple" if accent == "purple" else "guideBadgeBlue"
        )
        layout.addWidget(
            badge_label,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        title_label = QLabel(title, card)
        title_label.setObjectName("guideCardTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        description_label = QLabel(description, card)
        description_label.setObjectName("guideCardBody")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        return card

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget#userGuideTab,
            QWidget#guideContent,
            QScrollArea#guideScroll,
            QScrollArea#guideScroll QWidget#qt_scrollarea_viewport {
                background: transparent;
                border: none;
            }

            QLabel#guideTitle {
                color: #192C45;
                font-size: 14px;
                font-weight: 750;
            }

            QLabel#guideIntro {
                color: #64758B;
                font-size: 14px;
            }

            QLabel#guideSection {
                color: #0878D7;
                font-size: 14px;
                font-weight: 750;
                padding-top: 8px;
            }

            QFrame#guideCard {
                background: #FFFFFF;
                border: 1px solid #DEE8F3;
                border-radius: 11px;
            }

            QLabel#guideCardTitle {
                color: #1D3049;
                background: transparent;
                font-size: 14px;
                font-weight: 750;
            }

            QLabel#guideCardBody {
                color: #64758B;
                background: transparent;
                font-size: 11px;
            }

            QLabel#guideBadgeBlue,
            QLabel#guideBadgePurple {
                border-radius: 5px;
                padding: 3px 7px;
                font-size: 11px;
                font-weight: 700;
            }

            QLabel#guideBadgeBlue {
                color: #0878D7;
                background: #EAF4FF;
            }

            QLabel#guideBadgePurple {
                color: #7040CA;
                background: #F1EAFF;
            }

            QLabel#guideNote {
                color: #73869B;
                font-size: 12px;
                padding-top: 5px;
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
