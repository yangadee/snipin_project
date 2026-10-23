import ctypes
from ctypes import wintypes
import time
import sys
from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget
from utils.key_mapper import KeyMapper
import logging
from core.models import HotkeySpec


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class Win32HotkeyManager(QAbstractNativeEventFilter):
    """
    Hotkey Wrapper with automatic Fallback to the 'keyboard' package.
    Keeps the exact same API format for seamless integration into your controller.
    """

    def __init__(self):
        # Multiple inheritance initialization
        QAbstractNativeEventFilter.__init__(self)
        app = QApplication.instance()
        # Detect platform and attempt Win32 event filter registration
        if sys.platform == "win32":
            if not app:
                app = QCoreApplication.instance()
            if app:
                app.installNativeEventFilter(self)

        self.current_id = 100  # Auto-incrementing ID for Win32
        self.mapper = KeyMapper()

        self._hotkeys: dict[str, HotkeySpec] = {}
        self._callbacks: dict[str, callable] = {}
        self._registration_ids: dict[int, str] = {}  # reg_id to hotkey_id mapping
        self._hotkeys_suspended = False

        # # ==============================================
        # # Session monitor for lock / unlock action.
        # # ==============================================
        # self._dummy = QWidget()
        # self.session_hwnd = int(self._dummy.winId())
        # wts = ctypes.WinDLL("wtsapi32", use_last_error=True)

        # wts.WTSRegisterSessionNotification.argtypes = (wintypes.HWND, wintypes.DWORD)
        # wts.WTSRegisterSessionNotification.restype = wintypes.BOOL
        # wts.WTSUnRegisterSessionNotification.argtypes = (wintypes.HWND,)
        # wts.WTSUnRegisterSessionNotification.restype = wintypes.BOOL
        # registered = bool(wts.WTSRegisterSessionNotification(self.session_hwnd, 0))
        # if not registered:
        #     raise ctypes.WinError(ctypes.get_last_error())
        # # Use the WTS function setup from your successful test.
        # if not wts.WTSRegisterSessionNotification(self.session_hwnd, 0):
        #     raise ctypes.WinError(ctypes.get_last_error())

    @property
    def hotkeys(self) -> dict[str, HotkeySpec]:
        return self._hotkeys

    @property
    def hotkeys_suspended(self) -> bool:
        return self._hotkeys_suspended

    def suspend_hotkeys(self) -> None:
        self._hotkeys_suspended = True

    def resume_hotkeys(self) -> None:
        self._hotkeys_suspended = False

    def set_hotkeys_suspended(self, suspended: bool) -> None:
        self._hotkeys_suspended = suspended

    def parse_win32_hotkey(self, hotkey_str: str):
        """
        Parses modifier combinations specifically tailored for Win32 Kernel constraints.
        For native use
        """
        tokens = hotkey_str.lower().replace(" ", "").split("+")
        mods, vk = 0, None
        for token in tokens:
            if self.mapper.is_mod(token):
                mods |= self.mapper.mod_to_vk(token)
            else:
                vk = self.mapper.str_to_vk(token)
                vk = None if vk == 0 else vk
        return mods, vk

    # ----------------------------------------------
    # Hotkeys Watchdog
    # ----------------------------------------------

    def nativeEventFilter(self, event_type, message):
        """Standard Win32 thread pump router."""
        if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = MSG.from_address(int(message))
            if msg.message == 0x0312:  # WM_HOTKEY
                # Hotkey suspension check
                if self._hotkeys_suspended:
                    return True, 0

                registration_id = msg.wParam
                hotkey_id = self._registration_ids.get(registration_id)
                if hotkey_id:
                    callback = self._callbacks.get(hotkey_id)
                    if callback:
                        callback()
                    return True, 0
            # # ==============================================
            # # Session monitor for lock / unlock action.
            # # ==============================================
            # elif (
            #     msg.message == 0x02B1  # WM_WTSSESSION_CHANGE
            #     and int(msg.hwnd or 0) == self.session_hwnd
            # ):
            #     if msg.wParam == 0x7:  # WTS_SESSION_LOCK
            #         # self.on_session_lock()
            #         print("session lock")
            #     elif msg.wParam == 0x8:  # WTS_SESSION_UNLOCK
            #         # self.on_session_unlock()
            #         print("session unlock")

        # Existing hotkey handling continues unchanged.
        return False, 0

    # ----------------------------------------------
    # Register Main
    # ----------------------------------------------
    def register_hotkey(
        self,
        hotkey_id: str,
        hotkey_seq: str,
        owner: str,
        callback: callable,
        retries: int = 2,
        retry_delay: float = 1.0,
    ) -> HotkeySpec | None:
        """
        Add hotkey using Win32 method for robustness.
        """
        if hotkey_id in self._hotkeys:
            logging.debug("Hotkey already exists: %s", hotkey_id)
            return None
        registration_id = self.current_id
        # ========================================================
        # ENGINE A: Native Win32
        # ========================================================
        mods, vk = self.parse_win32_hotkey(hotkey_seq)
        if vk is None:
            logging.debug(
                "[Parsing Error] Cannot parse hotkey string format: %s", hotkey_seq
            )
            return None

        # ========================================================
        # RETRY METHOD
        # ========================================================
        for attempt in range(1, retries + 1):
            ctypes.windll.kernel32.SetLastError(0)
            success = ctypes.windll.user32.RegisterHotKey(
                None, registration_id, mods, vk
            )

            if success:
                spec = HotkeySpec(
                    hotkey_id=hotkey_id,
                    hotkey_seq=hotkey_seq.lower(),
                    registration_id=registration_id,
                    owner=owner,
                )
                # print(f"{spec.hotkey_id}| {spec.hotkey_seq}|{spec.registration_id}|{spec.owner}")
                self._hotkeys[spec.hotkey_id] = spec
                self._callbacks[spec.hotkey_id] = callback
                self._registration_ids[registration_id] = hotkey_id

                self.current_id += 1
                logging.debug(
                    "[Register] Successfully bound '%s' "
                    "(ID: %s, VK: %s, attempt: %s/%s)",
                    hotkey_seq,
                    hotkey_id,
                    hex(vk),
                    attempt,
                    retries,
                )

                return spec

            # ====================================================
            # Native failed
            # ====================================================
            error_code = ctypes.windll.kernel32.GetLastError()
            try:
                error_message = ctypes.FormatError(error_code).strip()
            except Exception:
                error_message = "Unknown Win32 error"

            logging.debug(
                "[Error] Failed to bind '%s' " "(attempt %d/%d) | Error %d: %s",
                hotkey_seq,
                attempt,
                retries,
                error_code,
                error_message,
            )

            if attempt < retries:
                time.sleep(retry_delay)

        return None

    # ----------------------------------------------
    # UN-Register Main
    # ----------------------------------------------
    def unregister_hotkey_spec(self, spec=None) -> bool:
        if not spec:
            return False

        try:
            if not ctypes.windll.user32.UnregisterHotKey(None, spec.registration_id):
                error = ctypes.windll.kernel32.GetLastError()
                logging.debug(
                    "Failed to unregister Win32 hotkey '%s' "
                    "(ID: %s, registration_id: %s). Error: %s",
                    spec.hotkey_seq,
                    spec.hotkey_id,
                    spec.registration_id,
                    error,
                )
                return False

            self._hotkeys.pop(spec.hotkey_id, None)
            self._callbacks.pop(spec.hotkey_id, None)
            self._registration_ids.pop(spec.registration_id)

            logging.debug(
                "[Successful] Unregistered hotkey: %s [%s]",
                spec.hotkey_seq,
                spec.hotkey_id,
            )
            return True

        except Exception:
            logging.exception("Failed to unregister hotkey '%s'", spec.hotkey_seq)
            return False

    def unregister_all(self):
        """Clean teardown dispatcher supporting safe release. using win32"""

        total, succeeded = 0, 0
        for spec in list(self._hotkeys.values()):
            total += 1
            if self.unregister_hotkey_spec(spec):
                succeeded += 1
        if total:
            logging.debug(
                "[Hotkeys] %s/%s hotkey(s) are unregistered.", succeeded, total
            )
        else:
            logging.debug("[Hotkeys] No hotkey is unregistered.")

        self._hotkeys.clear()
        self._callbacks.clear()
        self._registration_ids.clear()

    def unregister_hotkey_id(self, hotkey_id: str) -> bool:
        """
        Unregister hotkey by hotkey_id (string).
        """
        spec = self._hotkeys.get(hotkey_id)
        if spec is None:
            logging.warning("Hotkey ID '%s' is not registered.", hotkey_id)
            return False

        return self.unregister_hotkey_spec(spec)

    def unregister_hotkey(self, hotkey_seq: str) -> bool:
        """
        Unregister hotkey by hotkey sequence.
        """
        hotkey_seq = hotkey_seq.lower()
        for hotkey_id, spec in list(self._hotkeys.items()):
            if spec.hotkey_seq != hotkey_seq:
                continue
            return self.unregister_hotkey_spec(spec)

        logging.info("[Hotkeys] Hotkey '%s' is not registered, ignored", hotkey_seq)
        return False

    def unregister_hotkey_owner(self, owner: str) -> bool:
        """
        Unregister all hotkeys belonging to owner.
        """

        total, succeeded = 0, 0
        for hotkey_id, spec in list(self._hotkeys.items()):
            if spec.owner != owner:
                continue
            total += 1
            if self.unregister_hotkey_spec(spec):
                succeeded += 1

        if total:
            success_all = total == succeeded
            logging.debug(
                "[Hotkeys] %d/%d hotkeys unregistered for owner '%s'.",
                succeeded,
                total,
                owner,
            )
            return success_all
        logging.info("[Hotkeys] No hotkeys registered for owner '%s', skipped.", owner)
        return False

    def unregister_hotkey_reg_id(self, registration_id: int) -> bool:
        """
        Unregister hotkey by Win32 registration ID.
        """
        for hotkey_id, spec in list(self._hotkeys.items()):
            if spec.registration_id != registration_id:
                continue

            return self.unregister_hotkey_spec(spec)

        logging.info(
            "[Hotkeys] Registration ID %s is not registered, skipped.", registration_id
        )
        return False

    # ----------------------------------------------
    # Disable/Unable Hotkeys
    # ----------------------------------------------
    def disable_hotkey_spec(self, spec: HotkeySpec) -> bool:
        """
        Temporarily disable a hotkey while keeping its spec and callback.
        """

        # spec = self._hotkeys.get(hotkey_id)
        hotkey_id = spec.hotkey_id
        if not spec:
            logging.info("[Hotkeys] Hotkey '%s' not found, skipped.", hotkey_id)
            return False

        success = ctypes.windll.user32.UnregisterHotKey(
            None,
            spec.registration_id,
        )

        if success:
            spec.enabled = False
            logging.debug("[Hotkey disabled] '%s' (%s)", spec.hotkey_seq, hotkey_id)
            return True

        error_code = ctypes.windll.kernel32.GetLastError()

        logging.warning(
            "[Hotkeys] Failed to disable '%s' | Error %d: %s",
            spec.hotkey_seq,
            error_code,
            ctypes.FormatError(error_code).strip(),
        )

        return False

    def enable_hotkey_spec(self, spec: HotkeySpec) -> bool:
        """
        Re-enable a temporarily disabled hotkey.
        """
        # spec = self._hotkeys.get(hotkey_id)
        hotkey_id = spec.hotkey_id
        if not spec:
            logging.warning("[Enable hotkey] Hotkey '%s' not found.", hotkey_id)
            return False
        if spec.enabled:
            logging.debug(
                "[Enable hotkey] Hotkey '%s' already enabled, skipped!", hotkey_id
            )
            return True

        mods, vk = self.parse_win32_hotkey(spec.hotkey_seq)

        if vk is None:
            logging.debug("[Enable hotkey error] Cannot parse '%s'.", spec.hotkey_seq)
            return False

        ctypes.windll.kernel32.SetLastError(0)
        success = ctypes.windll.user32.RegisterHotKey(
            None,
            spec.registration_id,
            mods,
            vk,
        )

        if success:
            spec.enabled = True
            logging.debug("[Hotkey enabled] '%s' (%s)", spec.hotkey_seq, hotkey_id)
            return True

        error_code = ctypes.windll.kernel32.GetLastError()
        logging.debug(
            "[Enable hotkey error] Failed to enable '%s' | Error %d: %s",
            spec.hotkey_seq,
            error_code,
            ctypes.FormatError(error_code).strip(),
        )

        return False

    def disable_hotkey_owner(self, owner: str) -> bool:
        """
        Disable all hotkeys belonging to owner.
        """
        total, succeeded = 0, 0
        for hotkey_id, spec in list(self._hotkeys.items()):
            if spec.owner != owner:
                continue
            total += 1
            if self.disable_hotkey_spec(spec):
                succeeded += 1

        if total:
            success_all = total == succeeded
            logging.debug(
                "[Diable hotkeys] %d/%d hotkeys unregistered for owner '%s'.",
                succeeded,
                total,
                owner,
            )
            return success_all
        logging.debug("[Skip] No hotkeys registered for owner '%s'.", owner)
        return False

    def enable_hotkey_spec_owner(self, owner: str) -> bool:
        """
        Re-enable a temporarily disabled hotkey.
        """
        total, succeeded = 0, 0
        for hotkey_id, spec in list(self._hotkeys.items()):
            if spec.owner != owner:
                continue
            total += 1

        hotkey_id = spec.hotkey_id
        if not spec:
            logging.debug("[Enable hotkey] Hotkey '%s' not found.", hotkey_id)
            return False

        mods, vk = self.parse_win32_hotkey(spec.hotkey_seq)

        if vk is None:
            logging.debug("[Enable hotkey error] Cannot parse '%s'.", spec.hotkey_seq)
            return False

        ctypes.windll.kernel32.SetLastError(0)
        success = ctypes.windll.user32.RegisterHotKey(
            None,
            spec.registration_id,
            mods,
            vk,
        )

        if success:
            spec.enabled = True
            logging.debug("[Hotkey enabled] '%s' (%s)", spec.hotkey_seq, hotkey_id)
            return True

        error_code = ctypes.windll.kernel32.GetLastError()
        logging.debug(
            "[Enable hotkey error] Failed to enable '%s' | Error %d: %s",
            spec.hotkey_seq,
            error_code,
            ctypes.FormatError(error_code).strip(),
        )

        return False

    def update_hotkey(
        self,
        hotkey_id: str,
        hotkey_seq: str,
    ) -> bool:
        """
        Update an existing Win32 hotkey sequence by logical hotkey ID.
        """
        spec = self._hotkeys.get(hotkey_id)

        if spec is None:
            logging.debug(
                "[Update hotkey] Hotkey ID '%s' is not registered.", hotkey_id
            )
            return False

        new_hotkey_seq = hotkey_seq.lower()

        if spec.hotkey_seq == new_hotkey_seq:
            logging.debug(
                "[Update hotkey] Hotkey '%s' already uses sequence '%s', skipped!.",
                hotkey_id,
                new_hotkey_seq,
            )
            return True

        mods, vk = self.parse_win32_hotkey(new_hotkey_seq)
        if vk is None:
            logging.debug(
                "[Update hotkey] Cannot parse hotkey string format: %s", new_hotkey_seq
            )
            return False

        old_hotkey_seq = spec.hotkey_seq
        old_mods, old_vk = self.parse_win32_hotkey(old_hotkey_seq)

        try:
            # Release the old sequence first, if it's enabled.
            if spec.enabled:
                if not ctypes.windll.user32.UnregisterHotKey(
                    None, spec.registration_id
                ):
                    error = ctypes.windll.kernel32.GetLastError()
                    logging.debug(
                        "[Update hotkey] old hotkey '%s' was enable but failed to unregister"
                        "(ID: %s, registration_id: %s). Error: %s",
                        old_hotkey_seq,
                        hotkey_id,
                        spec.registration_id,
                        error,
                    )
                    return False

            ctypes.windll.kernel32.SetLastError(0)
            # Register the new sequence using the same registration ID.
            if ctypes.windll.user32.RegisterHotKey(
                None, spec.registration_id, mods, vk
            ):
                spec.hotkey_seq = new_hotkey_seq
                logging.debug(
                    "[Update hotkey] Updated hotkey '%s': '%s' -> '%s'",
                    hotkey_id,
                    old_hotkey_seq,
                    new_hotkey_seq,
                )
                spec.enabled = True
                return True

            error = ctypes.windll.kernel32.GetLastError()
            logging.debug(
                "[Update hotkey] Failed to register new hotkey '%s' "
                "(ID: %s, registration_id: %s). Error: %s",
                new_hotkey_seq,
                hotkey_id,
                spec.registration_id,
                error,
            )
            # ---------------------------------------------------
            # If register new hotkey_sq failed then rollback
            # Restore the old Win32 registration.
            # ---------------------------------------------------
            if old_vk is not None:
                restored = ctypes.windll.user32.RegisterHotKey(
                    None,
                    spec.registration_id,
                    old_mods,
                    old_vk,
                )

                if restored:
                    logging.debug(
                        "[Update hotkey] Restored previous hotkey '%s' for ID '%s'.",
                        old_hotkey_seq,
                        hotkey_id,
                    )
                else:
                    restore_error = ctypes.windll.kernel32.GetLastError()
                    logging.critical(
                        "[Update hotkey] Failed to restore previous hotkey '%s' "
                        "for ID '%s'. Error: %s",
                        old_hotkey_seq,
                        hotkey_id,
                        restore_error,
                    )
            return False

        except Exception:
            logging.exception(
                "[Update hotkey] Failed to update hotkey '%s' to '%s'.",
                hotkey_id,
                new_hotkey_seq,
            )
            return False

    def is_hotkey_available(self, hotkey_seq: str) -> bool:
        """Return True if the hotkey can currently be registered."""
        modifiers, vk = self._parse_hotkey(hotkey_seq)
        test_id = 0x7FFE
        ctypes.set_last_error(0)
        if not ctypes.windll.user32.RegisterHotKey(None, test_id, modifiers, vk):
            error = ctypes.get_last_error()
            logging.debug(
                "Hotkey '%s' is unavailable. Win32 error: %d", hotkey_seq, error
            )
            return False
        ctypes.windll.user32.UnregisterHotKey(None, test_id)
        return True

    def is_hotkey_available(self, hotkey_seq: str) -> tuple[bool, str]:
        """
        Test whether a global hotkey is available.
        Return:
            - is available
            - reason if not available.
        """
        modifiers, vk = self.parse_win32_hotkey(hotkey_seq)
        test_id = 0x7FFF
        ctypes.set_last_error(0)
        if not ctypes.windll.user32.RegisterHotKey(None, test_id, modifiers, vk):
            error = ctypes.get_last_error()
            reason = ctypes.FormatError(error).strip()
            return False, reason
        ctypes.windll.user32.UnregisterHotKey(None, test_id)

        return True, ""

    def shutdown(self):
        self.unregister_all()


