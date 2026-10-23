import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint, QRect, QEvent
from PyQt6.QtGui import QCursor

# ---------- Win32 definitions ----------
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
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
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


# ---------- RubberBand using reusable UpdateLayeredWindow DIB ----------
class NativeRubberBand:
    BORDER_WIDTH = 3
    # BGRA
    BORDER_COLOR = (255, 150, 0, 255)
    GROW_FACTOR = 1.5
    MIN_DIB_WIDTH = 500
    MIN_DIB_HEIGHT = 500

    def __init__(self):
        self.hwnd = None
        self.origin = QPoint()
        self.selecting = False
        self.hdc_screen = None
        self.hdc_mem = None
        # Persistent DIB
        self.hbitmap = None
        self.old_bitmap = None
        self.bits = None
        self.dib_width = 0
        self.dib_height = 0
        self._create_window()

    # ========================================================
    # Create window
    # ========================================================
    def _create_window(self):
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            "Static",
            "RubberBand",
            WS_POPUP,
            0,
            0,
            1,
            1,
            None,
            None,
            None,
            None,
        )
        self.hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)

    # ========================================================
    # Ensure DIB capacity
    # ========================================================
    def _ensure_dib(self, width: int, height: int):
        """
        Ensure persistent DIB capacity.
        Starts with a reasonable minimum size and grows geometrically.
        Never shrinks during normal use.
        """
        # ========================================================
        # Minimum capacity
        # ========================================================
        width = max(width, self.MIN_DIB_WIDTH)
        height = max(height, self.MIN_DIB_HEIGHT)
        # ========================================================
        # Already large enough
        # ========================================================
        if self.hbitmap and width <= self.dib_width and height <= self.dib_height:
            return
        # ========================================================
        # Grow geometrically
        # ========================================================
        if self.dib_width:
            new_width = max(width, int(self.dib_width * self.GROW_FACTOR))
        else:
            new_width = width
        if self.dib_height:
            new_height = max(height, int(self.dib_height * self.GROW_FACTOR))
        else:
            new_height = height
        # ========================================================
        # Remove old DIB
        # ========================================================
        if self.hbitmap:
            if self.old_bitmap:
                gdi32.SelectObject(self.hdc_mem, self.old_bitmap)
            gdi32.DeleteObject(self.hbitmap)
            self.hbitmap = None
            self.bits = None
        # ========================================================
        # Create new persistent DIB
        # ========================================================
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = new_width
        # Top-down DIB
        bmi.bmiHeader.biHeight = -new_height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB
        bits = ctypes.c_void_p()
        hbitmap = gdi32.CreateDIBSection(
            self.hdc_mem,
            ctypes.byref(bmi),
            0,  # DIB_RGB_COLORS
            ctypes.byref(bits),
            None,
            0,
        )
        if not hbitmap:
            raise ctypes.WinError(ctypes.get_last_error())
        # ========================================================
        # Select bitmap into memory DC
        # ========================================================
        previous = gdi32.SelectObject(self.hdc_mem, hbitmap)
        self.old_bitmap = previous
        self.hbitmap = hbitmap
        self.bits = bits
        self.dib_width = new_width
        self.dib_height = new_height
        # ========================================================
        # Initial transparent surface
        # ========================================================
        ctypes.memset(self.bits, 0, new_width * new_height * 4)

    # ========================================================
    # Update
    # ========================================================
    def _update(self, rect: QRect):
        rect = rect.normalized()
        w = rect.width()
        h = rect.height()
        if w < 2 or h < 2:
            self.hide()
            return
        # ========================================================
        # Ensure DIB
        # ========================================================
        self._ensure_dib(w, h)
        stride = self.dib_width * 4
        base = self.bits.value
        # ========================================================
        # Clear used area
        # ========================================================
        for y in range(h):
            ctypes.memset(base + y * stride, 0, w * 4)
        # ========================================================
        # Border
        # ========================================================
        bw = min(self.BORDER_WIDTH, w // 2, h // 2)
        color = self.BORDER_COLOR
        self._fill_bgra(0, 0, w, bw, color)  # Top
        self._fill_bgra(0, h - bw, w, bw, color)  # Bottom
        self._fill_bgra(0, bw, bw, h - 2 * bw, color)  # Left
        self._fill_bgra(w - bw, bw, bw, h - 2 * bw, color)  # Right
        # ========================================================
        # Update layered window
        # ========================================================
        pt_dst = POINT(rect.x(), rect.y())
        size = SIZE(w, h)
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd,
            self.hdc_screen,
            ctypes.byref(pt_dst),
            ctypes.byref(size),
            self.hdc_mem,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        user32.ShowWindow(self.hwnd, 5)  # SW_SHOW

    def _fill_bgra(self, x, y, width, height, color):
        if width <= 0 or height <= 0:
            return
        b, g, r, a = color
        pixel = bytes((b, g, r, a))
        row_data = pixel * width
        row_size = width * 4
        stride = self.dib_width * 4
        base = self.bits.value
        for row in range(y, y + height):
            ctypes.memmove(base + row * stride + x * 4, row_data, row_size)

    # ========================================================
    # Hide
    # ========================================================
    def hide(self):
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)  # SW_HIDE

    # ========================================================
    # Destroy
    # ========================================================
    def destroy(self):
        # ----------------------------------------------------
        # Bitmap
        # ----------------------------------------------------
        if self.hbitmap:
            # Must restore original bitmap before deleting ours.
            if self.old_bitmap:
                gdi32.SelectObject(self.hdc_mem, self.old_bitmap)
            gdi32.DeleteObject(self.hbitmap)
            self.hbitmap = None
            self.old_bitmap = None
            self.bits = None
            self.dib_width = 0
            self.dib_height = 0
        # ----------------------------------------------------
        # Memory DC
        # ----------------------------------------------------
        if self.hdc_mem:
            gdi32.DeleteDC(self.hdc_mem)
            self.hdc_mem = None
        # ----------------------------------------------------
        # Screen DC
        # ----------------------------------------------------
        if self.hdc_screen:
            user32.ReleaseDC(None, self.hdc_screen)
            self.hdc_screen = None
        # ----------------------------------------------------
        # Window
        # ----------------------------------------------------
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def __del__(self):
        self.destroy()
