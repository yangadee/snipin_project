"""
Main class: WinMouseDragDetector
    mouse + keyboard hooks on thread.
"""

import time
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import QThread, pyqtSignal

# ============================================================
# Win32 constants
# ============================================================
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
VK_LWIN = 0x5B
VK_RWIN = 0x5C
LLKHF_INJECTED = 0x00000010
LLMHF_INJECTED = 0x00000001
PM_NOREMOVE = 0x0000

WM_TIMER = 0x0113
WATCHDOG_TIMER_ID = 1
WATCHDOG_INTERVAL_MS = 500

# ------------------------------------------
# MASK KEY SendInput definitions
# ------------------------------------------
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_F24 = 0x87
MASK_KEY = VK_CONTROL  # Choose mask key
# ------------------------------------------
# MOUSE MASK CLICK
# ------------------------------------------
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SNIPIN_MOUSE_EVENT = 0x534E4950  # "SNIP"

GESTURE_WIN_LEFT = 1
GESTURE_WIN_RIGHT = 2
GESTURE_LEFT_RIGHT = 3
VK_LBUTTON = 0x01  # Left mouse button
VK_RBUTTON = 0x02  # Right mouse button

# ============================================================
# Win32 types
# ============================================================
ULONG_PTR = wintypes.WPARAM
LRESULT = wintypes.LPARAM
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


# ============================================================
# DLL setup
# ============================================================
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = LRESULT
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.GetMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


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


MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010


def _send_mouse_up(button: int) -> None:
    if button == VK_LBUTTON:
        flags = MOUSEEVENTF_LEFTUP

    elif button == VK_RBUTTON:
        flags = MOUSEEVENTF_RIGHTUP

    else:
        return
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
    res = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if res != 1:
        error = ctypes.get_last_error()
        print(f"{ctypes.WinError(error)}")
        return False