# class NativeHotkeyManager_Fallback(QAbstractNativeEventFilter):
#     """
#     Production-grade Hotkey Wrapper with automatic Fallback to the 'keyboard' package.
#     Keeps the exact same API format for seamless integration into your controller.
#     """

#     def __init__(self, app=None):
#         # Multiple inheritance initialization
#         QAbstractNativeEventFilter.__init__(self)

#         self.hotkeys = {}  # Maps ID -> callback for Win32
#         self.current_id = 100  # Auto-incrementing ID for Win32
#         self.use_fallback = False
#         self.keyboard_module = None
#         self.mapper = KeyMapper()
#         self._hotkeys: dict[str, HotkeySpec] = {}
#         self._callbacks: dict[str, callable] = {}

#         # Detect platform and attempt Win32 event filter registration
#         if sys.platform == "win32":
#             if not app:
#                 app = QCoreApplication.instance()
#             if app:
#                 app.installNativeEventFilter(self)

#         # Mapping configuration dictionaries
#         self.MOD_MAP = {
#             "ctrl": 0x0002,
#             "control": 0x0002,
#             "shift": 0x0004,
#             "alt": 0x0001,
#             "win": 0x0008,
#         }
#         self.VK_MAP = {"space": 0x20, "enter": 0x0D, "escape": 0x1B, "tab": 0x09}

