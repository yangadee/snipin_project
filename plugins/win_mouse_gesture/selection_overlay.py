"""
Main class: _SelectionPopup
- use widget frame rect as selection rect

"""

# ============================================================
# Disable Qt logical-pixel scaling.
# Must be set before importing PyQt6.
# ============================================================

from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, pyqtSlot
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen
from PyQt6.QtWidgets import QStyle, QStyleOption, QWidget
from utils.capture_virtual_desktop import get_virtual_screen_rect


import sys
import ctypes

# 引入 Windows 底層 API
USER32 = ctypes.windll.user32 if sys.platform == "win32" else None
SWP_NOCOPYBITS = 0x0100
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOSIZE = 0x0001  # 告訴系統：不要改變大小，只管移動
SWP_NOMOVE = 0x0002  # 告訴系統：不要改變位置，只管縮放
SC_SIZE = 0xF000

# 錨點邊界定義
WMSZ_LEFT = 1
WMSZ_RIGHT = 2
WMSZ_TOP = 3
WMSZ_TOPLEFT = 4  # 你出問題的方向（右下角為錨點）
WMSZ_TOPRIGHT = 5
WMSZ_BOTTOM = 6
WMSZ_BOTTOMLEFT = 7
WMSZ_BOTTOMRIGHT = 8


class SelectionPopup(QWidget):
    """Lightweight click-through selection rectangle."""

    BORDER_WIDTH = 2
    BORDER_COLOR = QColor(0, 120, 215)

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.ToolTip
            | Qt.WindowType.WindowStaysOnTopHint,
            # | Qt.WindowType.NoDropShadowWindowHint,
            # | Qt.WindowType.WindowTransparentForInput,
        )
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setStyleSheet("""
            SelectionPopup {
                border: 2px solid #3498db;
                background-color: transparent;
            }
        """)

    @pyqtSlot(int, int)
    def begin_selection(self, global_x: int, global_y: int):
        # Avoid showing a 0 x 0 native window.
        self.setGeometry(global_x, global_y, 1, 1)
        self.show()
        self.raise_()

    @pyqtSlot(int, int, int, int)
    def update_selection(self, x0: int, y0: int, x1: int, y1: int):
        global_rect = QRect(QPoint(x0, y0), QPoint(x1, y1)).normalized()

        # self.safe_set_geometry(global_rect)
        self.setUpdatesEnabled(False)
        self.setGeometry(global_rect)
        self.setUpdatesEnabled(True)

    def safe_set_geometry(self, rect):
        hwnd = int(self.winId())
        self.setUpdatesEnabled(False)
        SWP_NOSENDCHANGING = 0x0400
        SWP_DEFERERASE = 0x2000
        USER32.SetWindowPos(
            hwnd,
            0,
            rect.x(),
            rect.y(),
            rect.width(),
            rect.height(),
            SWP_NOCOPYBITS
            | SWP_NOACTIVATE
            | SWP_NOSENDCHANGING
            | SWP_DEFERERASE
            | SWP_FRAMECHANGED,
        )
        if self.windowHandle():
            self.windowHandle().setGeometry(rect)

        self.setUpdatesEnabled(True)

    @pyqtSlot(int, int, int, int)
    def finish_selection(self, x0: int, y0: int, x1: int, y1: int):
        self.update_selection(x0, y0, x1, y1)
        self.hide()

    @pyqtSlot()
    def clear_selection(self):
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        pen = QPen(
            self.BORDER_COLOR,
            self.BORDER_WIDTH,
            Qt.PenStyle.SolidLine,
        )
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = self.BORDER_WIDTH / 2.0
        border_rect = QRectF(self.rect()).adjusted(
            inset,
            inset,
            -inset,
            -inset,
        )
        painter.drawRect(border_rect)
