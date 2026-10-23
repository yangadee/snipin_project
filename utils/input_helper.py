import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
# ------------------------------------------
# MASK KEY SendInput definitions
# ------------------------------------------
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_F24 = 0x87
VK_MASK_KEY = VK_CONTROL  # Choose mask key

# ------------------------------------------
# MOUSE MASK CLICK
# ------------------------------------------
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SNIPIN_MOUSE_EVENT = 0x534E4950  # "SNIP"

# ============================================================
# Win32 types
# ============================================================
ULONG_PTR = wintypes.WPARAM
LRESULT = wintypes.LPARAM
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


def send_mask_key() -> bool:
    """
    Send VK_MASK_KEY as maskey
    """
    inputs = (INPUT * 2)()
    # MASKEY DOWN
    inputs[0].type = INPUT_KEYBOARD
    inputs[0].ki = KEYBDINPUT(
        wVk=VK_MASK_KEY, wScan=0, dwFlags=0, time=0, dwExtraInfo=0
    )
    # MASKEY UP
    inputs[1].type = INPUT_KEYBOARD
    inputs[1].ki = KEYBDINPUT(
        wVk=VK_MASK_KEY, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0
    )
    ctypes.set_last_error(0)
    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if sent != 2:
        error = ctypes.get_last_error()
        print("send mask key failed", {ctypes.WinError(error)})
        return False
    return True


def send_click():
    inputs = (INPUT * 2)()
    # Left down
    inputs[0].type = INPUT_MOUSE
    inputs[0].mi.dwFlags = MOUSEEVENTF_LEFTDOWN
    inputs[0].mi.dwExtraInfo = SNIPIN_MOUSE_EVENT

    # Left up
    inputs[1].type = INPUT_MOUSE
    inputs[1].mi.dwFlags = MOUSEEVENTF_LEFTUP
    inputs[1].mi.dwExtraInfo = SNIPIN_MOUSE_EVENT

    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    ctypes.set_last_error(0)
    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if sent != 2:
        error = ctypes.get_last_error()
        return False
    return True