#         # Build exact Win32 virtual-key matrix
#         for i in range(12):
#             self.VK_MAP[f"f{i+1}"] = 0x70 + i
#         for i in range(26):
#             self.VK_MAP[chr(97 + i)] = 0x41 + i
#         for i in range(10):
#             self.VK_MAP[str(i)] = 0x30 + i

#     def _activate_keyboard_fallback(self, reason_str=""):
#         """Safely lazy-loads the keyboard package if native hook crashes or is unavailable."""
#         if not self.use_fallback:
#             try:
#                 import keyboard

#                 self.keyboard_module = keyboard
#                 self.use_fallback = True
#                 logging.info(
#                     "%s -> Successfully falling back to 'keyboard' module engine.",
#                     reason_str,
#                 )
#             except ImportError:
#                 logging.error(
#                     "[Critical Error] Both Win32 API and 'keyboard' package failed to initialize!"
#                 )

#     def _parse_win32_hotkey(self, hotkey_str: str):
#         """Parses modifier combinations specifically tailored for Win32 Kernel constraints."""
#         tokens = hotkey_str.lower().replace(" ", "").split("+")
#         mods, vk = 0, None
#         for token in tokens:
#             if self.mapper.is_mod(token):
#                 mods |= self.mapper.mod_to_vk(token)
#             else:
#                 vk = self.mapper.str_to_vk(token)
#                 vk = None if vk == 0 else vk
#         return mods, vk