# ============================================================
# Hook thread
# ============================================================
class WinMouseDragDetector(QThread):
    # init signal.
    hook_error = pyqtSignal(str)
    hooks_started = pyqtSignal()
    hooks_stopped = pyqtSignal()

    # runtime signal.
    drag_started = pyqtSignal(int, int)
    drag_moved = pyqtSignal(int, int, int, int)
    drag_finished = pyqtSignal(int, int, int, int)
    right_drag_finished = pyqtSignal(int, int, int, int)

    # Constant
    DRAG_THRESHOLD = 5
    TARGET_FPS = 60  # hz
    _NS_PER_SECOND = 1_000_000_000
    WATCHDOG_INTERVAL_MS = 500
    KEY_STUCK_TIMEOUT_NS = 10 * _NS_PER_SECOND
    KEY_STUCK_TIMEOUT = 10.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread_id = 0
        self._mouse_hook = None
        self._keyboard_hook = None
        # Keep callback objects alive.
        self._mouse_callback = HOOKPROC(self._mouse_proc)
        self._keyboard_callback = HOOKPROC(self._keyboard_proc)
        self._stop_requested = False
        self._suspended = False
        # self._win_down = False
        self._mouse_down = False
        self._left_down = False
        self._right_down = False

        self._dragging = False
        self._drag_button = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._last_x = 0
        self._last_y = 0
        self._drag_threshold = 5
        self._gesture_used_win = None
        self._mask_win_release = None

        self.interval_ns = int(1_000_000_000 // self.TARGET_FPS)
        self.last_time_ns = time.perf_counter_ns()

        self._keys_down: dict[int, int] = {}

    @property
    def _win_down(self) -> bool:
        return VK_LWIN in self._keys_down or VK_RWIN in self._keys_down

    @property
    def _win_physical_down(self) -> bool:
        return bool(
            user32.GetAsyncKeyState(VK_LWIN) & 0x8000
            or user32.GetAsyncKeyState(VK_RWIN) & 0x8000
        )

    def run(self):
        """
        Everything in this function runs on the hook thread.
        """
        self._thread_id = kernel32.GetCurrentThreadId()
        self._stop_requested = False
        # Force creation of this thread's Win32 message queue.
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)
        module_handle = kernel32.GetModuleHandleW(None)
        self._mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._mouse_callback, module_handle, 0
        )
        if not self._mouse_hook:
            error = ctypes.get_last_error()
            self.hook_error.emit(
                f"SetWindowsHookExW(WH_MOUSE_LL) failed: ", f"{ctypes.WinError(error)}"
            )
            self._stop_detector()
            self._thread_id = 0
            return

        self._keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._keyboard_callback, module_handle, 0
        )
        if not self._keyboard_hook:
            error = ctypes.get_last_error()
            self.hook_error.emit(
                f"SetWindowsHookExW(WH_KEYBOARD_LL) failed: "
                f"{ctypes.WinError(error)}"
            )
            self._stop_detector()
            self._thread_id = 0
            return
        self.hooks_started.emit()

        # # Watchdog timer posts WM_TIMER into this thread's message queue.
        # self._watchdog_timer_id = user32.SetTimer(None, 0, WATCHDOG_INTERVAL_MS, None)
        # if not self._watchdog_timer_id:
        #     error = ctypes.get_last_error()
        #     self.hook_error.emit(f"SetTimer failed: {ctypes.WinError(error)}")

        # Native Win32 message loop, Win32 message pump
        while not self._stop_requested:
            # GetMessageW is a blocking call, waiting for result.
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == -1:
                error = ctypes.get_last_error()
                self.hook_error.emit(f"GetMessageW failed: {ctypes.WinError(error)}")
                break
            if result == 0:
                # WM_QUIT
                break

            # # ----------------------------------------
            # # Watchdog
            # # ----------------------------------------
            # if msg.message == WM_TIMER and msg.wParam == self._watchdog_timer_id:
            #     self._watchdog_check()
            #     continue

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        # --------------------------------------------
        # Cleanup
        # --------------------------------------------
        self._stop_detector()
        self._thread_id = 0
        self.hooks_stopped.emit()
        user32.KillTimer(None, WATCHDOG_TIMER_ID)

    def _send_mask_key(self) -> bool:
        """
        Send MASK_KEY as maskey
        """
        inputs = (INPUT * 2)()
        # Ctrl DOWN
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].ki = KEYBDINPUT(
            wVk=MASK_KEY, wScan=0, dwFlags=0, time=0, dwExtraInfo=0
        )
        # Ctrl UP
        inputs[1].type = INPUT_KEYBOARD
        inputs[1].ki = KEYBDINPUT(
            wVk=MASK_KEY, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0
        )
        ctypes.set_last_error(0)
        sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
        if sent != 2:
            error = ctypes.get_last_error()
            self.hook_error.emit(f"SendInput mask key failed: {ctypes.WinError(error)}")
            return False
        return True

    def _send_click(self):
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
            self.hook_error.emit(f"SendInput mask key failed: {ctypes.WinError(error)}")
            return False
        return True

    def send_mouse_up(self):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dwFlags = MOUSEEVENTF_LEFTUP
        inp.mi.dwExtraInfo = SNIPIN_MOUSE_EVENT
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _stop_detector(self):
        if self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None

        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
            self._keyboard_hook = None

    def suspend(self):
        """
        Can call by Main thread
        """
        self._suspended = True

    def resume(self):
        """
        Can call by Main thread
        """
        self._suspended = False

    def stop(self):
        """
        MAIN THREAD.
        Can be called safely from the Qt main thread.
        """
        self._stop_requested = True
        thread_id = self._thread_id
        if not thread_id:
            return
        if not user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0):
            error = ctypes.get_last_error()
            self.hook_error.emit(
                f"PostThreadMessageW(WM_QUIT) failed: " f"{ctypes.WinError(error)}"
            )

    # def _watchdog_check(self):
    #     return
    #     now = time.perf_counter_ns()
    #     for vk_code, pressed_at in list(self._keys_down.items()):
    #         held_time = now - pressed_at
    #         if held_time < self.KEY_STUCK_TIMEOUT_NS:
    #             continue
    #         # Our hook thinks DOWN.
    #         # Check actual Windows state.
    #         physically_down = bool(user32.GetAsyncKeyState(vk_code) & 0x8000)
    #         if physically_down:
    #             # User really is still holding the key.
    #             continue
    #         # Hook state and Windows state disagree.
    #         # Most likely KEYUP was missed.
    #         print(
    #             f"[Watchdog] Recover stuck key: "
    #             f"VK={vk_code}, held={held_time//self._NS_PER_SECOND:.1f}s"
    #         )
    #         self._keys_down.pop(vk_code, None)

    #         # if self._gesture_used_win:
    #         #     self._gesture_used_win = False
    #         #     self._send_mask_key()

    #         # self._send_mask_key()  # Send maskey if detect key stuck.
    #         # self.key_stuck.emit(vk_code, held_time)

    def _mouse_proc(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code < HC_ACTION or self._suspended:
            return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

        data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents

        if data.flags & LLMHF_INJECTED:
            return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

        x = int(data.pt.x)
        y = int(data.pt.y)

        current_time_ns = time.perf_counter_ns()

        # ========================================================
        # DOWN
        # ========================================================
        if w_param in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
            if self._win_down:
                if not self._win_physical_down or self._mouse_down:
                    self._win_state_recovery()
                    # Don't overwrite an existing gesture.
                    # if self._mouse_down:
                    return user32.CallNextHookEx(
                        self._mouse_hook, n_code, w_param, l_param
                    )

                self._mouse_down = True
                self._dragging = False
                self._drag_button = w_param

                self._drag_start_x = x
                self._drag_start_y = y

                self._gesture_used_win = True
                self._mask_win_release = True
                self.last_time_ns = current_time_ns
                return 1

        # ========================================================
        # MOVE
        # ========================================================

        elif w_param == WM_MOUSEMOVE:
            if self._mouse_down and self._gesture_used_win:
                if not self._dragging:
                    dx = abs(x - self._drag_start_x)
                    dy = abs(y - self._drag_start_y)
                    if dx >= self._drag_threshold or dy >= self._drag_threshold:
                        self._dragging = True
                        self.drag_started.emit(self._drag_start_x, self._drag_start_y)
                if self._dragging:
                    if current_time_ns - self.last_time_ns >= self.interval_ns:
                        self.drag_moved.emit(
                            self._drag_start_x, self._drag_start_y, x, y
                        )
                        self.last_time_ns = current_time_ns

                # Throttle signals, NOT suppression.
                # return 1

        # ========================================================
        # UP
        # ========================================================

        elif w_param in (WM_LBUTTONUP, WM_RBUTTONUP):
            if self._mouse_down:
                expected_up = (
                    WM_LBUTTONUP
                    if self._drag_button == WM_LBUTTONDOWN
                    else WM_RBUTTONUP
                )
                if w_param != expected_up:
                    return user32.CallNextHookEx(
                        self._mouse_hook, n_code, w_param, l_param
                    )
                was_dragging = self._dragging
                self._mouse_down = False
                self._dragging = False
                self._drag_button = None
                self._gesture_used_win = False
                if was_dragging:
                    if w_param == WM_LBUTTONUP:
                        self.drag_finished.emit(
                            self._drag_start_x, self._drag_start_y, x, y
                        )
                    else:
                        self.right_drag_finished.emit(
                            self._drag_start_x, self._drag_start_y, x, y
                        )
                # DOWN was suppressed, so always suppress matching UP.
                return 1
        return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    def __mouse_proc(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code < HC_ACTION or self._suspended:
            return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)
        data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if data.flags & LLMHF_INJECTED:
            return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)
        x = int(data.pt.x)
        y = int(data.pt.y)
        current_time_ns = time.perf_counter_ns()
        # ========================================================
        # PHYSICAL MOUSE STATE
        # ========================================================

        if w_param == WM_LBUTTONDOWN:
            self._left_down = True

        elif w_param == WM_LBUTTONUP:
            self._left_down = False

        elif w_param == WM_RBUTTONDOWN:
            self._right_down = True

        elif w_param == WM_RBUTTONUP:
            self._right_down = False

        # ========================================================
        # DOWN
        # ========================================================
        if w_param in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
            # ----------------------------------------------------
            # Left + Right mouse gesture
            # ----------------------------------------------------
            if not self._win_down and self._left_down and self._right_down:
                # if not self._win_down and not self._mouse_down and left_down and right_down:
                print("left + right triggered, swallowed", w_param)
                # _send_mouse_up(VK_RBUTTON)
                # if self._left_down:
                #     _send_mouse_up(VK_LBUTTON)

                self._mouse_down = True
                self._dragging = False
                self._gesture_type = GESTURE_LEFT_RIGHT
                # Remember which button completed the combination.
                self._drag_button = w_param
                self._drag_start_x = x
                self._drag_start_y = y
                self._gesture_used_win = False
                self.last_time_ns = current_time_ns
                # Suppress SECOND button DOWN.
                return 1
            # ----------------------------------------------------
            # Win + Left / Win + Right
            # ----------------------------------------------------
            if self._win_down:
                print("win +Mouse triggered, swallowed", w_param)
                if not self._win_physical_down or self._mouse_down:
                    self._win_state_recovery()
                    return user32.CallNextHookEx(
                        self._mouse_hook, n_code, w_param, l_param
                    )
                self._mouse_down = True
                self._dragging = False
                self._drag_button = w_param
                self._gesture_type = (
                    GESTURE_WIN_LEFT if w_param == WM_LBUTTONDOWN else GESTURE_WIN_RIGHT
                )
                self._drag_start_x = x
                self._drag_start_y = y
                self._gesture_used_win = True
                self._mask_win_release = True
                self.last_time_ns = current_time_ns
                return 1
        # ========================================================
        # MOVE
        # ========================================================
        elif w_param == WM_MOUSEMOVE:
            if self._mouse_down:
                if not self._dragging:
                    dx = abs(x - self._drag_start_x)
                    dy = abs(y - self._drag_start_y)

                    if dx >= self._drag_threshold or dy >= self._drag_threshold:
                        self._dragging = True

                        self.drag_started.emit(
                            self._drag_start_x,
                            self._drag_start_y,
                        )
                if self._dragging:
                    if current_time_ns - self.last_time_ns >= self.interval_ns:
                        self.drag_moved.emit(
                            self._drag_start_x, self._drag_start_y, x, y
                        )
                        self.last_time_ns = current_time_ns
        # ========================================================
        # UP
        # ========================================================

        elif w_param in (WM_LBUTTONUP, WM_RBUTTONUP):

            if self._mouse_down:
                # ------------------------------------------------
                # Win + Left / Win + Right
                # ------------------------------------------------

                if self._gesture_type in (GESTURE_WIN_LEFT, GESTURE_WIN_RIGHT):

                    expected_up = (
                        WM_LBUTTONUP
                        if self._drag_button == WM_LBUTTONDOWN
                        else WM_RBUTTONUP
                    )
                    if w_param != expected_up:
                        return user32.CallNextHookEx(
                            self._mouse_hook, n_code, w_param, l_param
                        )

                    was_dragging = self._dragging
                    gesture_type = self._gesture_type

                    self._mouse_down = False
                    self._dragging = False
                    self._drag_button = None
                    self._gesture_type = None
                    self._gesture_used_win = False

                    if was_dragging:
                        self.drag_finished.emit(
                            self._drag_start_x, self._drag_start_y, x, y
                        )

                    # DOWN was suppressed, therefore suppress UP.
                    return 1
                # ------------------------------------------------
                # Left + Right
                # ------------------------------------------------
                elif self._gesture_type == GESTURE_LEFT_RIGHT:
                    # Only handle UP belonging to the second button
                    # whose DOWN we suppressed.
                    # expected_up = (
                    #     WM_LBUTTONUP
                    #     if self._drag_button == WM_LBUTTONDOWN
                    #     else WM_RBUTTONUP
                    # )

                    # if w_param == expected_up:
                    # Update physical state.
                    # if w_param == WM_LBUTTONUP:
                    #     self._left_down = False

                    # elif w_param == WM_RBUTTONUP:
                    #     self._right_down = False

                    # --------------------------------------------
                    # Keep gesture alive until BOTH are released
                    # --------------------------------------------

                    if not self._left_down and not self._right_down:
                        # if self._dragging:
                        was_dragging = self._dragging
                        self._mouse_down = False
                        self._dragging = False
                        self._drag_button = None
                        self._gesture_type = None
                        if was_dragging:
                            self.drag_finished.emit(
                                self._drag_start_x, self._drag_start_y, x, y
                            )

                    # IMPORTANT:
                    # Swallow BOTH left and right UP while
                    # LEFT_RIGHT gesture is active.

                    # print("swallowed", w_param)
                    # return 1
        # left_down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        # right_down = bool(user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000)
        # print(f"left down: {left_down}; right down: {right_down}")
        return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    def _keyboard_proc(self, n_code, w_param, l_param):
        if n_code < HC_ACTION or self._suspended:
            return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)
        data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents

        # Ignore SendInput-generated events.
        if data.flags & LLKHF_INJECTED:
            return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)
        vk_code = int(data.vkCode)
        # ========================================================
        # WIN key
        # ========================================================
        if vk_code in (VK_LWIN, VK_RWIN):
            if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                self._keys_down.setdefault(
                    vk_code,
                    time.perf_counter_ns(),
                )

            elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                self._keys_down.pop(vk_code, None)

                # Only after LAST tracked Win key is gone.
                if not self._win_down and self._mask_win_release:
                    self._send_mask_key()
                    self._mask_win_release = False
        return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)
        # # ========================================================
        # # OTHER key
        # # ========================================================
        # elif w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
        #     # Another keyboard key was pressed while Win was
        #     # armed. Do not allow the still-held Win key to
        #     # subsequently initiate Win+mouse.
        #     if self._win_down:
        #         self._keys_down.pop(VK_LWIN, None)
        #         self._keys_down.pop(VK_RWIN, None)
        #         self._gesture_used_win = False
        # return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

    def _win_state_recovery(self):
        print("inconsistent winkey detect, recovering...")
        self._keys_down.pop(VK_LWIN, None)
        self._keys_down.pop(VK_RWIN, None)
        self._gesture_used_win = False
        self._mouse_down = False
        self._left_down = False
        self._right_down = False
        self._dragging = False
        self._drag_button = None

    # def _keyboard_proc(self, n_code, w_param, l_param):
    #     if n_code < HC_ACTION or self._suspended:
    #         return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

    #     data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
    #     if data.flags & LLKHF_INJECTED:
    #         return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

    #     vk_code = int(data.vkCode)
    #     if vk_code in (VK_LWIN, VK_RWIN):
    #         if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
    #             self._keys_down.setdefault(vk_code, time.perf_counter_ns())

    #         elif w_param in (WM_KEYUP, WM_SYSKEYUP):
    #             self._keys_down.pop(vk_code, None)

    #             # Only mask after the LAST Win key is released.
    #             if not self._win_down and self._mask_win_release:
    #                 self._send_mask_key()
    #                 self._mask_win_release = False
    #         else:  # when other key pressed, release _win_down state.
    #             if self._win_down and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
    #                 # self._win_down = False
    #                 self._keys_down.pop(VK_LWIN, None)
    #                 self._keys_down.pop(VK_RWIN, None)
    #                 # print("pop", vk_code)
    #                 self._gesture_used_win = False

    #     return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

    # def __mouse_proc(self, n_code, w_param, l_param):
    #     """
    #     Runs on the hook thread.
    #     Keep this callback very short:
    #     1. Read event
    #     2. Update simple state
    #     3. Emit signal
    #     4. Return
    #     """
    #     if n_code < HC_ACTION or self._suspended:
    #         return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)
    #     current_time_ns = time.perf_counter_ns()
    #     data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
    #     # Ignore our own injected input if needed.
    #     if data.flags & LLMHF_INJECTED:
    #         return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)
    #     x = int(data.pt.x)
    #     y = int(data.pt.y)
    #     self._last_x = x
    #     self._last_y = y
    #     if w_param in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
    #         if self._win_down:
    #             self._mouse_down = True
    #             self._drag_start_x = x
    #             self._drag_start_y = y
    #             self._gesture_used_win = True
    #             return 1  # Suppress mouse down.

    #     elif w_param == WM_MOUSEMOVE:
    #         # Throttle 60hz only in mouse move
    #         if current_time_ns - self.last_time_ns < self.interval_ns:
    #             return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    #         if self._mouse_down and self._win_down:
    #             dx = abs(x - self._drag_start_x)
    #             dy = abs(y - self._drag_start_y)
    #             if not self._dragging:
    #                 if dx >= self._drag_threshold or dy >= self._drag_threshold:
    #                     self._dragging = True
    #                     self.drag_started.emit(self._drag_start_x, self._drag_start_y)
    #             if self._dragging:
    #                 self.drag_moved.emit(self._drag_start_x, self._drag_start_y, x, y)
    #                 self.last_time_ns = current_time_ns
    #                 return 1  # Suppress mouse move.

    #     elif w_param in (WM_LBUTTONUP, WM_RBUTTONUP):
    #         self._mouse_down = False
    #         # self.mouse_released.emit(x, y)
    #         if self._dragging:
    #             self._dragging = False
    #             if w_param == WM_LBUTTONUP:
    #                 self.drag_finished.emit(
    #                     self._drag_start_x, self._drag_start_y, x, y
    #                 )
    #             else:
    #                 self.right_drag_finished.emit(
    #                     self._drag_start_x, self._drag_start_y, x, y
    #                 )
    #             return 1  # Suppress mouse up.
    #             self._send_mask_key()

    #     self.last_time_ns = current_time_ns
    #     return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    # def _mouse_proc(self, n_code: int, w_param: int, l_param: int) -> int:
    #     """
    #     Runs on the hook thread.
    #     """

    #     if n_code < HC_ACTION or self._suspended:
    #         return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)
    #     current_time_ns = time.perf_counter_ns()
    #     data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
    #     # Ignore injected input.
    #     if data.flags & LLMHF_INJECTED:
    #         return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)
    #     x = int(data.pt.x)
    #     y = int(data.pt.y)
    #     # print("winmouse detector hook", x, y)
    #     # ========================================================
    #     # Mouse DOWN
    #     # ========================================================

    #     if w_param in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
    #         if self._win_down:
    #             self._mouse_down = True
    #             self._dragging = False
    #             # Remember exactly which button started this gesture.
    #             self._drag_button = w_param
    #             self._drag_start_x = x
    #             self._drag_start_y = y
    #             self._gesture_used_win = True
    #             # Start timing MOVE emissions from here.
    #             self.last_time_ns = current_time_ns
    #             # Suppress mouse DOWN.
    #             return 1
    #     # ========================================================
    #     # Mouse MOVE
    #     # ========================================================
    #     elif w_param == WM_MOUSEMOVE:
    #         # if self._mouse_down and self._win_down:
    #         if self._mouse_down and self._gesture_used_win:
    #             # ------------------------------------------------
    #             # Candidate -> dragging
    #             # ------------------------------------------------
    #             if not self._dragging:
    #                 dx = abs(x - self._drag_start_x)
    #                 dy = abs(y - self._drag_start_y)
    #                 if dx >= self._drag_threshold or dy >= self._drag_threshold:
    #                     self._dragging = True
    #                     self.drag_started.emit(self._drag_start_x, self._drag_start_y)
    #             # ------------------------------------------------
    #             # Actual drag
    #             # ------------------------------------------------
    #             if self._dragging:
    #                 # Throttle SIGNAL emission only.
    #                 if current_time_ns - self.last_time_ns >= self.interval_ns:
    #                     self.drag_moved.emit(
    #                         self._drag_start_x, self._drag_start_y, x, y
    #                     )
    #                     self.last_time_ns = current_time_ns

    #             # suppress all MOVE events belonging to gesture,
    #             # including moves that were throttled.
    #             return 1

    #     # ========================================================
    #     # Mouse UP
    #     # ========================================================
    #     elif w_param in (WM_LBUTTONUP, WM_RBUTTONUP):
    #         if self._mouse_down:
    #             expected_up = (
    #                 WM_LBUTTONUP
    #                 if self._drag_button == WM_LBUTTONDOWN
    #                 else WM_RBUTTONUP
    #             )
    #             # Ignore release of unrelated button.
    #             if w_param != expected_up:
    #                 return user32.CallNextHookEx(
    #                     self._mouse_hook, n_code, w_param, l_param
    #                 )
    #             was_dragging = self._dragging

    #             self._mouse_down = False
    #             self._dragging = False
    #             self._drag_button = None
    #             self._gesture_used_win = False

    #             if was_dragging:
    #                 if w_param == WM_LBUTTONUP:
    #                     self.drag_finished.emit(
    #                         self._drag_start_x, self._drag_start_y, x, y
    #                     )
    #                 else:
    #                     self.right_drag_finished.emit(
    #                         self._drag_start_x, self._drag_start_y, x, y
    #                     )
    #                 self._send_mask_key()

    #             # DOWN was suppressed, therefore its matching UP
    #             # should also be suppressed, even if drag threshold
    #             # wasn't reached.
    #             return 1

    #     # ========================================================
    #     # Normal mouse event
    #     # ========================================================
    #     return user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    # def _keyboard_proc(self, n_code, w_param, l_param):
    #     """
    #     Runs on the same dedicated hook thread.
    #     """
    #     if n_code < HC_ACTION or self._suspended:
    #         return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)
    #     data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents

    #     # Prevent reacting to SendInput-generated keyboard events.
    #     if data.flags & LLKHF_INJECTED:
    #         return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)
    #     vk_code = int(data.vkCode)
    #     if vk_code in (VK_LWIN, VK_RWIN):
    #         if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
    #             if not self._win_down:
    #                 self._win_down = True
    #             self._keys_down.setdefault(vk_code, time.perf_counter_ns())
    #         elif w_param in (WM_KEYUP, WM_SYSKEYUP):
    #             if self._win_down:
    #                 self._send_mask_key()
    #                 self._win_down = False
    #             self._keys_down.pop(vk_code, None)
    #             # if self._gesture_used_win:
    #             # self._gesture_used_win = False
    #             # self._send_mask_key()
    #     # if other key press after windown, then reset win-down status.
    #     else:
    #         if self._win_down:
    #             # print("Release because other keys were pressed", self._keys_down.keys())
    #             self._win_down = False
    #     return user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)
