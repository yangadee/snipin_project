import ctypes
import atexit
from ctypes import wintypes

# =======================
# QPixmap -> HCURSOR
# =======================

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


# =======================
# Win32 structures
# =======================
class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = wintypes.HANDLE
user32.SetSystemCursor.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
]
user32.SetSystemCursor.restype = wintypes.BOOL
gdi32.CreateBitmap.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_void_p,
]
gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL


def pixmap_to_hcursor(pixmap: QPixmap, hotspot_x: int, hotspot_y: int):
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width = image.width()
    height = image.height()
    bits = image.bits()
    bits.setsize(image.sizeInBytes())
    color_bitmap = gdi32.CreateBitmap(
        width,
        height,
        1,
        32,
        bits.asstring(image.sizeInBytes()),
    )
    # required mask bitmap
    mask_bytes = bytes((0xFF,)) * ((width * height + 7) // 8)
    mask_bitmap = gdi32.CreateBitmap(
        width,
        height,
        1,
        1,
        mask_bytes,
    )
    if not color_bitmap or not mask_bitmap:
        raise ctypes.WinError()
    iconinfo = ICONINFO()
    iconinfo.fIcon = False
    iconinfo.xHotspot = hotspot_x
    iconinfo.yHotspot = hotspot_y
    iconinfo.hbmMask = mask_bitmap
    iconinfo.hbmColor = color_bitmap
    hcursor = user32.CreateIconIndirect(ctypes.byref(iconinfo))
    gdi32.DeleteObject(mask_bitmap)
    gdi32.DeleteObject(color_bitmap)
    if not hcursor:
        raise ctypes.WinError()
    return hcursor


def create_custom_cursor_pixmap():
    cursor_size = 31

    pixmap = QPixmap(cursor_size, cursor_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    center = cursor_size // 2
    gap = 2
    length = 15

    # black outline
    painter.setPen(QPen(QColor(0, 0, 0), 3))
    painter.drawLine(center - length, center, center - gap, center)
    painter.drawLine(center + gap, center, center + length, center)
    painter.drawLine(center, center - length, center, center - gap)
    painter.drawLine(center, center + gap, center, center + length)

    # white core
    painter.setPen(QPen(QColor(255, 255, 255), 1))
    painter.drawLine(center - length, center, center - gap, center)
    painter.drawLine(center + gap, center, center + length, center)
    painter.drawLine(center, center - length, center, center - gap)
    painter.drawLine(center, center + gap, center, center + length)

    painter.end()

    return pixmap, center


class SystemCursorEngine:
    SPI_SETCURSORS = 0x0057
    IDC_CROSS = 32515

    CURSOR_IDS = [
        32512,  # OCR_NORMAL
        32513,  # OCR_IBEAM
        32514,  # OCR_WAIT
        32515,  # OCR_CROSS
        32516,  # OCR_UP
        32642,  # OCR_SIZENWSE
        32643,  # OCR_SIZENESW
        32644,  # OCR_SIZEWE
        32645,  # OCR_SIZENS
        32646,  # OCR_SIZEALL
        32648,  # OCR_NO
        32649,  # OCR_HAND
        32650,  # OCR_APPSTARTING
        32651,  # OCR_HELP
    ]

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.active = False
        self.HCURSOR = wintypes.HANDLE
        self.HICON = wintypes.HANDLE
        self.user32.LoadCursorW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
        ]
        self.user32.LoadCursorW.restype = self.HCURSOR
        self.user32.CopyIcon.argtypes = [self.HICON]
        self.user32.CopyIcon.restype = self.HICON
        self.user32.SetSystemCursor.argtypes = [
            self.HCURSOR,
            wintypes.DWORD,
        ]
        self.user32.SetSystemCursor.restype = wintypes.BOOL
        self.user32.SystemParametersInfoW.argtypes = [
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            wintypes.UINT,
        ]
        self.user32.SystemParametersInfoW.restype = wintypes.BOOL
        atexit.register(self.restore)

    def _res(self, value):
        return ctypes.cast(ctypes.c_void_p(value), wintypes.LPCWSTR)

    def set_cross(self):
        pixmap, center = create_custom_cursor_pixmap()
        if not pixmap:
            raise ctypes.WinError()
        for cursor_id in self.CURSOR_IDS:
            cur = pixmap_to_hcursor(
                pixmap,
                center,
                center,
            )
            if not cur:
                raise ctypes.WinError()
            if not self.user32.SetSystemCursor(cur, cursor_id):
                raise ctypes.WinError()
        self.active = True

    # ======================================================
    # Set cursor to system default cross IDC_CROSS = 32515
    # ======================================================
    def set_default_cross(self):
        base = self.user32.LoadCursorW(
            None,
            self._res(self.IDC_CROSS),
        )
        if not base:
            raise ctypes.WinError()
        pixmap, center = create_custom_cursor_pixmap()
        if not pixmap:
            raise ctypes.WinError()
        for cursor_id in self.CURSOR_IDS:
            cur = self.user32.CopyIcon(base)
            if not cur:
                raise ctypes.WinError()
            if not self.user32.SetSystemCursor(cur, cursor_id):
                raise ctypes.WinError()
        self.active = True

    def restore(self):
        if not self.active:
            return
        if not self.user32.SystemParametersInfoW(
            self.SPI_SETCURSORS,
            0,
            None,
            0,
        ):
            raise ctypes.WinError()
        self.active = False

    # # Safe destroyed
    # def __del__(self):
    #     self.restore()
    #     print("💥System cursor safe destroyed")