#     def addhotkey(
#         self,
#         hotkey_str: str,
#         callback,
#         enable_fallback: bool = False,
#         native_retries: int = 2,
#         retry_delay: float = 0.1,
#     ) -> bool:
#         """
#         Unified API:
#         - Try native Win32 first.
#         - Retry native registration if it fails.
#         - If all native retries fail:
#             enable_fallback=True  -> activate keyboard fallback
#             enable_fallback=False -> return None

#         Returns hotkey_id on success, None on failure.
#         [Caution] Fallback to Keyboard module will cause high risk on stick CTRL keys.
#         """

#         hotkey_id = self.current_id

#         # ========================================================
#         # ENGINE B: Keyboard Package Fallback
#         # ========================================================
#         if self.use_fallback:
#             if not enable_fallback:
#                 logging.warning(
#                     "[Hotkey Engine B] Fallback disabled. Cannot bind '%s'.",
#                     hotkey_str,
#                 )
#                 return None

#             if not self.keyboard_module:
#                 logging.warning(
#                     "[Hotkey Engine B Error] Keyboard module unavailable. Cannot bind '%s'.",
#                     hotkey_str,
#                 )
#                 return None

#             try:
#                 keyboard_handle = self.keyboard_module.add_hotkey(
#                     hotkey_str.lower(),
#                     callback,
#                     suppress=True,
#                 )
#                 # Use our own ID for Engine B too
#                 self.hotkeys[hotkey_id] = {
#                     "callback": callback,
#                     "engine": "keyboard",
#                     "handle": keyboard_handle,
#                     "hotkey": hotkey_str.lower(),
#                 }
#                 # self.hotkeys[hotkey_id] = callback

