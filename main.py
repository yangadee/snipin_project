import sys
import ctypes
from ctypes import wintypes

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, QTimer
from PyQt6.QtGui import QGuiApplication, QPainter, QColor, QPen

import comtypes
import comtypes.client

# --- generate / import the UIA COM wrapper (first run is slower, then cached) ---
comtypes.client.GetModule('UIAutomationCore.dll')
import comtypes.gen.UIAutomationClient as UIA  # noqa: E402

comtypes.CoInitialize()

user32 = ctypes.windll.user32
user32.PhysicalToLogicalPointForPerMonitorDPI.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.POINT)
]
user32.PhysicalToLogicalPointForPerMonitorDPI.restype = wintypes.BOOL


class HitTestOverlay(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Click-through: mouse events pass through to real windows below,
        # so UIA hit-testing hits the actual UI, not our overlay.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.virtual_rect = QRect()
        for screen in QGuiApplication.screens():
            self.virtual_rect = self.virtual_rect.united(screen.geometry())
        self.setGeometry(self.virtual_rect)

        self.showFullScreen()

        # UIA COM object
        self.uia = comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)

        self.current_rect = None   # QRect in overlay-local logical coords
        self.current_label = ""

        self.hwnd = int(self.winId())

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_hit_test)
        self.timer.start(50)  # ~20 fps polling

    # ---- physical -> logical conversion (handles mixed DPI correctly) ----
    def physical_point_to_logical(self, x, y):
        pt = wintypes.POINT(x, y)
        user32.PhysicalToLogicalPointForPerMonitorDPI(self.hwnd, ctypes.byref(pt))
        return QPoint(pt.x, pt.y)

    def poll_hit_test(self):
        # Physical cursor position (true physical pixels, since our process
        # is Per-Monitor DPI V2 aware).
        cpt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(cpt))

        try:
            pt = UIA.tagPOINT(cpt.x, cpt.y) if hasattr(UIA, "tagPOINT") else wintypes.POINT(cpt.x, cpt.y)
            element = self.uia.ElementFromPoint(pt)
        except Exception:
            element = None

        if element is None:
            if self.current_rect is not None:
                self.current_rect = None
                self.update()
            return

        try:
            rect = element.CurrentBoundingRectangle  # physical px: left, top, right, bottom
            name = element.CurrentName or ""
            ctrl_type = element.CurrentLocalizedControlType or ""
            cls_name = element.CurrentClassName or ""
        except Exception:
            return

        if rect.right <= rect.left or rect.bottom <= rect.top:
            # zero-size / off-screen element (e.g. desktop root) — skip
            self.current_rect = None
            self.update()
            return

        top_left = self.physical_point_to_logical(rect.left, rect.top)
        bottom_right = self.physical_point_to_logical(rect.right, rect.bottom)

        # convert global logical -> overlay-local logical
        local_tl = top_left - self.virtual_rect.topLeft()
        local_br = bottom_right - self.virtual_rect.topLeft()

        self.current_rect = QRect(local_tl, local_br).normalized()
        self.current_label = f"{ctrl_type or cls_name}  \"{name[:60]}\""
        self.update()

    def paintEvent(self, event):
        if not self.current_rect:
            return
        painter = QPainter(self)
        pen = QPen(QColor(0, 220, 255), 2)
        painter.setPen(pen)
        painter.drawRect(self.current_rect)

        painter.setPen(QColor(255, 255, 255))
        label_pos = self.current_rect.topLeft() + QPoint(4, -6)
        if label_pos.y() < 10:
            label_pos = self.current_rect.topLeft() + QPoint(4, 16)
        painter.fillRect(
            label_pos.x() - 2, label_pos.y() - 14,
            min(600, painter.fontMetrics().horizontalAdvance(self.current_label) + 6), 18,
            QColor(0, 0, 0, 180)
        )
        painter.drawText(label_pos, self.current_label)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()


def main():
    app = QApplication(sys.argv)
    overlay = HitTestOverlay()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()