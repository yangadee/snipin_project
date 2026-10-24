# lookup_popup.py
from __future__ import annotations
from dataclasses import dataclass
import math
import sys

import os


from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, QUrl, pyqtSignal, QRectF
from PyQt6.QtGui import (
    QCursor,
    QDesktopServices,
    QFontMetricsF,
    QColor,
    QGuiApplication,
    QPainter,
    QPen,
    QScreen,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
    QToolButton,
    QTextEdit,
    QSizePolicy,
    QAbstractItemView,
    QStackedWidget,
)


from plugins.shared.findit import Findit, FindItResult
from plugins.shared.helpers import extract_items, extract_search_items
from plugins.shared.sap import SAPController, SAPOptions, SAP_OPERATIONS
from resources.icon_provider import icon_provider as AppIcon
import re


@dataclass(frozen=True)
class SapTransaction:
    code: str  # e.g. "MMBE"
    description: str = ""


class ExpandableEdit(QTextEdit):
    returnPressed = pyqtSignal()

    def __init__(self, parent=None, max_lines=4):
        super().__init__(parent)

        self._max_lines = max(1, max_lines)

        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Also wrap long IDs that contain no spaces.
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        # self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.textChanged.connect(self._update_height)
        self.document().documentLayout().documentSizeChanged.connect(
            self._update_height
        )

        self._update_height()

    def _update_height(self, *_):
        line_height = self.fontMetrics().lineSpacing()
        margins = 2 * self.document().documentMargin()

        # Include the frame and any stylesheet padding.
        chrome = max(0, self.height() - self.viewport().height())

        collapsed = math.ceil(line_height + margins + chrome)
        maximum = math.ceil(line_height * self._max_lines + margins + chrome)

        if self.hasFocus():
            content_height = self.document().documentLayout().documentSize().height()
            target = min(
                maximum,
                max(collapsed, math.ceil(content_height + chrome)),
            )
        else:
            target = collapsed

        if self.height() != target:
            self.setFixedHeight(target)

    def collapsed_height(self) -> int:
        line_height = self.fontMetrics().lineSpacing()
        margins = 2 * self.document().documentMargin()
        chrome = max(0, self.height() - self.viewport().height())
        return math.ceil(line_height + margins + chrome)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._update_height()
        self.ensureCursorVisible()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._update_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()
        if hasattr(self, "_clear_button"):
            self._update_clear_button()

    def keyPressEvent(self, event):
        # Preserve Enter-to-search behavior instead of inserting a newline.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.returnPressed.emit()
            event.accept()
            return

        super().keyPressEvent(event)

    # Compatibility with your existing search_edit.text()/setText() calls.
    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText(text)

    def setClearButtonEnabled(self, enabled: bool):
        if not hasattr(self, "_clear_button"):
            self._clear_button = QToolButton(self)
            self._clear_button.setText("✕")
            self._clear_button.setToolTip("Clear")
            self._clear_button.setCursor(Qt.CursorShape.ArrowCursor)
            self._clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._clear_button.setFixedSize(22, 22)
            self._clear_button.setStyleSheet("""
                QToolButton {
                    border: none;
                    background: transparent;
                    color: #738399;
                    font-size: 18px;
                    padding: 0;
                }
                QToolButton:hover {
                    color: #1D3049;
                    background: #E5EDF5;
                    border-radius: 5px;
                }
            """)
            self._clear_button.clicked.connect(self._clear_text)
            self.textChanged.connect(self._update_clear_button)

        self._clear_button_enabled = enabled

        # Reserve space so text cannot overlap the button.
        self.setViewportMargins(0, 0, 26 if enabled else 0, 0)
        self._update_clear_button()

    def _clear_text(self):
        self.clear()
        self.setFocus()

    def _update_clear_button(self):
        if not hasattr(self, "_clear_button"):
            return
        visible = (
            self._clear_button_enabled
            and not self.document().isEmpty()
            and not self.isReadOnly()
        )
        self._clear_button.setVisible(visible)
        viewport_rect = self.viewport().geometry()
        x = viewport_rect.right() + 2
        collapsed_h = self.collapsed_height()
        y = (collapsed_h - self._clear_button.height()) // 2
        self._clear_button.move(x, y)
        if visible:
            self._clear_button.raise_()


class Spinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)

        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)

    def _advance(self):
        self._angle = (self._angle + 15) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)

        pen = QPen(QColor("#E5EDF5"), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        pen.setColor(QColor("#397DCE"))
        painter.setPen(pen)
        painter.drawArc(rect, -self._angle * 16, 100 * 16)


# class _FinditSAPUI(QWidget):
#     """
#     Search + FindIt results + available SAP transactions.

#     The widget does not perform a search or automate SAP itself.
#     Connect its signals to your existing search/SAP controller.
#     """

#     search_requested = pyqtSignal(str)
#     # Emitted for non-HTTP(S) links that need your application's handler.
#     findit_link_requested = pyqtSignal(str)

#     def __init__(self, parent: QWidget | None = None):
#         # super().__init__(parent)
#         super().__init__(parent=None)
#         self.setWindowFlag(
#             Qt.WindowType.Popup
#             | Qt.WindowType.FramelessWindowHint
#             | Qt.WindowType.WindowStaysOnTopHint
#             | Qt.WindowType.NoDropShadowWindowHint
#         )
#         # self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
#         self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

#         self.setObjectName("lookupPopup")
#         self._height = 400
#         self._width = 500
#         # self.setMaximumWidth(self._width)
#         # self.setFixedHeight(self._height)
#         # self.resize(self._width, self._height)
#         self.setFixedSize(self._width, self._height)
#         # self.setMinimumSize(760, 440)

#         self._initial_split_applied = False

#         self._build_ui()
#         self._apply_style()
#         self._update_actions()

#         self._sap_busy = False
#         self.sap = SAPController()
#         self.sap.status.connect(self.set_sap_progress)
#         self.sap.error.connect(lambda error: self.finish_sap_open(False, error))
#         self.sap.finished.connect(lambda: self.finish_sap_open(True))

#     def _build_ui(self) -> None:
#         root = QVBoxLayout(self)
#         root.setContentsMargins(0, 0, 0, 0)  # Transparent space around rounded frame
#         root.setSpacing(0)

#         self.window_frame = QFrame(self)
#         self.window_frame.setObjectName("lookupWindowFrame")
#         root.addWidget(self.window_frame)

#         content_layout = QVBoxLayout(self.window_frame)
#         # content_layout.setContentsMargins(0, 0, 0, 0)
#         content_layout.setContentsMargins(10, 5, 10, 14)
#         content_layout.setSpacing(2)

#         # --------------------------------------------------
#         # Header
#         # --------------------------------------------------
#         header = QHBoxLayout()
#         header.setSpacing(12)

#         header.addStretch()

#         close_button = QPushButton("✕", self.window_frame)
#         close_button.setObjectName("lookupCloseButton")
#         close_button.setAutoDefault(False)
#         close_button.setFixedSize(32, 32)
#         close_button.clicked.connect(self.hide)
#         # header.addWidget(close_button)
#         # content_layout.addLayout(header)

#         status_row = QHBoxLayout()
#         status_row.setSpacing(9)

#         self.status_label = QLabel(
#             "Enter a reference to search, or paste text recognized by OCR.", self
#         )
#         self.status_label.setObjectName("statusLabel")
#         status_row.addWidget(self.status_label, Qt.AlignmentFlag.AlignBottom)
#         status_row.addStretch()
#         status_row.addWidget(close_button)
#         content_layout.addLayout(status_row)

#         # --------------------------------------------------
#         # Search bar
#         # --------------------------------------------------
#         search_row = QHBoxLayout()
#         search_row.setSpacing(9)

#         self.search_edit = ExpandableEdit(self)
#         self.search_edit.setObjectName("searchEdit")
#         metrics = QFontMetricsF(self.search_edit.font())
#         self.search_edit.setTabStopDistance(metrics.horizontalAdvance(" ") * 4)
#         self.search_edit.setPlaceholderText(
#             "Search a service order, material 12NC, procedure, AIR ID..."
#         )
#         self.search_edit.setClearButtonEnabled(True)
#         self.search_edit.returnPressed.connect(self._request_search)
#         search_row.addWidget(self.search_edit, 1, Qt.AlignmentFlag.AlignTop)
#         search_row.setSpacing(1)
#         self.search_button = QPushButton("Search", self)
#         # self.search_button.setFixedHeight(self.search_edit.collapsed_height())
#         self.search_button.setObjectName("searchButton")
#         self.search_button.setFixedWidth(70)
#         self.search_button.clicked.connect(self._request_search)
#         search_row.addWidget(self.search_button, 0, Qt.AlignmentFlag.AlignTop)

#         self.findit_button = QPushButton("Findit", self)
#         self.findit_button.setObjectName("searchButton")
#         self.findit_button.setFixedWidth(70)
#         self.findit_button.clicked.connect(self._go_findit)
#         search_row.addWidget(self.findit_button, 0, Qt.AlignmentFlag.AlignTop)

#         content_layout.addLayout(search_row)
#         content_layout.addSpacing(5)
#         # --------------------------------------------------
#         # Exactly two equal-width panels initially
#         # --------------------------------------------------
#         self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
#         self.splitter.setObjectName("resultsSplitter")
#         self.splitter.setChildrenCollapsible(True)
#         self.splitter.setHandleWidth(3)

#         self.findit_panel = self._build_findit_panel()
#         self.sap_panel = self._build_sap_panel()

#         self.splitter.addWidget(self.sap_panel)
#         self.splitter.addWidget(self.findit_panel)

#         self.splitter.setStretchFactor(0, 1)
#         self.splitter.setStretchFactor(1, 1)
#         self.splitter.setSizes([500, 500])

#         content_layout.addWidget(self.splitter, 1)

#     def _apply_style(self) -> None:
#         self.setStyleSheet("""
#             QDialog#lookupPopup {
#                 background: #F4F8FC;
#             }
#             QWidget#lookupPopup {
#                 background: transparent;
#                 border: none;
#             }
#             QFrame#lookupWindowFrame {
#                 background: #F4F8FC; /*#F4F8FC;*/
#                 border: 1px solid #C9DCEC;
#                 border-radius: 16px;
#             }
#             QPushButton#lookupCloseButton {
#                 color: #52657A;
#                 background: transparent;
#                 border: none;
#                 border-radius: 8px;
#                 font-size: 22px;
#                 padding: 0;
#             }
#             QPushButton#lookupCloseButton:hover {
#                 color: #ff0000; /*#172944;*/
#                 background: #E5EEF7;
#             }

#             QLabel#brand {
#                 color: white;
#                 background: #0878D7;
#                 border-radius: 10px;
#                 font-size: 23px;
#                 font-weight: 800;
#             }

#             QLabel#title {
#                 color: #192C45;
#                 font-size: 20px;
#                 font-weight: 750;
#             }
#             QLabel#finditStatus{
#                 font-size: 14px;
#             }
#             QLabel#subtitle,
#             QLabel#panelHint,
#             QLabel#statusLabel {
#                 color: #65788D;
#                 font-size: 12px;
#             }

#             QLineEdit#searchEdit {
#                 min-height: 30px;
#                 padding: 0 6px;
#                 color: #1D3049;
#                 background: white;
#                 border: 1px solid #C8D9E9;
#                 border-radius: 8px;
#                 font-size: 12px;
#             }

#             QLineEdit#searchEdit:focus {
#                 border: 1px solid #0878D7;
#             }
#             ExpandableEdit#searchEdit {
#                 min-height: 30px;
#                 padding: 0 6px;
#                 color: #1D3049;
#                 background: white;
#                 border: 1px solid #C8D9E9;
#                 border-radius: 8px;
#                 font-size: 12px;
#             }

#             ExpandableEdit#searchEdit:focus {
#                 border: 1px solid #0878D7;
#             }
#             QFrame#panel {
#                 background: white;
#                 border: 1px solid #DCE7F1;
#                 border-radius: 13px;
#             }

#             QLabel#panelTitle {
#                 color: #1D3049;
#                 font-size: 13px;
#                 font-weight: 750;
#                 background: transparent;
#             }

#             QLabel#countBadge {
#                 color: #0878D7;
#                 background: #EAF4FF;
#                 border-radius: 7px;
#                 padding: 4px 8px;
#                 font-size: 11px;
#                 font-weight: 700;
#             }
#             QListWidget {
#                 qproperty-iconSize: 15px 15px;
#             }
#             QListWidget#resultList {
#                 background: transparent;
#                 border: none;
#                 outline: none;
#                 color: #253B55;
#                 font-size: 12px;
#             }

#             QListWidget#resultList::item {
#                 padding: 5px 5px;
#                 border: 1px solid #E5EDF5;
#                 border-radius: 8px;
#             }

#             QListWidget#resultList::item:hover {
#                 background: #F2F8FE;
#                 border-color: #C7E0F6;
#             }

#             QListWidget#resultList::item:selected {
#                 color: #153A63;
#                 background: #E7F3FF;
#                 border-color: #9DCDF2;
#             }
#             QSplitter#resultsSplitter::handle {
#                 background-color: #e5e7eb;
#                 margin: 5px 3px;
#                 /*border-left: 4px solid transparent;*/
#                 /*border-right: 4px solid transparent;*/
#                 /*background-clip: content;*/
#             }

#             QSplitter#resultsSplitter::handle:hover {
#                 background-color: #555555;
#             }
#             QPushButton#searchButton {
#                 min-width: 70px;  max-width: 70px;     /* = setFixedWidth(70) */
#                 min-height: 25px;
#                 padding: 0 16px;
#                 color: white;
#                 background: #0878D7;
#                 border: 1px solid #0878D7;
#                 border-radius: 9px;
#                 font-size: 12px;
#                 font-weight: 700;
#             }

#             QPushButton#searchButton:hover{
#                 background: #006CC5;
#             }

#             QPushButton#secondaryButton,
#             QPushButton#primaryButton {
#                 min-height: 20px;
#                 padding: 0 16px;
#                 color: #0878D7;
#                 background: white;
#                 border: 1px solid #B8D9F3;
#                 border-radius: 8px;
#                 font-size: 12px;
#                 font-weight: 700;
#             }

#             QPushButton#secondaryButton:hover,
#             QPushButton#primaryButton:hover{
#                 background: #EAF4FF;
#             }

#             QPushButton#secondaryButton:disabled,
#             QPushButton#primaryButton:disabled {
#                 color: #9BAABD;
#                 background: #EDF2F7;
#                 border-color: #E0E8F0;
#             }

#             QScrollBar:vertical {
#                 width: 9px;
#                 background: transparent;
#             }

#             QScrollBar::handle:vertical {
#                 background: #C9D8E7;
#                 border-radius: 4px;
#                 min-height: 25px;
#             }

#             QScrollBar::add-line:vertical,
#             QScrollBar::sub-line:vertical {
#                 height: 0;
#             }
#             """)

#     def _build_sap_panel(self) -> QFrame:
#         panel = QFrame(self)
#         panel.setObjectName("panel")

#         layout = QVBoxLayout(panel)
#         # layout.setContentsMargins(15, 15, 15, 14)
#         layout.setContentsMargins(5, 5, 5, 5)
#         layout.setSpacing(5)

#         heading = QHBoxLayout()

#         label = QLabel("SAP transactions", panel)
#         label.setObjectName("panelTitle")
#         heading.addWidget(label)

#         heading.addStretch()

#         self.sap_count = QLabel("0 available", panel)
#         self.sap_count.setObjectName("countBadge")
#         heading.addWidget(self.sap_count)

#         layout.addLayout(heading)

#         hint = QLabel(
#             "Click a transaction to open it in SAP.",
#             panel
#         )
#         hint.setObjectName("panelHint")
#         layout.addWidget(hint)

#         # Reuse the Spinner class from the previous answer.
#         status_row = QHBoxLayout()

#         self.sap_spinner = Spinner(panel)
#         self.sap_spinner.hide()
#         status_row.addWidget(self.sap_spinner)

#         self.sap_status = QLabel("", panel)
#         self.sap_status.setObjectName("statusLabel")
#         self.sap_status.setWordWrap(True)
#         self.sap_status.setTextFormat(Qt.TextFormat.PlainText)
#         self.sap_status.hide()
#         status_row.addWidget(self.sap_status, 1)

#         self.sap_list = QListWidget(panel)
#         self.sap_list.setObjectName("resultList")
#         self.sap_list.setSpacing(1)
#         self.sap_list.doubleClicked.connect(self._open_sap_item)

#         # model = self.sap_list.model()
#         # model.rowsInserted.connect(self.check_emptiness)
#         # model.rowsRemoved.connect(self.check_emptiness)

#         layout.addWidget(self.sap_list, 1)
#         layout.addLayout(status_row)
#         return panel

#     def _build_findit_panel(self) -> QFrame:
#         panel = QFrame(self)
#         panel.setObjectName("panel")

#         layout = QVBoxLayout(panel)
#         layout.setContentsMargins(5, 5, 5, 5)
#         layout.setSpacing(5)

#         heading = QHBoxLayout()

#         label = QLabel("FindIt results", panel)
#         label.setObjectName("panelTitle")
#         heading.addWidget(label)
#         heading.addStretch()

#         self.findit_count = QLabel("0 results", panel)
#         self.findit_count.setObjectName("countBadge")
#         heading.addWidget(self.findit_count)

#         layout.addLayout(heading)

#         hint = QLabel("Click a result to open its link.", panel)
#         hint.setObjectName("panelHint")
#         layout.addWidget(hint)

#         # Stack: results OR searching/error status.
#         self.findit_stack = QStackedWidget(panel)
#         layout.addWidget(self.findit_stack, 1)

#         self.findit_list = QListWidget(self.findit_stack)
#         self.findit_list.setObjectName("resultList")
#         self.findit_list.setSpacing(1)
#         self.findit_list.setSelectionMode(
#             QAbstractItemView.SelectionMode.ExtendedSelection
#         )
#         self.findit_list.doubleClicked.connect(self._open_findit_item)
#         self.findit_list.itemSelectionChanged.connect(self._update_actions)

#         model = self.findit_list.model()
#         model.rowsInserted.connect(self.check_emptiness)
#         model.rowsRemoved.connect(self.check_emptiness)

#         self.findit_stack.addWidget(self.findit_list)

#         # Centered status page.
#         self.findit_status_page = QWidget(self.findit_stack)

#         status_layout = QVBoxLayout(self.findit_status_page)
#         status_layout.setContentsMargins(15, 15, 15, 15)
#         status_layout.setSpacing(12)
#         status_layout.addStretch()

#         self.findit_spinner = Spinner(self.findit_status_page)
#         status_layout.addWidget(
#             self.findit_spinner, alignment=Qt.AlignmentFlag.AlignHCenter
#         )

#         self.findit_status_label = QLabel(self.findit_status_page)
#         self.findit_status_label.setObjectName("finditStatus")
#         self.findit_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.findit_status_label.setTextFormat(Qt.TextFormat.PlainText)
#         self.findit_status_label.setWordWrap(True)

#         status_layout.addWidget(self.findit_status_label)
#         status_layout.addStretch()

#         self.findit_stack.addWidget(self.findit_status_page)

#         actions = QHBoxLayout()
#         actions.setSpacing(9)
#         actions.setContentsMargins(10, 0, 10, 0)

#         self.open_button = QPushButton("Open", panel)
#         self.open_button.setObjectName("secondaryButton")
#         self.open_button.clicked.connect(self._open_selected_findit)
#         actions.addWidget(self.open_button)

#         actions.addStretch()

#         self.open_all_button = QPushButton("Open All", panel)
#         self.open_all_button.setObjectName("primaryButton")
#         self.open_all_button.clicked.connect(self._open_all_findit)
#         actions.addWidget(self.open_all_button)

#         layout.addLayout(actions)

#         self.set_findit_status("ready")

#         return panel

#     def _go_findit(self, *_):
#         first_line = self.search_edit.document().firstBlock().text().strip()
#         if not first_line:
#             return
#         url = QUrl(f"https://findit.asml.com/search?q={first_line}")
#         scheme = url.scheme().lower()
#         # Open ordinary web links directly. Route internal/custom schemes
#         # through the application, where you can apply your own rules.
#         if scheme in {"https", "http"} and url.isValid() and url.host():
#             QDesktopServices.openUrl(url)

#     def check_emptiness(self):
#         is_sap_empty = self.sap_list.count() == 0
#         is_findit_empty = self.findit_list.count() == 0
#         half = self.splitter.width() // 2
#         if is_findit_empty:
#             self.splitter.setSizes([self.splitter.width(), 0])
#             self.resize(self._width // 2, self._height)
#         elif is_sap_empty:
#             self.splitter.setSizes([0, self.splitter.width()])
#             self.resize(self._width // 2, self._height)
#         else:
#             self._set_equal_panel_sizes()
#             self.resize(self._width, self._height)
#             # half = self.splitter.width() // 2
#             # self.splitter.setSizes([half, half])
#         # print(f"self.sap_list.count() {self.sap_list.count()}")

#     def set_findit_status(self, state: str, message: str = ""):
#         if state not in ("canceled", "searching", "failed", "ready"):
#             raise ValueError(f"Unknown FindIt state: {state}")

#         if state == "ready":
#             self.findit_stack.setCurrentWidget(self.findit_list)
#             self.findit_spinner.hide()

#             count = self.findit_list.count()
#             self.findit_count.setText(f"{count} results")

#             self._update_actions()
#             return

#         searching = state == "searching"

#         self.findit_status_label.setText(
#             message or ("Searching..." if searching else "Search failed.")
#         )
#         self.findit_status_label.setStyleSheet(
#             "color: #738399;" if searching else "color: #C34242;"
#         )

#         self.findit_spinner.setVisible(searching)
#         self.findit_stack.setCurrentWidget(self.findit_status_page)

#         self.findit_count.setText("Searching..." if searching else "Not found")
#         self.open_button.setEnabled(False)
#         self.open_all_button.setEnabled(False)

#     def begin_sap_open(self) -> bool:
#         """Return False if another SAP operation is already running."""
#         if self._sap_busy:
#             return False
#         self._sap_busy = True

#         # self.search_button.setEnabled(False)
#         # self.search_edit.setEnabled(False)
#         self.sap_list.setEnabled(False)

#         self.sap_status.setText("Opening SAP...")
#         self.sap_status.setStyleSheet("color: #738399;")
#         self.sap_status.show()
#         self.sap_spinner.show()
#         QApplication.processEvents()

#         return True

#     def set_sap_progress(self, message: str):
#         if self._sap_busy:
#             self.sap_status.setText(message)

#     def finish_sap_open(self, success: bool = True, message: str = ""):
#         self._sap_busy = False

#         self.sap_spinner.hide()
#         # self.search_button.setEnabled(True)
#         # self.search_edit.setEnabled(True)
#         self.sap_list.setEnabled(True)

#         if success:
#             self.sap_status.clear()
#             self.sap_status.hide()
#         else:
#             self.sap_status.setText(message or "Failed to open SAP.")
#             self.sap_status.setStyleSheet("color: #C34242;")
#             self.sap_status.show()

#     # ------------------------------------------------------
#     # Public API: populate from your actual plugin results
#     # ------------------------------------------------------

#     def set_query(self, text: str) -> None:
#         self.search_edit.setText(text)
#         # self.sap_panel.show()
#         # self.findit_panel.show()
#         self._request_search()

#     def set_findit_results(
#         self,
#         results: list[FindItResult] | tuple[FindItResult, ...],
#     ) -> None:
#         self.set_findit_status("ready")
#         self.findit_list.clear()
#         for result in results:
#             item = QListWidgetItem(
#                 AppIcon.icon(result.kind), f"{result.title} - {result.subtitle}"
#             )
#             item.setToolTip(result.subtitle)
#             item.setData(Qt.ItemDataRole.UserRole, result)
#             # item.setToolTip(result.link)
#             self.findit_list.addItem(item)

#         count = self.findit_list.count()
#         self.findit_count.setText(
#             f"{count} result" if count == 1 else f"{count} results"
#         )
#         self._update_actions()

#     def set_sap_transactions(
#         self,
#         transactions: list[SapTransaction] | tuple[SapTransaction, ...],
#     ) -> None:
#         self.sap_list.clear()

#         for transaction in transactions:
#             item = QListWidgetItem(
#                 self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
#                 (
#                     f"{transaction.code}\n{transaction.description}"
#                     if transaction.description
#                     else transaction.code
#                 ),
#             )
#             item.setData(Qt.ItemDataRole.UserRole, transaction)
#             self.sap_list.addItem(item)

#         count = self.sap_list.count()
#         self.sap_count.setText(f"{count} available")
#         # self._update_actions()

#     def append_sap_transactions(
#         self,
#         transaction: SapTransaction,
#     ) -> None:

#         item = QListWidgetItem(
#             self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
#             (
#                 f"{transaction.code}\n{transaction.description}"
#                 if transaction.description
#                 else transaction.code
#             ),
#         )
#         item.setData(Qt.ItemDataRole.UserRole, transaction)
#         self.sap_list.addItem(item)

#         count = self.sap_list.count()
#         self.sap_count.setText(f"{count} available")
#         # self._update_actions()

#     def set_busy(self, busy: bool) -> None:
#         self.search_button.setEnabled(not busy)
#         self.search_edit.setEnabled(not busy)
#         self.search_button.setText("Searching..." if busy else "Search")

#     def set_status(self, message: str) -> None:
#         self.status_label.setText(message)

#     # ------------------------------------------------------
#     # Actions
#     # ------------------------------------------------------

#     def _request_search(self) -> None:
#         query = self.search_edit.text().strip()
#         if not query:
#             self.search_edit.setFocus()
#             self.set_status("Enter a reference before searching.")
#             return
#         self.set_findit_status("searching")

#         self.sap_list.clear()
#         self.sap_count.setText(f"0 available")

#         self.finish_sap_open()
#         self.findit_list.clear()
#         self.findit_handler(query)
#         self.sap_handler(query)

#     def findit_handler(self, text):
#         target_items = extract_search_items(text)
#         if not target_items:
#             self.set_findit_status("failed", "Item(s) not found!")
#             self.findit_list.clear()
#             return
#         self.search_worker = Findit(target_items)
#         self.search_worker.result_readay.connect(self.set_findit_results)
#         self.search_worker.start()

#     def handle_result(self, data_list: list):
#         results = []
#         for data in data_list:
#             results.append(
#                 FindItResult(
#                     kind=data["type"],
#                     title=data["text"],
#                     subtitle=data.get("subtitle", ""),
#                     link=data["url"],
#                 )
#             )
#         self.set_findit_results(results)

#     def sap_handler(self, text):
#         if not text:
#             return
#         items = extract_items(text)
#         if not items:
#             return
#         options = SAPOptions(
#             material=(items.material_12NC[0] if items.material_12NC else ""),
#             machine=(items.machine_nr[0] if items.machine_nr else ""),
#             service_order=(items.service_order[0] if items.service_order else ""),
#         )
#         self.build_sap_menu(options=options)

#     def build_sap_menu(self, options: SAPOptions):
#         operations = self.get_available_operations(options)
#         if not operations:
#             return None
#         self.sap_list.clear()
#         for operation in operations:
#             info = SAP_OPERATIONS[operation]
#             # self.append_sap_transactions(SapTransaction(info.title))
#             item = QListWidgetItem(
#                 AppIcon.icon("sap"),
#                 (f"{info.title}"),
#             )
#             item.setData(Qt.ItemDataRole.UserRole, (operation, options))
#             self.sap_list.addItem(item)

#         count = self.sap_list.count()
#         self.sap_count.setText(f"{count} available")

#     def get_available_operations(self, options: SAPOptions) -> list:
#         available = []
#         for operation, info in SAP_OPERATIONS.items():
#             if any(getattr(options, field, "") for field in info.inputs):
#                 available.append(operation)
#         return available

#     def _open_findit_item(self, item: QListWidgetItem) -> None:
#         result = item.data(Qt.ItemDataRole.UserRole)
#         if not isinstance(result, FindItResult):
#             return

#         url = QUrl(result.link)
#         scheme = url.scheme().lower()

#         # Open ordinary web links directly. Route internal/custom schemes
#         # through the application, where you can apply your own rules.
#         if scheme in {"https", "http"} and url.isValid() and url.host():
#             if not QDesktopServices.openUrl(url):
#                 self.set_status(f"Could not open: {result.title}")
#             return

#         self.findit_link_requested.emit(result.link)

#     def _open_sap_item(self, item: QListWidgetItem) -> None:
#         if not self.begin_sap_open():
#             return
#         operation, options = item.data(Qt.ItemDataRole.UserRole)
#         try:
#             self.set_sap_progress("Waiting for SAP transaction...")
#             QTimer.singleShot(0, lambda: self.sap.execute(operation, options))
#             # self.sap.execute(operation, options)
#         except Exception as exc:
#             self.finish_sap_open(success=False, message=str(exc))

#     def _open_selected_findit(self) -> None:
#         # item = self.findit_list.currentItem()
#         # if item is not None:
#         #     self._open_findit_item(item)
#         items = self.findit_list.selectedItems()
#         for item in items:
#             self._open_findit_item(item)

#     def _open_all_findit(self) -> None:
#         codes: list[str] = []

#         for index in range(self.findit_list.count()):
#             item = self.findit_list.item(index)
#             self._open_findit_item(item)

#     def _update_actions(self) -> None:
#         selected = self.findit_list.selectedItems()
#         self.open_button.setEnabled(bool(selected))
#         # self.open_button.setEnabled(self.findit_list.currentItem() is not None)
#         self.open_all_button.setEnabled(self.findit_list.count() > 0)

#     def showEvent(self, event):
#         super().showEvent(event)
#         self.search_edit.setFocus()
#         # Apply 50/50 once the splitter has a real width.
#         if not self._initial_split_applied:
#             self._initial_split_applied = True
#             QTimer.singleShot(0, self._set_equal_panel_sizes)
#         super().showEvent(event)
#         # QTimer.singleShot(0, self._restore_size)
#         print("finditsap ui size", self.size())

#     def _restore_size(self, *_):
#         # width is halved when only one panel has results (see check_emptiness)
#         self.resize(self._width, self._height)

#     # def event(self, e):
#     #     t = getattr(QEvent.Type, "DevicePixelRatioChange", None)  # Qt >= 6.6
#     #     if t is not None and e.type() == t:
#     #         print("DevicePixelRatioChange")
#     #         QTimer.singleShot(0, self._restore_size)
#     #     return super().event(e)

#     def _set_equal_panel_sizes(self) -> None:
#         half = self.splitter.width() // 2
#         self.splitter.setSizes([half, half])

#     def shutdown(self):
#         self.sap.stop()

#     def closeEvent(self, event):
#         # self.sap.stop()
#         # QApplication.quit()
#         return super().closeEvent(event)

#     def keyPressEvent(self, event) -> None:
#         if event.key() == Qt.Key.Key_Escape:
#             self.close()
#             return

#         super().keyPressEvent(event)

#     def mousePressEvent(self, event) -> None:
#         if event.button() == Qt.MouseButton.LeftButton:
#             window_handle = self.window().windowHandle()
#             if window_handle and window_handle.startSystemMove():
#                 event.accept()
#                 return
#         # if event.button() != Qt.MouseButton.LeftButton:
#         #     self.close()
#         #     QApplication.quit()
#         #     event.accept()
#         #     return
#         super().mousePressEvent(event)

#     # def event(self, event):
#     #     # print(event.type())
#     #     # if event.type() == QEvent.Type.ActivationChange:
#     #     if event.type() == QEvent.Type.FocusOut:
#     #         if not self.isActiveWindow():
#     #             self.hide()
#     #     return super().changeEvent(event)

#     # def focusOutEvent(self, event):
#     #     self.hide()
#     #     return super().focusOutEvent(event)

# # ----------------------------------------------------------------------
# # Keep ALL your existing imports, and add these:
# # ----------------------------------------------------------------------
# import re
# from PyQt6.QtCore import QSize
# from PyQt6.QtGui import QCursor, QGuiApplication

# # ----------------------------------------------------------------------
# # Manual DPI helpers (needed because Qt high-DPI scaling is disabled)
# # ----------------------------------------------------------------------
# def dpi_scale() -> float:
#     """1.0 at 100%, 1.25 at 125%, 1.5 at 150% ... for the screen under the cursor."""
#     screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
#     print(screen.logicalDotsPerInch())
#     return max(1.0, screen.logicalDotsPerInch() / 96.0)


# def scale_px(css: str, k: float) -> str:
#     """Multiply every 'NNpx' in a stylesheet by k (min 1px)."""
#     return re.sub(
#         r"(\d+(?:\.\d+)?)px",
#         lambda m: f"{max(1, round(float(m.group(1)) * k))}px",
#         css,
#     )


# class FinditSAPUI(QWidget):
#     """
#     Search + FindIt results + available SAP transactions.

#     The widget does not perform a search or automate SAP itself.
#     Connect its signals to your existing search/SAP controller.
#     """

#     search_requested = pyqtSignal(str)
#     # Emitted for non-HTTP(S) links that need your application's handler.
#     findit_link_requested = pyqtSignal(str)

#     def __init__(self, parent: QWidget | None = None):
#         super().__init__(parent=None)

#         # ---- manual DPI scale (must be set before anything is built) ----
#         self.k = dpi_scale()

#         self.setWindowFlag(
#             Qt.WindowType.Popup
#             | Qt.WindowType.FramelessWindowHint
#             | Qt.WindowType.WindowStaysOnTopHint
#             | Qt.WindowType.NoDropShadowWindowHint
#         )
#         self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

#         self.setObjectName("lookupPopup")
#         self._height = 350
#         self._width = 400
#         self.resize(self.S(self._width), self.S(self._height))

#         self._initial_split_applied = False

#         self._build_ui()
#         self._apply_style()
#         self._update_actions()

#         self._sap_busy = False
#         self.sap = SAPController()
#         self.sap.status.connect(self.set_sap_progress)
#         self.sap.error.connect(lambda error: self.finish_sap_open(False, error))
#         self.sap.finished.connect(lambda: self.finish_sap_open(True))

#     # ------------------------------------------------------
#     # DPI helper
#     # ------------------------------------------------------
#     def S(self, value: float) -> int:
#         """Scale a 96-DPI pixel value to the current screen."""
#         return round(value * self.k)

#     # ------------------------------------------------------
#     # UI construction
#     # ------------------------------------------------------
#     def _build_ui(self) -> None:
#         S = self.S

#         root = QVBoxLayout(self)
#         root.setContentsMargins(0, 0, 0, 0)
#         root.setSpacing(0)
#         root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)   # layout must not set the window minimum

#         self.window_frame = QFrame(self)
#         self.window_frame.setObjectName("lookupWindowFrame")
#         root.addWidget(self.window_frame)

#         content_layout = QVBoxLayout(self.window_frame)
#         content_layout.setContentsMargins(S(10), S(5), S(10), S(14))
#         content_layout.setSpacing(S(2))

#         # --------------------------------------------------
#         # Status row + close button
#         # --------------------------------------------------
#         close_button = QPushButton("✕", self.window_frame)
#         close_button.setObjectName("lookupCloseButton")
#         # close_button.setAutoDefault(False)
#         # close_button.setFixedSize(S(32), S(32))
#         close_button.clicked.connect(self.hide)

#         status_row = QHBoxLayout()
#         status_row.setSpacing(S(9))

#         self.status_label = QLabel(
#             "Enter a reference to search, or paste text recognized by OCR.", self
#         )
#         self.status_label.setObjectName("statusLabel")

#         self.status_label.setWordWrap(True)
#         self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

#         status_row.addWidget(self.status_label, Qt.AlignmentFlag.AlignBottom)
#         status_row.addStretch()
#         status_row.addWidget(close_button)
#         content_layout.addLayout(status_row)

#         # --------------------------------------------------
#         # Search bar
#         # --------------------------------------------------
#         search_row = QHBoxLayout()
#         search_row.setSpacing(S(1))

#         self.search_edit = ExpandableEdit(self)
#         self.search_edit.setObjectName("searchEdit")
#         metrics = QFontMetricsF(self.search_edit.font())
#         self.search_edit.setTabStopDistance(metrics.horizontalAdvance(" ") * 4)
#         self.search_edit.setPlaceholderText(
#             "Search a service order, material 12NC, procedure, AIR ID..."
#         )
#         self.search_edit.setClearButtonEnabled(True)
#         self.search_edit.returnPressed.connect(self._request_search)
#         search_row.addWidget(self.search_edit, 1, Qt.AlignmentFlag.AlignTop)

#         self.search_button = QPushButton("Search", self)
#         self.search_button.setObjectName("searchButton")
#         # self.search_button.setFixedWidth(S(70))
#         self.search_button.clicked.connect(self._request_search)
#         search_row.addWidget(self.search_button, 0, Qt.AlignmentFlag.AlignTop)

#         self.findit_button = QPushButton("Findit", self)
#         self.findit_button.setObjectName("searchButton")
#         # self.findit_button.setFixedWidth(S(70))
#         self.findit_button.clicked.connect(self._go_findit)
#         search_row.addWidget(self.findit_button, 0, Qt.AlignmentFlag.AlignTop)

#         content_layout.addLayout(search_row)
#         content_layout.addSpacing(S(5))

#         # --------------------------------------------------
#         # Two equal-width panels initially
#         # --------------------------------------------------
#         self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
#         self.splitter.setObjectName("resultsSplitter")
#         self.splitter.setChildrenCollapsible(True)
#         self.splitter.setHandleWidth(S(3))

#         self.findit_panel = self._build_findit_panel()
#         self.sap_panel = self._build_sap_panel()

#         self.splitter.addWidget(self.sap_panel)
#         self.splitter.addWidget(self.findit_panel)

#         self.splitter.setStretchFactor(0, 1)
#         self.splitter.setStretchFactor(1, 1)
#         self.splitter.setSizes([S(500), S(500)])

#         content_layout.addWidget(self.splitter, 1)

#     def _apply_style(self) -> None:
#         # Every "NNpx" below is multiplied by self.k by scale_px().
#         css = """
#             QDialog#lookupPopup {
#                 background: #F4F8FC;
#             }
#             QWidget#lookupPopup {
#                 background: transparent;
#                 border: none;
#             }
#             QFrame#lookupWindowFrame {
#                 background: #F4F8FC;
#                 border: 1px solid #C9DCEC;
#                 border-radius: 16px;
#             }
#             QPushButton#lookupCloseButton {
#                 min-width: 32px;  max-width: 32px;
#                 min-height: 32px; max-height: 32px;
#                 color: #52657A;
#                 background: transparent;
#                 border: none;
#                 border-radius: 8px;
#                 font-size: 22px;
#                 padding: 0;
#             }
#             QPushButton#lookupCloseButton:hover {
#                 color: #ff0000;
#                 background: #E5EEF7;
#             }

#             QLabel#brand {
#                 color: white;
#                 background: #0878D7;
#                 border-radius: 10px;
#                 font-size: 23px;
#                 font-weight: 800;
#             }

#             QLabel#title {
#                 color: #192C45;
#                 font-size: 20px;
#                 font-weight: 750;
#             }

#             QLabel#subtitle,
#             QLabel#panelHint,
#             QLabel#statusLabel {
#                 color: #65788D;
#                 font-size: 12px;
#             }

#             QLineEdit#searchEdit {
#                 min-height: 30px;
#                 padding: 0 6px;
#                 color: #1D3049;
#                 background: white;
#                 border: 1px solid #C8D9E9;
#                 border-radius: 8px;
#                 font-size: 12px;
#             }

#             QLineEdit#searchEdit:focus {
#                 border: 1px solid #0878D7;
#             }
#             ExpandableEdit#searchEdit {
#                 min-height: 30px;
#                 padding: 0 6px;
#                 color: #1D3049;
#                 background: white;
#                 border: 1px solid #C8D9E9;
#                 border-radius: 8px;
#                 font-size: 12px;
#             }

#             ExpandableEdit#searchEdit:focus {
#                 border: 1px solid #0878D7;
#             }
#             QFrame#panel {
#                 background: white;
#                 border: 1px solid #DCE7F1;
#                 border-radius: 13px;
#             }

#             QLabel#panelTitle {
#                 color: #1D3049;
#                 font-size: 13px;
#                 font-weight: 750;
#                 background: transparent;
#             }

#             QLabel#countBadge {
#                 color: #0878D7;
#                 background: #EAF4FF;
#                 border-radius: 7px;
#                 padding: 4px 8px;
#                 font-size: 11px;
#                 font-weight: 700;
#             }
#             QListWidget {
#                 qproperty-iconSize: 15px 15px;
#             }
#             QListWidget#resultList {
#                 background: transparent;
#                 border: none;
#                 outline: none;
#                 color: #253B55;
#                 font-size: 12px;
#             }

#             QListWidget#resultList::item {
#                 padding: 2px 5px;
#                 border: 1px solid #E5EDF5;
#                 border-radius: 8px;
#             }

#             QListWidget#resultList::item:hover {
#                 background: #F2F8FE;
#                 border-color: #C7E0F6;
#             }

#             QListWidget#resultList::item:selected {
#                 color: #153A63;
#                 background: #E7F3FF;
#                 border-color: #9DCDF2;
#             }
#             QSplitter#resultsSplitter::handle {
#                 background-color: #e5e7eb;
#                 margin: 5px 3px;
#             }

#             QSplitter#resultsSplitter::handle:hover {
#                 background-color: #555555;
#             }
#             QPushButton#searchButton {
#                 min-width: 40px;  max-width: 40px;
#                 min-height: 25px;
#                 padding: 0 16px;
#                 color: white;
#                 background: #0878D7;
#                 border: 1px solid #0878D7;
#                 border-radius: 9px;
#                 font-size: 12px;
#                 font-weight: 700;
#             }

#             QPushButton#searchButton:hover{
#                 background: #006CC5;
#             }

#             QPushButton#secondaryButton,
#             QPushButton#primaryButton {
#                 min-height: 20px;
#                 padding: 0 16px;
#                 color: #0878D7;
#                 background: white;
#                 border: 1px solid #B8D9F3;
#                 border-radius: 8px;
#                 font-size: 12px;
#                 font-weight: 700;
#             }

#             QPushButton#secondaryButton:hover,
#             QPushButton#primaryButton:hover{
#                 background: #EAF4FF;
#             }

#             QPushButton#secondaryButton:disabled,
#             QPushButton#primaryButton:disabled {
#                 color: #9BAABD;
#                 background: #EDF2F7;
#                 border-color: #E0E8F0;
#             }

#             QScrollBar:vertical {
#                 width: 9px;
#                 background: transparent;
#             }

#             QScrollBar::handle:vertical {
#                 background: #C9D8E7;
#                 border-radius: 4px;
#                 min-height: 25px;
#             }

#             QScrollBar::add-line:vertical,
#             QScrollBar::sub-line:vertical {
#                 height: 0;
#             }
#             """
#         self.setStyleSheet(scale_px(css, self.k))

#         # Item icons are drawn at the QListWidget icon size; set it explicitly
#         # so it is scaled even if qproperty-iconSize is ignored.
#         icon = QSize(self.S(15), self.S(15))
#         self.sap_list.setIconSize(icon)
#         self.findit_list.setIconSize(icon)

#     def _build_sap_panel(self) -> QFrame:
#         S = self.S
#         panel = QFrame(self)
#         panel.setObjectName("panel")

#         layout = QVBoxLayout(panel)
#         layout.setContentsMargins(S(5), S(5), S(5), S(5))
#         layout.setSpacing(S(5))

#         heading = QHBoxLayout()

#         label = QLabel("SAP transactions", panel)
#         label.setObjectName("panelTitle")
#         heading.addWidget(label)

#         heading.addStretch()

#         self.sap_count = QLabel("0 available", panel)
#         self.sap_count.setObjectName("countBadge")
#         heading.addWidget(self.sap_count)

#         layout.addLayout(heading)

#         hint = QLabel("Click a transaction to open it in SAP.", panel)
#         hint.setObjectName("panelHint")
#         layout.addWidget(hint)

#         status_row = QHBoxLayout()

#         self.sap_spinner = Spinner(panel)
#         self.sap_spinner.hide()
#         status_row.addWidget(self.sap_spinner)

#         self.sap_status = QLabel("", panel)
#         self.sap_status.setObjectName("statusLabel")
#         self.sap_status.setWordWrap(True)
#         self.sap_status.setTextFormat(Qt.TextFormat.PlainText)
#         self.sap_status.hide()
#         status_row.addWidget(self.sap_status, 1)

#         self.sap_list = QListWidget(panel)
#         self.sap_list.setObjectName("resultList")
#         self.sap_list.setSpacing(S(1))
#         self.sap_list.doubleClicked.connect(self._open_sap_item)

#         layout.addWidget(self.sap_list, 1)
#         layout.addLayout(status_row)
#         return panel

#     def _build_findit_panel(self) -> QFrame:
#         S = self.S
#         panel = QFrame(self)
#         panel.setObjectName("panel")

#         layout = QVBoxLayout(panel)
#         layout.setContentsMargins(S(5), S(5), S(5), S(5))
#         layout.setSpacing(S(5))

#         heading = QHBoxLayout()

#         label = QLabel("FindIt results", panel)
#         label.setObjectName("panelTitle")
#         heading.addWidget(label)
#         heading.addStretch()

#         self.findit_count = QLabel("0 results", panel)
#         self.findit_count.setObjectName("countBadge")
#         heading.addWidget(self.findit_count)

#         layout.addLayout(heading)

#         hint = QLabel("Click a result to open its link.", panel)
#         hint.setObjectName("panelHint")
#         layout.addWidget(hint)

#         # Stack: results OR searching/error status.
#         self.findit_stack = QStackedWidget(panel)
#         layout.addWidget(self.findit_stack, 1)

#         self.findit_list = QListWidget(self.findit_stack)
#         self.findit_list.setObjectName("resultList")
#         self.findit_list.setSpacing(S(1))
#         self.findit_list.setSelectionMode(
#             QAbstractItemView.SelectionMode.ExtendedSelection
#         )
#         self.findit_list.doubleClicked.connect(self._open_findit_item)
#         self.findit_list.itemSelectionChanged.connect(self._update_actions)

#         model = self.findit_list.model()
#         model.rowsInserted.connect(self.check_emptiness)
#         model.rowsRemoved.connect(self.check_emptiness)

#         self.findit_stack.addWidget(self.findit_list)

#         # Centered status page.
#         self.findit_status_page = QWidget(self.findit_stack)

#         status_layout = QVBoxLayout(self.findit_status_page)
#         status_layout.setContentsMargins(S(15), S(15), S(15), S(15))
#         status_layout.setSpacing(S(12))
#         status_layout.addStretch()

#         self.findit_spinner = Spinner(self.findit_status_page)
#         status_layout.addWidget(
#             self.findit_spinner, alignment=Qt.AlignmentFlag.AlignHCenter
#         )

#         self.findit_status_label = QLabel(self.findit_status_page)
#         self.findit_status_label.setObjectName("finditStatus")
#         self.findit_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.findit_status_label.setTextFormat(Qt.TextFormat.PlainText)
#         self.findit_status_label.setWordWrap(True)

#         status_layout.addWidget(self.findit_status_label)
#         status_layout.addStretch()

#         self.findit_stack.addWidget(self.findit_status_page)

#         actions = QHBoxLayout()
#         actions.setSpacing(S(9))
#         actions.setContentsMargins(S(10), 0, S(10), 0)

#         self.open_button = QPushButton("Open", panel)
#         self.open_button.setObjectName("secondaryButton")
#         self.open_button.clicked.connect(self._open_selected_findit)
#         actions.addWidget(self.open_button)

#         actions.addStretch()

#         self.open_all_button = QPushButton("Open All", panel)
#         self.open_all_button.setObjectName("primaryButton")
#         self.open_all_button.clicked.connect(self._open_all_findit)
#         actions.addWidget(self.open_all_button)

#         layout.addLayout(actions)

#         self.set_findit_status("ready")

#         return panel

#     # ------------------------------------------------------
#     # Behaviour (unchanged except where noted)
#     # ------------------------------------------------------
#     def _go_findit(self, *_):
#         first_line = self.search_edit.document().firstBlock().text().strip()
#         if not first_line:
#             return
#         url = QUrl(f"https://findit.asml.com/search?q={first_line}")
#         scheme = url.scheme().lower()
#         if scheme in {"https", "http"} and url.isValid() and url.host():
#             QDesktopServices.openUrl(url)

#     def check_emptiness(self):
#         # return
#         is_sap_empty = self.sap_list.count() == 0
#         is_findit_empty = self.findit_list.count() == 0
#         if is_findit_empty:
#             self.splitter.setSizes([self.splitter.width(), 0])
#             # self.resize(self._width // 2, self._height)
#         elif is_sap_empty:
#             self.splitter.setSizes([0, self.splitter.width()])
#             # self.resize(self._width // 2, self._height)
#         else:
#             self._set_equal_panel_sizes()
#             # self.resize(self._width, self._height)

#     def set_findit_status(self, state: str, message: str = ""):
#         if state not in ("canceled", "searching", "failed", "ready"):
#             raise ValueError(f"Unknown FindIt state: {state}")

#         if state == "ready":
#             self.findit_stack.setCurrentWidget(self.findit_list)
#             self.findit_spinner.hide()

#             count = self.findit_list.count()
#             self.findit_count.setText(f"{count} results")

#             self._update_actions()
#             return

#         searching = state == "searching"

#         self.findit_status_label.setText(
#             message or ("Searching..." if searching else "Search failed.")
#         )
#         self.findit_status_label.setStyleSheet(
#             "color: #738399;" if searching else "color: #C34242;"
#         )

#         self.findit_spinner.setVisible(searching)
#         self.findit_stack.setCurrentWidget(self.findit_status_page)

#         self.findit_count.setText("Searching..." if searching else "Failed")
#         self.open_button.setEnabled(False)
#         self.open_all_button.setEnabled(False)

#     def begin_sap_open(self) -> bool:
#         """Return False if another SAP operation is already running."""
#         if self._sap_busy:
#             return False
#         self._sap_busy = True

#         self.sap_list.setEnabled(False)

#         self.sap_status.setText("Opening SAP...")
#         self.sap_status.setStyleSheet("color: #738399;")
#         self.sap_status.show()
#         self.sap_spinner.show()
#         QApplication.processEvents()

#         return True

#     def set_sap_progress(self, message: str):
#         if self._sap_busy:
#             self.sap_status.setText(message)

#     def finish_sap_open(self, success: bool = True, message: str = ""):
#         self._sap_busy = False

#         self.sap_spinner.hide()
#         self.sap_list.setEnabled(True)

#         if success:
#             self.sap_status.clear()
#             self.sap_status.hide()
#         else:
#             self.sap_status.setText(message or "Failed to open SAP.")
#             self.sap_status.setStyleSheet("color: #C34242;")
#             self.sap_status.show()

#     # ------------------------------------------------------
#     # Public API: populate from your actual plugin results
#     # ------------------------------------------------------
#     def set_query(self, text: str) -> None:
#         self.search_edit.setText(text)
#         self._request_search()

#     def set_findit_results(
#         self,
#         results: list[FindItResult] | tuple[FindItResult, ...],
#     ) -> None:
#         self.set_findit_status("ready")
#         self.findit_list.clear()
#         for result in results:
#             item = QListWidgetItem(
#                 AppIcon.icon(result.kind), f"{result.title} - {result.subtitle}"
#             )
#             item.setToolTip(result.subtitle)
#             item.setData(Qt.ItemDataRole.UserRole, result)
#             self.findit_list.addItem(item)

#         count = self.findit_list.count()
#         self.findit_count.setText(
#             f"{count} result" if count == 1 else f"{count} results"
#         )
#         self._update_actions()

#     def set_sap_transactions(
#         self,
#         transactions: list[SapTransaction] | tuple[SapTransaction, ...],
#     ) -> None:
#         self.sap_list.clear()

#         for transaction in transactions:
#             item = QListWidgetItem(
#                 self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
#                 (
#                     f"{transaction.code}\n{transaction.description}"
#                     if transaction.description
#                     else transaction.code
#                 ),
#             )
#             item.setData(Qt.ItemDataRole.UserRole, transaction)
#             self.sap_list.addItem(item)

#         count = self.sap_list.count()
#         self.sap_count.setText(f"{count} available")

#     def append_sap_transactions(self, transaction: SapTransaction) -> None:
#         item = QListWidgetItem(
#             self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
#             (
#                 f"{transaction.code}\n{transaction.description}"
#                 if transaction.description
#                 else transaction.code
#             ),
#         )
#         item.setData(Qt.ItemDataRole.UserRole, transaction)
#         self.sap_list.addItem(item)

#         count = self.sap_list.count()
#         self.sap_count.setText(f"{count} available")

#     def set_busy(self, busy: bool) -> None:
#         self.search_button.setEnabled(not busy)
#         self.search_edit.setEnabled(not busy)
#         self.search_button.setText("Searching..." if busy else "Search")

#     def set_status(self, message: str) -> None:
#         self.status_label.setText(message)

#     # ------------------------------------------------------
#     # Actions
#     # ------------------------------------------------------
#     def _request_search(self) -> None:
#         query = self.search_edit.text().strip()
#         if not query:
#             self.search_edit.setFocus()
#             self.set_status("Enter a reference before searching.")
#             return
#         self.set_findit_status("searching")

#         self.sap_list.clear()
#         self.sap_count.setText("0 available")

#         self.finish_sap_open()
#         self.findit_list.clear()
#         self.findit_handler(query)
#         self.sap_handler(query)

#     def findit_handler(self, text):
#         target_items = extract_search_items(text)
#         if not target_items:
#             self.set_findit_status("failed", "Item(s) not found!")
#             self.findit_list.clear()
#             return
#         self.search_worker = Findit(target_items)
#         self.search_worker.result_readay.connect(self.set_findit_results)
#         self.search_worker.start()

#     def handle_result(self, data_list: list):
#         results = []
#         for data in data_list:
#             results.append(
#                 FindItResult(
#                     kind=data["type"],
#                     title=data["text"],
#                     subtitle=data.get("subtitle", ""),
#                     link=data["url"],
#                 )
#             )
#         self.set_findit_results(results)

#     def sap_handler(self, text):
#         if not text:
#             return
#         items = extract_items(text)
#         if not items:
#             return
#         options = SAPOptions(
#             material=(items.material_12NC[0] if items.material_12NC else ""),
#             machine=(items.machine_nr[0] if items.machine_nr else ""),
#             service_order=(items.service_order[0] if items.service_order else ""),
#         )
#         self.build_sap_menu(options=options)

#     def build_sap_menu(self, options: SAPOptions):
#         operations = self.get_available_operations(options)
#         if not operations:
#             return None
#         self.sap_list.clear()
#         for operation in operations:
#             info = SAP_OPERATIONS[operation]
#             item = QListWidgetItem(AppIcon.icon("sap"), f"{info.title}")
#             item.setData(Qt.ItemDataRole.UserRole, (operation, options))
#             self.sap_list.addItem(item)

#         count = self.sap_list.count()
#         self.sap_count.setText(f"{count} available")

#     def get_available_operations(self, options: SAPOptions) -> list:
#         available = []
#         for operation, info in SAP_OPERATIONS.items():
#             if any(getattr(options, field, "") for field in info.inputs):
#                 available.append(operation)
#         return available

#     def _open_findit_item(self, item: QListWidgetItem) -> None:
#         result = item.data(Qt.ItemDataRole.UserRole)
#         if not isinstance(result, FindItResult):
#             return

#         url = QUrl(result.link)
#         scheme = url.scheme().lower()

#         if scheme in {"https", "http"} and url.isValid() and url.host():
#             if not QDesktopServices.openUrl(url):
#                 self.set_status(f"Could not open: {result.title}")
#             return

#         self.findit_link_requested.emit(result.link)

#     def _open_sap_item(self, item: QListWidgetItem) -> None:
#         if not self.begin_sap_open():
#             return
#         operation, options = item.data(Qt.ItemDataRole.UserRole)
#         try:
#             self.set_sap_progress("Waiting for SAP transaction...")
#             QTimer.singleShot(0, lambda: self.sap.execute(operation, options))
#         except Exception as exc:
#             self.finish_sap_open(success=False, message=str(exc))

#     def _open_selected_findit(self) -> None:
#         for item in self.findit_list.selectedItems():
#             self._open_findit_item(item)

#     def _open_all_findit(self) -> None:
#         for index in range(self.findit_list.count()):
#             self._open_findit_item(self.findit_list.item(index))

#     def _update_actions(self) -> None:
#         selected = self.findit_list.selectedItems()
#         self.open_button.setEnabled(bool(selected))
#         self.open_all_button.setEnabled(self.findit_list.count() > 0)

#     # do all scaling BEFORE show, never inside showEvent
#     def apply_scale(self):
#         self.k = dpi_scale()
#         self._apply_style()
#         self.ensurePolished()
#         self.layout().invalidate()
#         self.layout().activate()          # refresh the minimum now, not later
#         self._target = QSize(self.S(self._width), self.S(self._height))
#         self.resize(self._target)

#     def showEvent(self, event) -> None:
#         self.apply_scale()
#         super().showEvent(event)
#         # self.k = dpi_scale()
#         self.search_edit.setFocus()
#         if not self._initial_split_applied:
#             self._initial_split_applied = True
#             QTimer.singleShot(0, self._set_equal_panel_sizes)
#         # self._apply_style()
#         # self.resize(self.S(self._width), self.S(self._height))
#         # QTimer.singleShot(0, lambda: self.resize(self.S(self._width), self.S(self._height)))

#         QTimer.singleShot(1000, lambda: print(self.minimumSizeHint(), self.minimumSize(), self.layout().minimumSize()))


#     # import traceback


#     def _set_equal_panel_sizes(self) -> None:
#         half = self.splitter.width() // 2
#         self.splitter.setSizes([half, half])

#     def shutdown(self):
#         self.sap.stop()

#     def closeEvent(self, event):
#         return super().closeEvent(event)

#     def keyPressEvent(self, event) -> None:
#         if event.key() == Qt.Key.Key_Escape:
#             self.close()
#             return
#         super().keyPressEvent(event)

#     def mousePressEvent(self, event) -> None:
#         if event.button() == Qt.MouseButton.LeftButton:
#             window_handle = self.window().windowHandle()
#             if window_handle and window_handle.startSystemMove():
#                 event.accept()
#                 return
#         super().mousePressEvent(event)

# ======================================================================
# FinditSAPUI - multi-screen DPI-safe version (QT_ENABLE_HIGHDPI_SCALING=0)
#
# Keep ALL your existing imports and add:
#     import re
#     from PyQt6.QtCore import QPoint, QSize
#     from PyQt6.QtGui import QCursor, QGuiApplication, QScreen
#     from PyQt6.QtWidgets import QLayout, QSizePolicy
#
# Startup: ONLY set QT_ENABLE_HIGHDPI_SCALING=0.
# Do NOT set QT_SCALE_FACTOR / QT_FONT_DPI (the class does the scaling).
# ======================================================================


# ----------------------------------------------------------------------
# DPI helpers
# ----------------------------------------------------------------------
def screen_scale(screen: "QScreen | None") -> float:
    """1.0 at 100%, 1.25 at 125%, 1.5 at 150% ... for the given screen."""
    screen = screen or QGuiApplication.primaryScreen()
    return round(max(1.0, screen.logicalDotsPerInch() / 96.0), 2)


_PX = re.compile(r"(\d+(?:\.\d+)?)px")


def scale_qss(css: str, k: float) -> str:
    """Multiply every 'NNpx' in a stylesheet by k. 0px and 1px stay as they are."""

    def repl(m: "re.Match") -> str:
        v = float(m.group(1))
        return m.group(0) if v <= 1 else f"{round(v * k)}px"

    return _PX.sub(repl, css)


# Written at 96 DPI. Every px value is scaled by scale_qss().
_QSS = """
QWidget { font-size: 12px; }

QWidget#lookupPopup { background: transparent; border: none; }

QFrame#lookupWindowFrame {
    background: #F4F8FC;
    border: 1px solid #C9DCEC;
    border-radius: 16px;
}
QPushButton#lookupCloseButton {
    color: #52657A;
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 22px;
    padding: 0;
}
QPushButton#lookupCloseButton:hover { color: #ff0000; background: #E5EEF7; }

QLabel#panelHint, QLabel#statusLabel { color: #65788D; }

QLineEdit#searchEdit, ExpandableEdit#searchEdit {
    min-height: 30px;
    padding: 0 6px;
    color: #1D3049;
    background: white;
    border: 1px solid #C8D9E9;
    border-radius: 8px;
}
QLineEdit#searchEdit:focus, ExpandableEdit#searchEdit:focus {
    border: 1px solid #0878D7;
}

QFrame#panel {
    background: white;
    border: 1px solid #DCE7F1;
    border-radius: 13px;
}
QLabel#panelTitle {
    color: #1D3049;
    font-size: 13px;
    font-weight: 750;
    background: transparent;
}
QLabel#countBadge {
    color: #0878D7;
    background: #EAF4FF;
    border-radius: 7px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 700;
}

QListWidget#resultList {
    background: transparent;
    border: none;
    outline: none;
    color: #253B55;
}
QListWidget#resultList::item {
    padding: 2px 5px;
    border: 1px solid #E5EDF5;
    border-radius: 8px;
}
QListWidget#resultList::item:hover { background: #F2F8FE; border-color: #C7E0F6; }
QListWidget#resultList::item:selected {
    color: #153A63;
    background: #E7F3FF;
    border-color: #9DCDF2;
}

QSplitter#resultsSplitter::handle { background-color: #e5e7eb; margin: 5px 3px; }
QSplitter#resultsSplitter::handle:hover { background-color: #555555; }

QPushButton#searchButton {
    min-height: 25px;
    padding: 0 16px;
    color: white;
    background: #0878D7;
    border: 1px solid #0878D7;
    border-radius: 9px;
    font-weight: 700;
}
QPushButton#searchButton:hover { background: #006CC5; }

QPushButton#secondaryButton, QPushButton#primaryButton {
    min-height: 20px;
    padding: 0 16px;
    color: #0878D7;
    background: white;
    border: 1px solid #B8D9F3;
    border-radius: 8px;
    font-weight: 700;
}
QPushButton#secondaryButton:hover, QPushButton#primaryButton:hover {
    background: #EAF4FF;
}
QPushButton#secondaryButton:disabled, QPushButton#primaryButton:disabled {
    color: #9BAABD;
    background: #EDF2F7;
    border-color: #E0E8F0;
}

QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical {
    background: #C9D8E7;
    border-radius: 4px;
    min-height: 25px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class FinditSAPUI(QWidget):
    """
    Search + FindIt results + available SAP transactions.

    DPI design (high-DPI scaling is OFF, so Qt units are physical pixels):
      * self.k is the scale of the screen the popup is on.
      * All pixel numbers are written at 96 DPI and go through self.S().
      * Everything that needs a number is registered once with self._scaled(fn);
        _set_scale() re-runs them when the screen (and k) changes. No rebuilds.
      * Window size is set explicitly and is never clamped by the layout
        (SetNoConstraint + Ignored size policies).
      * Show the popup with show_at(global_pos), not show().
    """

    BASE_W = 500  # design size at 96 DPI
    BASE_H = 400

    search_requested = pyqtSignal(str)
    # Emitted for non-HTTP(S) links that need your application's handler.
    findit_link_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=None)

        self.k = 1.0
        self._scale_fns: list = []
        self._single_panel = False
        self._sap_busy = False

        self.setWindowFlag(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("lookupPopup")

        self._build_ui()
        self._set_scale(
            screen_scale(QGuiApplication.screenAt(QCursor.pos())), force=True
        )
        self._apply_size()
        self._update_actions()

        self.sap = SAPController()
        self.sap.status.connect(self.set_sap_progress)
        self.sap.error.connect(lambda error: self.finish_sap_open(False, error))
        self.sap.finished.connect(lambda: self.finish_sap_open(True))

    # ------------------------------------------------------
    # DPI core
    # ------------------------------------------------------
    def S(self, value: float) -> int:
        """Scale a 96-DPI pixel value to the current screen."""
        return round(value * self.k)

    def _scaled(self, fn) -> None:
        """Register fn(S); it is called on every scale change."""
        self._scale_fns.append(fn)

    def _set_scale(self, k: float, force: bool = False) -> bool:
        if not force and abs(k - self.k) < 0.005:
            return False
        self.k = k
        self.setUpdatesEnabled(False)
        try:
            self.setStyleSheet(scale_qss(_QSS, k))
            self.ensurePolished()
            for fn in self._scale_fns:
                fn(self.S)
        finally:
            self.setUpdatesEnabled(True)
        return True

    def _target_size(self) -> QSize:
        w = self.S(self.BASE_W)
        if self._single_panel:
            w //= 2
        return QSize(w, self.S(self.BASE_H))

    def _apply_size(self) -> None:
        self.resize(self._target_size())

    def _layout_panels(self) -> None:
        total = self.splitter.width()
        if self.findit_list.count() == 0:
            sizes = [total, 0]
        elif self.sap_list.count() == 0:
            sizes = [0, total]
        else:
            sizes = [total // 2, total - total // 2]
        self.splitter.setSizes(sizes)

        # sizes = [total // 2, total - total // 2]
        # self.splitter.setSizes(sizes)

    # ------------------------------------------------------
    # Public entry point: use this instead of show()
    # ------------------------------------------------------
    def show_at(self, global_pos: QPoint) -> None:
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        self._set_scale(screen_scale(screen))
        self._apply_size()

        size = self._target_size()
        avail = screen.availableGeometry()
        x = max(avail.left(), min(global_pos.x(), avail.right() - size.width() + 1))
        y = max(avail.top(), min(global_pos.y(), avail.bottom() - size.height() + 1))
        self.move(x, y)

        self.show()
        self.activateWindow()

    def _on_screen_changed(self, screen) -> None:
        """Window dragged to another monitor."""
        if screen is None:
            return
        k = screen_scale(screen)
        if abs(k - self.k) < 0.005:
            return
        QTimer.singleShot(0, lambda: self._rescale(k))

    def _rescale(self, k: float) -> None:
        if self._set_scale(k):
            self._apply_size()
            self._layout_panels()

    # ------------------------------------------------------
    # UI construction (no hard-coded pixels outside self._scaled)
    # ------------------------------------------------------
    def _build_ui(self) -> None:
        reg = self._scaled
        no_constraint = QLayout.SizeConstraint.SetNoConstraint

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setSizeConstraint(no_constraint)  # layout never clamps the window

        self.window_frame = QFrame(self)
        self.window_frame.setObjectName("lookupWindowFrame")
        root.addWidget(self.window_frame)

        content = QVBoxLayout(self.window_frame)
        content.setSizeConstraint(no_constraint)

        def content_metrics(S):
            content.setContentsMargins(S(10), S(5), S(10), S(14))
            content.setSpacing(S(2))

        reg(content_metrics)

        # ---- status row + close button ----
        close_button = QPushButton("✕", self.window_frame)
        close_button.setObjectName("lookupCloseButton")
        close_button.setAutoDefault(False)
        close_button.clicked.connect(self.hide)
        reg(lambda S: close_button.setFixedSize(S(32), S(32)))

        status_row = QHBoxLayout()
        reg(lambda S: status_row.setSpacing(S(9)))

        self.status_label = QLabel(
            "Enter a reference to search, or paste text recognized by OCR.", self
        )
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(close_button)
        content.addLayout(status_row)

        # ---- search bar ----
        search_row = QHBoxLayout()
        reg(lambda S: search_row.setSpacing(S(1)))

        self.search_edit = ExpandableEdit(self)
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText(
            "Search a service order, material 12NC, procedure, AIR ID..."
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self._request_search)
        search_row.addWidget(self.search_edit, 1, Qt.AlignmentFlag.AlignTop)

        def edit_metrics(S):
            self.search_edit.setTabStopDistance(S(14))
            # Optional hook if ExpandableEdit keeps its own pixel constants.
            if hasattr(self.search_edit, "set_scale"):
                self.search_edit.set_scale(self.k)

        reg(edit_metrics)

        self.search_button = QPushButton("Search", self)
        self.search_button.setObjectName("searchButton")
        self.search_button.clicked.connect(self._request_search)
        search_row.addWidget(self.search_button, 0, Qt.AlignmentFlag.AlignTop)

        self.findit_button = QPushButton("Findit", self)
        self.findit_button.setObjectName("searchButton")
        self.findit_button.clicked.connect(self._go_findit)
        search_row.addWidget(self.findit_button, 0, Qt.AlignmentFlag.AlignTop)

        def button_widths(S):
            self.search_button.setFixedWidth(S(70))
            self.findit_button.setFixedWidth(S(70))

        reg(button_widths)

        content.addLayout(search_row)
        spacer_index = content.count()
        content.addSpacing(0)
        reg(
            lambda S: content.itemAt(spacer_index).changeSize(
                0, S(5), QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
            )
        )

        # ---- two panels ----
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("resultsSplitter")
        self.splitter.setChildrenCollapsible(True)
        reg(lambda S: self.splitter.setHandleWidth(S(3)))

        self.findit_panel = self._build_findit_panel()
        self.sap_panel = self._build_sap_panel()

        for panel in (self.sap_panel, self.findit_panel):
            # Ignored => the panel's content never sets a minimum for the window.
            panel.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
            )

        self.splitter.addWidget(self.sap_panel)
        self.splitter.addWidget(self.findit_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        content.addWidget(self.splitter, 1)

        def list_metrics(S):
            icon = QSize(S(15), S(15))
            for lst in (self.sap_list, self.findit_list):
                lst.setIconSize(icon)
                lst.setSpacing(S(1))

        reg(list_metrics)

    def _panel_layout(self, panel: QFrame) -> QVBoxLayout:
        layout = QVBoxLayout(panel)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

        def metrics(S):
            layout.setContentsMargins(S(5), S(5), S(5), S(5))
            layout.setSpacing(S(5))

        self._scaled(metrics)
        return layout

    def _make_spinner(self, parent: QWidget):
        spinner = Spinner(parent)
        # Spinner must paint using its own width()/height(), not constants.
        self._scaled(lambda S: spinner.setFixedSize(S(20), S(20)))
        return spinner

    def _build_sap_panel(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("panel")
        layout = self._panel_layout(panel)

        heading = QHBoxLayout()
        label = QLabel("SAP transactions", panel)
        label.setObjectName("panelTitle")
        heading.addWidget(label)
        heading.addStretch()
        self.sap_count = QLabel("0 available", panel)
        self.sap_count.setObjectName("countBadge")
        heading.addWidget(self.sap_count)
        layout.addLayout(heading)

        hint = QLabel("Click a transaction to open it in SAP.", panel)
        hint.setObjectName("panelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        status_row = QHBoxLayout()
        self.sap_spinner = self._make_spinner(panel)
        self.sap_spinner.hide()
        status_row.addWidget(self.sap_spinner)

        self.sap_status = QLabel("", panel)
        self.sap_status.setObjectName("statusLabel")
        self.sap_status.setWordWrap(True)
        self.sap_status.setTextFormat(Qt.TextFormat.PlainText)
        self.sap_status.hide()
        status_row.addWidget(self.sap_status, 1)

        self.sap_list = QListWidget(panel)
        self.sap_list.setObjectName("resultList")
        self.sap_list.doubleClicked.connect(self._open_sap_item)

        layout.addWidget(self.sap_list, 1)
        layout.addLayout(status_row)
        return panel

    def _build_findit_panel(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("panel")
        layout = self._panel_layout(panel)

        heading = QHBoxLayout()
        label = QLabel("FindIt results", panel)
        label.setObjectName("panelTitle")
        heading.addWidget(label)
        heading.addStretch()
        self.findit_count = QLabel("0 results", panel)
        self.findit_count.setObjectName("countBadge")
        heading.addWidget(self.findit_count)
        layout.addLayout(heading)

        hint = QLabel("Click a result to open its link.", panel)
        hint.setObjectName("panelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Stack: results OR searching/error status.
        self.findit_stack = QStackedWidget(panel)
        layout.addWidget(self.findit_stack, 1)

        self.findit_list = QListWidget(self.findit_stack)
        self.findit_list.setObjectName("resultList")
        self.findit_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.findit_list.doubleClicked.connect(self._open_findit_item)
        self.findit_list.itemSelectionChanged.connect(self._update_actions)

        model = self.findit_list.model()
        model.rowsInserted.connect(self.check_emptiness)
        model.rowsRemoved.connect(self.check_emptiness)

        self.findit_stack.addWidget(self.findit_list)

        # Centered status page.
        self.findit_status_page = QWidget(self.findit_stack)
        status_layout = QVBoxLayout(self.findit_status_page)

        def status_metrics(S):
            status_layout.setContentsMargins(S(15), S(15), S(15), S(15))
            status_layout.setSpacing(S(12))

        self._scaled(status_metrics)
        status_layout.addStretch()

        self.findit_spinner = self._make_spinner(self.findit_status_page)
        status_layout.addWidget(
            self.findit_spinner, alignment=Qt.AlignmentFlag.AlignHCenter
        )

        self.findit_status_label = QLabel(self.findit_status_page)
        self.findit_status_label.setObjectName("finditStatus")
        self.findit_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.findit_status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.findit_status_label.setWordWrap(True)
        status_layout.addWidget(self.findit_status_label)
        status_layout.addStretch()

        self.findit_stack.addWidget(self.findit_status_page)

        actions = QHBoxLayout()

        def action_metrics(S):
            actions.setSpacing(S(9))
            actions.setContentsMargins(S(10), 0, S(10), 0)

        self._scaled(action_metrics)

        self.open_button = QPushButton("Open", panel)
        self.open_button.setObjectName("secondaryButton")
        self.open_button.clicked.connect(self._open_selected_findit)
        actions.addWidget(self.open_button)
        actions.addStretch()

        self.open_all_button = QPushButton("Open All", panel)
        self.open_all_button.setObjectName("primaryButton")
        self.open_all_button.clicked.connect(self._open_all_findit)
        actions.addWidget(self.open_all_button)

        layout.addLayout(actions)

        self.set_findit_status("ready")
        return panel

    # ------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------
    def _go_findit(self, *_):
        first_line = self.search_edit.document().firstBlock().text().strip()
        if not first_line:
            return
        url = QUrl(f"https://findit.asml.com/search?q={first_line}")
        scheme = url.scheme().lower()
        if scheme in {"https", "http"} and url.isValid() and url.host():
            QDesktopServices.openUrl(url)

    def check_emptiness(self, *_):
        # One panel visible => half-width window.
        # self._single_panel = self.findit_list.count() == 0 or self.sap_list.count() == 0
        self._apply_size()
        QTimer.singleShot(0, self._layout_panels)

    def set_findit_status(self, state: str, message: str = ""):
        if state not in ("canceled", "searching", "failed", "ready"):
            raise ValueError(f"Unknown FindIt state: {state}")

        if state == "ready":
            self.findit_stack.setCurrentWidget(self.findit_list)
            self.findit_spinner.hide()
            count = self.findit_list.count()
            self.findit_count.setText(f"{count} results")
            self._update_actions()
            return

        searching = state == "searching"

        self.findit_status_label.setText(
            message or ("Searching..." if searching else "Search failed.")
        )
        self.findit_status_label.setStyleSheet(
            "color: #738399;" if searching else "color: #C34242;"
        )

        self.findit_spinner.setVisible(searching)
        self.findit_stack.setCurrentWidget(self.findit_status_page)

        self.findit_count.setText("Searching..." if searching else "Failed")
        self.open_button.setEnabled(False)
        self.open_all_button.setEnabled(False)

    def begin_sap_open(self) -> bool:
        """Return False if another SAP operation is already running."""
        if self._sap_busy:
            return False
        self._sap_busy = True

        self.sap_list.setEnabled(False)
        self.sap_status.setText("Opening SAP...")
        self.sap_status.setStyleSheet("color: #738399;")
        self.sap_status.show()
        self.sap_spinner.show()
        QApplication.processEvents()
        return True

    def set_sap_progress(self, message: str):
        if self._sap_busy:
            self.sap_status.setText(message)

    def finish_sap_open(self, success: bool = True, message: str = ""):
        self._sap_busy = False

        self.sap_spinner.hide()
        self.sap_list.setEnabled(True)

        if success:
            self.sap_status.clear()
            self.sap_status.hide()
        else:
            self.sap_status.setText(message or "Failed to open SAP.")
            self.sap_status.setStyleSheet("color: #C34242;")
            self.sap_status.show()

    # ------------------------------------------------------
    # Public API: populate from your actual plugin results
    # ------------------------------------------------------
    def set_query(self, text: str) -> None:
        self.search_edit.setText(text)
        self._request_search()

    def set_findit_results(
        self,
        results: list[FindItResult] | tuple[FindItResult, ...],
    ) -> None:
        self.set_findit_status("ready")
        self.findit_list.clear()
        for result in results:
            item = QListWidgetItem(
                AppIcon.icon(result.kind), f"{result.title} - {result.subtitle}"
            )
            item.setToolTip(result.subtitle)
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.findit_list.addItem(item)

        count = self.findit_list.count()
        self.findit_count.setText(
            f"{count} result" if count == 1 else f"{count} results"
        )
        self._update_actions()

    def set_sap_transactions(
        self,
        transactions: list[SapTransaction] | tuple[SapTransaction, ...],
    ) -> None:
        self.sap_list.clear()
        for transaction in transactions:
            self.append_sap_transactions(transaction)

    def append_sap_transactions(self, transaction: SapTransaction) -> None:
        item = QListWidgetItem(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
            (
                f"{transaction.code}\n{transaction.description}"
                if transaction.description
                else transaction.code
            ),
        )
        item.setData(Qt.ItemDataRole.UserRole, transaction)
        self.sap_list.addItem(item)
        self.sap_count.setText(f"{self.sap_list.count()} available")

    def set_busy(self, busy: bool) -> None:
        self.search_button.setEnabled(not busy)
        self.search_edit.setEnabled(not busy)
        self.search_button.setText("Searching..." if busy else "Search")

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    # ------------------------------------------------------
    # Actions
    # ------------------------------------------------------
    def _request_search(self) -> None:
        query = self.search_edit.text().strip()
        if not query:
            self.search_edit.setFocus()
            self.set_status("Enter a reference before searching.")
            return
        self.set_findit_status("searching")

        self.sap_list.clear()
        self.sap_count.setText("0 available")

        self.finish_sap_open()
        self.findit_list.clear()
        self.findit_handler(query)
        self.sap_handler(query)

    def findit_handler(self, text):
        target_items = extract_search_items(text)
        if not target_items:
            self.set_findit_status("failed", "Item(s) not found!")
            self.findit_list.clear()
            return
        self.search_worker = Findit(target_items)
        self.search_worker.result_readay.connect(self.set_findit_results)
        self.search_worker.start()

    def handle_result(self, data_list: list):
        results = []
        for data in data_list:
            results.append(
                FindItResult(
                    kind=data["type"],
                    title=data["text"],
                    subtitle=data.get("subtitle", ""),
                    link=data["url"],
                )
            )
        self.set_findit_results(results)

    def sap_handler(self, text):
        if not text:
            return
        items = extract_items(text)
        if not items:
            return
        options = SAPOptions(
            material=(items.material_12NC[0] if items.material_12NC else ""),
            machine=(items.machine_nr[0] if items.machine_nr else ""),
            service_order=(items.service_order[0] if items.service_order else ""),
        )
        self.build_sap_menu(options=options)

    def build_sap_menu(self, options: SAPOptions):
        operations = self.get_available_operations(options)
        if not operations:
            return None
        self.sap_list.clear()
        for operation in operations:
            info = SAP_OPERATIONS[operation]
            item = QListWidgetItem(AppIcon.icon("sap"), f"{info.title}")
            item.setData(Qt.ItemDataRole.UserRole, (operation, options))
            self.sap_list.addItem(item)
        self.sap_count.setText(f"{self.sap_list.count()} available")

    def get_available_operations(self, options: SAPOptions) -> list:
        available = []
        for operation, info in SAP_OPERATIONS.items():
            if any(getattr(options, field, "") for field in info.inputs):
                available.append(operation)
        return available

    def _open_findit_item(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(result, FindItResult):
            return

        url = QUrl(result.link)
        scheme = url.scheme().lower()

        if scheme in {"https", "http"} and url.isValid() and url.host():
            if not QDesktopServices.openUrl(url):
                self.set_status(f"Could not open: {result.title}")
            return

        self.findit_link_requested.emit(result.link)

    def _open_sap_item(self, item: QListWidgetItem) -> None:
        if not self.begin_sap_open():
            return
        operation, options = item.data(Qt.ItemDataRole.UserRole)
        try:
            self.set_sap_progress("Waiting for SAP transaction...")
            QTimer.singleShot(0, lambda: self.sap.execute(operation, options))
        except Exception as exc:
            self.finish_sap_open(success=False, message=str(exc))

    def _open_selected_findit(self) -> None:
        for item in self.findit_list.selectedItems():
            self._open_findit_item(item)

    def _open_all_findit(self) -> None:
        for index in range(self.findit_list.count()):
            self._open_findit_item(self.findit_list.item(index))

    def _update_actions(self) -> None:
        self.open_button.setEnabled(bool(self.findit_list.selectedItems()))
        self.open_all_button.setEnabled(self.findit_list.count() > 0)

    # ------------------------------------------------------
    # Qt events
    # ------------------------------------------------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.search_edit.setFocus()
        handle = self.windowHandle()
        if handle is not None:
            handle.screenChanged.connect(
                self._on_screen_changed, Qt.ConnectionType.UniqueConnection
            )
        QTimer.singleShot(0, self._layout_panels)

    def shutdown(self):
        self.sap.stop()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window_handle = self.window().windowHandle()
            if window_handle and window_handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)


if __name__ == "__main__":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    popup = FinditSAPUI()

    # Preview only: these are transaction codes you mentioned.
    # Populate real availability from your plugin/controller.
    # popup.set_sap_transactions(
    #     [
    #         SapTransaction("MMBE"),
    #         SapTransaction("ZMRN"),
    #         SapTransaction("IW73"),
    #         SapTransaction("IE03"),
    #     ]
    # )
    # popup.set_findit_results(
    #     [
    #         FindItResult(
    #             kind="procedure", title="cme123.adj", subtitle="ZLLN calibrate"
    #         ),
    #         FindItResult(kind="cerberus", title="SERV.456.78901"),
    #         FindItResult(kind="air", title="P900109"),
    #         FindItResult(kind="procedure", title="cme123.adj"),
    #     ]
    # )

    popup.show()
    sys.exit(app.exec())