#                 self.current_id += 1
#                 logging.info(
#                     f"[Hotkey Engine B] Successfully bound "
#                     f"'{hotkey_str}' "
#                     f"(ID: {hotkey_id}) via keyboard hook."
#                 )
#                 return hotkey_id

#             except Exception as e:
#                 logging.exception(
#                     "[Hotkey Engine B Error] Fallback binding failed for '%s'",
#                     hotkey_str,
#                 )
#                 return None

#         # ========================================================
#         # ENGINE A: Native Win32
#         # ========================================================
#         mods, vk = self._parse_win32_hotkey(hotkey_str)

#         if vk is None:
#             logging.error(
#                 "[Hotkey Error] Cannot parse hotkey string format: %s", {hotkey_str}
#             )
#             return None

#         # ========================================================
#         # RETRY NATIVE METHOD
#         # ========================================================
#         for attempt in range(1, native_retries + 1):
#             ctypes.windll.kernel32.SetLastError(0)
#             success = ctypes.windll.user32.RegisterHotKey(
#                 None,
#                 hotkey_id,
#                 mods,
#                 vk,
#             )

#             if success:
#                 # self.hotkeys[hotkey_id] = callback
#                 self.hotkeys[hotkey_id] = {
#                     "callback": callback,
#                     "engine": "win32",
#                     "handle": hotkey_id,
#                     "hotkey": hotkey_str.lower(),
#                 }
#                 self.current_id += 1

