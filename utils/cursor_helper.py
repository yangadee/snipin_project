import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor, QImage, QPixmap

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


# ============================================================
# Structures
# ============================================================
class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


# ============================================================
# Constants
# ============================================================
CURSOR_SHOWING = 0x00000001
DI_MASK = 0x0001
DI_IMAGE = 0x0002
DI_NORMAL = DI_MASK | DI_IMAGE
BI_RGB = 0
DIB_RGB_COLORS = 0
BLACKNESS = 0x00000042
WHITENESS = 0x00FF0062
# ============================================================
# API signatures
# ============================================================
user32.GetCursorInfo.argtypes = [
    ctypes.POINTER(CURSORINFO),
]
user32.GetCursorInfo.restype = wintypes.BOOL
user32.GetIconInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(ICONINFO),
]
user32.GetIconInfo.restype = wintypes.BOOL
user32.DrawIconEx.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.HBRUSH,
    wintypes.UINT,
]
user32.DrawIconEx.restype = wintypes.BOOL
gdi32.CreateCompatibleDC.argtypes = [
    wintypes.HDC,
]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = [
    wintypes.HDC,
]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.SelectObject.argtypes = [
    wintypes.HDC,
    wintypes.HGDIOBJ,
]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [
    wintypes.HGDIOBJ,
]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.GetObjectW.argtypes = [
    wintypes.HGDIOBJ,
    ctypes.c_int,
    ctypes.c_void_p,
]
gdi32.GetObjectW.restype = ctypes.c_int
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.PatBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi32.PatBlt.restype = wintypes.BOOL


# ============================================================
# Internal renderer
# ============================================================
def _render_cursor_on_background(
    hcursor: int, width: int, height: int, white: bool
) -> QImage | None:
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    # Top-down bitmap.
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bits = ctypes.c_void_p()
    dc = gdi32.CreateCompatibleDC(None)
    if not dc:
        return None
    dib = None
    old_bitmap = None
    try:
        dib = gdi32.CreateDIBSection(
            dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if not dib or not bits:
            return None
        old_bitmap = gdi32.SelectObject(dc, dib)
        # ----------------------------------------------------
        # Background
        # ----------------------------------------------------
        result = gdi32.PatBlt(
            dc, 0, 0, width, height, WHITENESS if white else BLACKNESS
        )
        if not result:
            return None
        # ----------------------------------------------------
        # Windows renders the actual cursor
        # ----------------------------------------------------
        result = user32.DrawIconEx(dc, 0, 0, hcursor, width, height, 0, None, DI_NORMAL)
        if not result:
            return None
        # ----------------------------------------------------
        # Copy before deleting DIB
        # ----------------------------------------------------
        image = QImage(bits.value, width, height, width * 4, QImage.Format.Format_RGB32)
        return image.copy()
    finally:
        if old_bitmap:
            gdi32.SelectObject(dc, old_bitmap)
        if dib:
            gdi32.DeleteObject(dib)
        gdi32.DeleteDC(dc)


# ============================================================
# Public API
# ============================================================
def capture_system_cursor() -> tuple[QPixmap, QPoint, QPoint] | None:
    """
    Capture the current Windows system cursor as a frozen QPixmap.
    Returns:
        (
            cursor_pixmap,
            cursor_global_position,
            cursor_hotspot)
    cursor_global_position is the cursor HOTSPOT location.
    Therefore:
        pixmap_top_left = cursor_pos - hotspot
    """
    # --------------------------------------------------------
    # Current global cursor
    # --------------------------------------------------------
    cursor_info = CURSORINFO()
    cursor_info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(cursor_info)):
        return None
    if not (cursor_info.flags & CURSOR_SHOWING):
        return None
    if not cursor_info.hCursor:
        return None
    cursor_pos = QPoint(int(cursor_info.ptScreenPos.x), int(cursor_info.ptScreenPos.y))
    # --------------------------------------------------------
    # Cursor resource information
    # --------------------------------------------------------
    icon_info = ICONINFO()
    if not user32.GetIconInfo(cursor_info.hCursor, ctypes.byref(icon_info)):
        return None
    try:
        hotspot = QPoint(int(icon_info.xHotspot), int(icon_info.yHotspot))
        # ----------------------------------------------------
        # Determine cursor dimensions
        # ----------------------------------------------------
        hbitmap = icon_info.hbmColor if icon_info.hbmColor else icon_info.hbmMask
        if not hbitmap:
            return None
        bitmap = BITMAP()
        if not gdi32.GetObjectW(hbitmap, ctypes.sizeof(BITMAP), ctypes.byref(bitmap)):
            return None
        width = int(bitmap.bmWidth)
        height = int(bitmap.bmHeight)
        # A monochrome cursor mask consists of two vertically
        # stacked bitmaps:
        #
        #   AND mask
        #   XOR mask
        #
        if not icon_info.hbmColor:
            height //= 2
        if width <= 0 or height <= 0:
            return None
        # ----------------------------------------------------
        # Render against BLACK and WHITE.
        #
        # We intentionally don't trust DrawIconEx's resulting
        # alpha channel.
        # ----------------------------------------------------
        black = _render_cursor_on_background(
            cursor_info.hCursor, width, height, white=False
        )
        white = _render_cursor_on_background(
            cursor_info.hCursor, width, height, white=True
        )
        if black is None or white is None:
            return None
        # ----------------------------------------------------
        # Reconstruct RGBA
        #
        # Standard alpha compositing:
        #
        # B = C * A
        #
        # W = C * A + 255 * (1 - A)
        #
        # Therefore:
        #
        # A = 255 - (W - B)
        #
        # ----------------------------------------------------
        output = QImage(width, height, QImage.Format.Format_ARGB32)
        output.fill(0)
        for y in range(height):
            for x in range(width):
                cb = black.pixelColor(x, y)
                cw = white.pixelColor(x, y)
                # Calculate alpha independently and average.
                ar = 255 - (cw.red() - cb.red())
                ag = 255 - (cw.green() - cb.green())
                ab = 255 - (cw.blue() - cb.blue())
                alpha = round((ar + ag + ab) / 3)
                alpha = max(0, min(255, alpha))
                if alpha == 0:
                    output.setPixelColor(x, y, QColor(0, 0, 0, 0))
                    continue
                # Recover original RGB from black-background
                # version:
                #
                # black = color * alpha
                #
                scale = 255.0 / alpha
                r = round(cb.red() * scale)
                g = round(cb.green() * scale)
                b = round(cb.blue() * scale)
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                output.setPixelColor(x, y, QColor(r, g, b, alpha))
        return (QPixmap.fromImage(output), cursor_pos, hotspot)
    finally:
        # GetIconInfo creates these bitmap objects.
        if icon_info.hbmColor:
            gdi32.DeleteObject(icon_info.hbmColor)
        if icon_info.hbmMask:
            gdi32.DeleteObject(icon_info.hbmMask)
