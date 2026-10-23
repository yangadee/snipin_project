import time

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter
from PyQt6.QtWidgets import QApplication


def capture_qt_virtual_desktop_image():
    screens = QApplication.screens()
    virtual_rect = QRect()
    for screen in screens:
        virtual_rect = virtual_rect.united(screen.geometry())
    desktop_image = QImage(virtual_rect.size(), QImage.Format.Format_RGB32)
    desktop_image.fill(Qt.GlobalColor.black)
    painter = QPainter(desktop_image)
    for screen in screens:
        geometry = screen.geometry()
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            continue
        target = geometry.translated(-virtual_rect.left(), -virtual_rect.top())
        painter.drawPixmap(target, pixmap)
    painter.end()
    return desktop_image, virtual_rect


def capture_qt_virtual_desktop_pixmap():
    t0 = time.perf_counter_ns()
    screens = QApplication.screens()
    virtual_rect = QRect()
    for screen in screens:
        virtual_rect = virtual_rect.united(screen.geometry())
    # print(f"get virtual_rect time: {(time.perf_counter_ns()-t0)// 1_000_000} ms")
    desktop_pixmap = QPixmap(virtual_rect.size())
    # desktop_pixmap.fill(Qt.GlobalColor.black) # Try remove for full image.s
    painter = QPainter(desktop_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    for screen in screens:
        t1 = time.perf_counter_ns()
        geometry = screen.geometry()
        pixmap = screen.grabWindow(0)

        if pixmap.isNull():
            continue
        target = geometry.translated(-virtual_rect.left(), -virtual_rect.top())
        painter.drawPixmap(target, pixmap)
        print(
            f"capture screen {screen.name()} time: {(time.perf_counter_ns()-t1)// 1_000_000} ms"
        )
    painter.end()
    print(
        f"capture_qt_virtual_desktop_pixmap time: {(time.perf_counter_ns()-t0)// 1_000_000} ms"
    )
    return desktop_pixmap, virtual_rect


def get_virtual_screen_rect() -> QRect:
    screens = QApplication.screens()
    virtual_rect = QRect()
    for screen in screens:
        virtual_rect = virtual_rect.united(screen.geometry())
    return virtual_rect


import ctypes
from ctypes import wintypes
import time

# ======================================================================
# Windows APIs
# ======================================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
# GetSystemMetrics constants
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
# GDI constants
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
BI_RGB = 0


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


def get_physical_virtual_geometry():
    """
    Return the complete Windows virtual desktop geometry in physical pixels.
    The returned QRect is in Windows global physical coordinates and may
    have a negative X or Y origin.
    """
    return QRect(
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def capture_physical_virtual_desktop():
    """
    Capture the complete Windows virtual desktop with GDI.
    Returns:
        tuple:
            QImage containing physical pixels
            QRect containing global physical virtual desktop geometry
    """
    virtual_rect = get_physical_virtual_geometry()
    x = virtual_rect.x()
    y = virtual_rect.y()
    width = virtual_rect.width()
    height = virtual_rect.height()
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid virtual desktop size: {width} x {height}")
    screen_dc = user32.GetDC(None)
    if not screen_dc:
        raise RuntimeError("GetDC failed")
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    if not memory_dc:
        user32.ReleaseDC(None, screen_dc)
        raise RuntimeError("CreateCompatibleDC failed")
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    if not bitmap:
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(None, screen_dc)
        raise RuntimeError("CreateCompatibleBitmap failed")
    old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        copied = gdi32.BitBlt(
            memory_dc, 0, 0, width, height, screen_dc, x, y, SRCCOPY | CAPTUREBLT
        )
        if not copied:
            raise RuntimeError("BitBlt failed")
        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        # Negative height requests a top-down image.
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = BI_RGB
        byte_count = width * height * 4
        pixel_buffer = ctypes.create_string_buffer(byte_count)
        rows = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            pixel_buffer,
            ctypes.byref(bitmap_info),
            DIB_RGB_COLORS,
        )
        if rows != height:
            raise RuntimeError(f"GetDIBits returned {rows} rows, expected {height}")
        # GDI 32-bit DIB layout is BGRA, which matches
        # QImage.Format_ARGB32 on little-endian Windows.
        image = QImage(
            pixel_buffer.raw, width, height, width * 4, QImage.Format.Format_ARGB32
        ).copy()
        return QPixmap.fromImage(image), virtual_rect
    finally:
        gdi32.SelectObject(memory_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(None, screen_dc)