#                 logging.info(
#                     "[Hotkey Engine A] Successfully bound '%s' "
#                     "(ID: %s, VK: %s, attempt: %s/%s)",
#                     hotkey_str,
#                     hotkey_id,
#                     hex(vk),
#                     attempt,
#                     native_retries,
#                 )

#                 return hotkey_id

#             # ====================================================
#             # Native failed
#             # ====================================================
#             error_code = ctypes.windll.kernel32.GetLastError()

#             try:
#                 error_message = ctypes.FormatError(error_code).strip()
#             except Exception:
#                 error_message = "Unknown Win32 error"

#             logging.error(
#                 "[Hotkey Engine A Error] Failed to bind '%s' "
#                 "(attempt %d/%d) | Error %d: %s",
#                 hotkey_str,
#                 attempt,
#                 native_retries,
#                 error_code,
#                 error_message,
#             )

#             if attempt < native_retries:
#                 time.sleep(retry_delay)

#         # ========================================================
#         # ALL NATIVE ATTEMPTS FAILED
#         # ========================================================
#         if not enable_fallback:
#             logging.error(
#                 "[Hotkey Error] Native registration failed after %d attempts "
#                 "and keyboard fallback is disabled for '%s'.",
#                 native_retries,
#                 hotkey_str,
#             )
#             return None

#         # ========================================================
#         # ACTIVATE ENGINE B
#         # ========================================================
#         self._activate_keyboard_fallback(
#             "[Conflict Notice] Key combination occupied in Windows Kernel."
#         )

