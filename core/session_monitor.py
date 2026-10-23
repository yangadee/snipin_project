import ctypes
from ctypes import wintypes
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0


class SessionMonitor(QWidget):
    """
    Monitor for window locked unlocked.
    """

    locked = pyqtSignal()
    unlocked = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Set state before winId() creates the native window.
        self._registered = False
        self._hwnd = 0

        # Keep your existing WTS function setup here.
        self._wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
        self._wts.WTSRegisterSessionNotification.argtypes = (
            wintypes.HWND,
            wintypes.DWORD,
        )
        self._wts.WTSRegisterSessionNotification.restype = wintypes.BOOL
        self._wts.WTSUnRegisterSessionNotification.argtypes = (wintypes.HWND,)
        self._wts.WTSUnRegisterSessionNotification.restype = wintypes.BOOL
        self._hwnd = int(self.winId())
        if not self._wts.WTSRegisterSessionNotification(self._hwnd, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        self._registered = True

    def nativeEvent(self, event_type, message):
        if not self._registered:
            return False, 0
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x02B1:  # WM_WTSSESSION_CHANGE
                if msg.wParam == 0x7:  # WTS_SESSION_LOCK
                    self.locked.emit()
                elif msg.wParam == 0x8:  # WTS_SESSION_UNLOCK
                    self.unlocked.emit()
        return False, 0  # Observe the message; let Qt process it normally.

    def stop(self):
        if self._registered:
            self._wts.WTSUnRegisterSessionNotification(self._hwnd)
            self._registered = False
