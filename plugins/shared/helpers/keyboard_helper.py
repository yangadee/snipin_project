import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_C = 0x43


# ULONG_PTR follows the current Python process architecture.
if ctypes.sizeof(ctypes.c_void_p) == 8:
    ULONG_PTR = ctypes.c_ulonglong
else:
    ULONG_PTR = ctypes.c_ulong


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
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)

    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


LPINPUT = ctypes.POINTER(INPUT)

user32.SendInput.argtypes = (wintypes.UINT, LPINPUT, ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


def make_keyboard_input(
    virtual_key: int,
    *,
    key_up: bool = False,
) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD

    event.ki.wVk = virtual_key
    event.ki.wScan = 0
    event.ki.dwFlags = KEYEVENTF_KEYUP if key_up else 0
    event.ki.time = 0
    event.ki.dwExtraInfo = 0

    return event


def send_ctrl_c() -> bool:
    events = (INPUT * 4)(
        make_keyboard_input(VK_CONTROL),
        make_keyboard_input(VK_C),
        make_keyboard_input(VK_C, key_up=True),
        make_keyboard_input(VK_CONTROL, key_up=True),
    )

    input_size = ctypes.sizeof(INPUT)

    # print("Pointer size:", ctypes.sizeof(ctypes.c_void_p))
    # print("INPUT size:", input_size)
    # print("KEYBDINPUT size:", ctypes.sizeof(KEYBDINPUT))

    ctypes.set_last_error(0)

    sent = user32.SendInput(
        len(events), events, input_size  # Size of one INPUT, not the array.
    )

    if sent != len(events):
        error = ctypes.get_last_error()
        # print(
        #     "SendInput failed or incomplete: "
        #     f"sent={sent}/{len(events)}, "
        #     f"error={error}"
        # )
        return False
    # print(f"SendInput succeeded: {sent}/{len(events)}")
    return True