#         if not self.use_fallback:
#             logging.error(
#                 f"[Hotkey Engine B Error] Failed to activate fallback "
#                 f"for '{hotkey_str}'."
#             )
#             return None

#         # Retry once. Because use_fallback=True,
#         # this immediately enters Engine B.
#         return self.addhotkey(
#             hotkey_str,
#             callback,
#             enable_fallback=enable_fallback,
#             native_retries=native_retries,
#             retry_delay=retry_delay,
#         )

#     def _nativeEventFilter(self, event_type, message):
#         """Standard Win32 thread pump router. Ignored completely if use_fallback is active."""
#         if not self.use_fallback and bytes(event_type) in (
#             b"windows_generic_MSG",
#             b"windows_dispatcher_MSG",
#         ):
#             msg = MSG.from_address(int(message))
#             if msg.message == 0x0312:  # 0x0312 is WM_HOTKEY
#                 hotkey_id = msg.wParam
#                 if hotkey_id in list(self.hotkeys.keys()):
#                     self.hotkeys[hotkey_id].get("callback")()
#                     return True, 0
#         return False, 0

#     def nativeEventFilter(self, event_type, message):
#         """Standard Win32 thread pump router."""

#         if bytes(event_type) in (
#             b"windows_generic_MSG",
#             b"windows_dispatcher_MSG",
#         ):
#             msg = MSG.from_address(int(message))

#             if msg.message == 0x0312:  # WM_HOTKEY
#                 registration_id = msg.wParam

#                 for hotkey_id, spec in self._hotkeys.items():
#                     if spec.registration_id == registration_id:
#                         callback = self._callbacks.get(hotkey_id)
#                         if callback:
#                             callback()
#                         return True, 0
#         return False, 0

#     def unregister_all(self):
#         """Clean teardown dispatcher supporting safe release across both engines."""
#         if self.keyboard_module:  # self.use_fallback and :
#             self.keyboard_module.unhook_all()
#             logging.info(
#                 "[Hotkey Engine B] All keyboard event hooks unhooked smoothly."
#             )
#         else:
#             for hotkey_id in list(self.hotkeys.keys()):
#                 ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
#             self.hotkeys.clear()
#             logging.info(
#                 "[Hotkey Engine A] All thread-level Win32 hooks released cleanly."
#             )

#     def unregister_hotkey_id(self, hotkey_id: int) -> bool:
#         """
#         Unregister hotkey by hotkey_id for both Keyboard and win32 method.
#         """
#         info = self.hotkeys.get(hotkey_id)

#         if info is None:
#             logging.warning(
#                 "Hotkey ID %s is not registered.",
#                 hotkey_id,
#             )
#             return False
#         engine = info["engine"]
#         handle = info["handle"]
#         try:
#             if engine == "keyboard":
#                 self.keyboard_module.remove_hotkey(handle)

#             elif engine == "win32":
#                 if not ctypes.windll.user32.UnregisterHotKey(None, handle):
#                     error = ctypes.get_last_error()
#                     logging.error(
#                         "Failed to unregister Win32 hotkey %s. Error: %s",
#                         info["hotkey"],
#                         error,
#                     )
#                     return False
#             else:
#                 logging.warning("Unknown hotkey engine: %s", engine)
#                 return False

#             self.hotkeys.pop(hotkey_id)
#             logging.info("Unregistered hotkey: %s [%s]", info["hotkey"], engine)
#             return True

#         except Exception as error:
#             logging.exception(
#                 "Failed to unregister hotkey '%s' [%s]", info["hotkey"], engine
#             )
#             return False

#     def unregister_hotkey(self, hotkey_str: str) -> bool:
#         """
#         Unregister hotkey by hotkey_str for both Keyboard and win32 method.
#         """
#         hotkey_str = hotkey_str.lower()

#         for hotkey_id, info in list(self.hotkeys.items()):
#             if info["hotkey"] != hotkey_str:
#                 continue

#             try:
#                 if info["engine"] == "keyboard":
#                     self.keyboard_module.remove_hotkey(info["handle"])

#                 elif info["engine"] == "win32":
#                     if not ctypes.windll.user32.UnregisterHotKey(
#                         None,
#                         info["handle"],
#                     ):
#                         error = ctypes.get_last_error()
#                         logging.error(
#                             "Failed to unregister Win32 hotkey %s. Error: %s",
#                             info["hotkey"],
#                             error,
#                         )
#                         return False

