# ======================================================================
# Set HWND TRANSPARENT Hit-test window
# ======================================================================
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
if ctypes.sizeof(ctypes.c_void_p) == 8:
    GetWindowLongPtr = user32.GetWindowLongPtrW
    SetWindowLongPtr = user32.SetWindowLongPtrW
else:
    GetWindowLongPtr = user32.GetWindowLongW
    SetWindowLongPtr = user32.SetWindowLongW
GetWindowLongPtr.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
]
GetWindowLongPtr.restype = ctypes.c_ssize_t
SetWindowLongPtr.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_ssize_t,
]
SetWindowLongPtr.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL


def set_hwnd_transparent(hwnd: int, transparent: bool = False):
    """
    Temporarily make the overlay transparent to Windows input hit testing.
    This is used only while calling WindowFromPoint/ UIA ElementFromPoint(), so UIA sees the
    application underneath the overlay instead of the overlay itself.
    """
    current_style = GetWindowLongPtr(
        hwnd,
        GWL_EXSTYLE,
    )
    if transparent:
        new_style = current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
    else:
        new_style = current_style & ~WS_EX_TRANSPARENT
    if new_style == current_style:
        return
    ctypes.set_last_error(0)
    previous_style = SetWindowLongPtr(
        hwnd,
        GWL_EXSTYLE,
        new_style,
    )
    error = ctypes.get_last_error()
    if previous_style == 0 and error != 0:
        print(
            "SetWindowLongPtr failed:",
            error,
        )
        return
    # Notify Windows that the extended style changed.
    # user32.SetWindowPos(
    #     hwnd,
    #     None,
    #     0,
    #     0,
    #     0,
    #     0,
    #     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    # )
    return