#                 else:
#                     logging.warning(
#                         "Unknown hotkey engine: %s",
#                         info["engine"],
#                     )
#                     return False

#                 self.hotkeys.pop(hotkey_id)

#                 logging.info(
#                     "[Successful] Unregistered hotkey: %s [%s]",
#                     hotkey_str,
#                     info["engine"],
#                 )
#                 return True

#             except Exception as error:
#                 logging.exception("Failed to unregister '%s'", hotkey_str)
#                 return False

#         logging.warning(
#             "[Ignore unregister] Hotkey '%s' is not registered.", hotkey_str
#         )
#         return False

#     def add_hotkey(
#         self,
#         hotkey_id: str,
#         hotkey_seq: str,
#         owner: str,
#         callback,
#         retries: int = 2,
#         retry_delay: float = 1,
#     ) -> HotkeySpec | None:
#         """
#         Add hotkey using Win32 method for robustness.
#         """
#         if hotkey_id in self._hotkeys:
#             raise ValueError(f"Hotkey already exists: {hotkey_id}")

#         registration_id = self.current_id
#         # ========================================================
#         # ENGINE A: Native Win32
#         # ========================================================
#         mods, vk = self._parse_win32_hotkey(hotkey_seq)
#         if vk is None:
#             logging.error(
#                 "[Hotkey Error] Cannot parse hotkey string format: %s", hotkey_seq
#             )
#             return None

#         # ========================================================
#         # RETRY METHOD
#         # ========================================================
#         for attempt in range(1, retries + 1):
#             ctypes.windll.kernel32.SetLastError(0)
#             success = ctypes.windll.user32.RegisterHotKey(
#                 None, registration_id, mods, vk
#             )

#             if success:
#                 spec = HotkeySpec(
#                     hotkey_id=hotkey_id,
#                     hotkey_seq=hotkey_seq.lower(),
#                     registration_id=registration_id,
#                     owner=owner,
#                 )
#                 self._hotkeys[spec.hotkey_id] = spec
#                 self._callbacks[spec.hotkey_id] = callback
#                 self.current_id += 1
#                 logging.info(
#                     "[Hotkey Engine A] Successfully bound '%s' "
#                     "(ID: %s, VK: %s, attempt: %s/%s)",
#                     hotkey_seq,
#                     hotkey_id,
#                     hex(vk),
#                     attempt,
#                     retries,
#                 )

#                 return spec

#             # ====================================================
#             # Native failed
#             # ====================================================
#             error_code = ctypes.windll.kernel32.GetLastError()

#             try:
#                 error_message = ctypes.FormatError(error_code).strip()
#             except Exception:
#                 error_message = "Unknown Win32 error"

#             logging.error(
#                 "[Hotkey Engine A Error] Failed to bind '%s' "
#                 "(attempt %d/%d) | Error %d: %s",
#                 hotkey_seq,
#                 attempt,
#                 retries,
#                 error_code,
#                 error_message,
#             )

#             if attempt < retries:
#                 time.sleep(retry_delay)

#         return None


# # --- 測試與使用範例 ---
# class MyWindow(QMainWindow):
#    def __init__(self):
#        super().__init__()
#        self.setWindowTitle("Native Hotkey 測試")
#        self.resize(300, 200)
#        self.label = QLabel("按下 Shift+F 或 Ctrl+Shift+F1 試試看", self)
#        self.label.setGeometry(20, 80, 260, 30)
#        # 1. 初始化 Manager (必須在 QApplication 之後)
#        self.hotkey_manager = NativeHotkeyManager()
#        # 2. 註冊熱鍵並綁定 Callback (完全符合你要求的語法)
#        self.hotkey_manager.addhotkey("shift+f", self.on_shift_f_trigger)
#        self.hotkey_manager.addhotkey("ctrl+shift+f1", self.on_ctrl_shift_f1_trigger)
#    def on_shift_f_trigger(self):
#        print("觸發了 Shift + F !")
#        self.label.setText("偵測到：Shift + F")
#    def on_ctrl_shift_f1_trigger(self):
#        print("觸發了 Ctrl + Shift + F1 !")
#        self.label.setText("偵測到：Ctrl + Shift + F1")
#    def closeEvent(self, event):
#        # 視窗關閉時記得釋放 Windows 熱鍵資源
#        self.hotkey_manager.unregister_all()
#        event.accept()
# if __name__ == "__main__":
#    app = QApplication(sys.argv)
#    win = MyWindow()
#    win.show()
#    sys.exit(app.exec())
