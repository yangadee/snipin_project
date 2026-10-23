import os
import sys
import winreg as reg
from core.app_info import AppInfo
import logging

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
# regedit
# Computer\HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run


def enable_auto_startup() -> bool:
    # =====================================================
    # prevent accidentally registering python.exe during development
    # =====================================================
    if "__compiled__" not in globals():  # nuitka compiled flag.
        print("Auto-startup should only be enabled in the compiled application.")
        return False

    # exe_path = os.path.abspath(sys.executable) return python.exe
    # Python runtime, possibly python.exe
    exe_path = os.path.abspath(sys.argv[0])
    startup_command = f'"{exe_path}"'
    try:
        with reg.OpenKey(
            reg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            reg.KEY_QUERY_VALUE | reg.KEY_SET_VALUE,
        ) as key:
            try:
                current_value, _ = reg.QueryValueEx(key, AppInfo.NAME)

                if current_value == startup_command:
                    return True

            except FileNotFoundError:
                pass

            reg.SetValueEx(
                key,
                AppInfo.NAME,
                0,
                reg.REG_SZ,
                startup_command,
            )

        return True

    except OSError as error:
        print(f"Failed to enable auto-startup: {error}")
        logging.error("Failed to enable auto-startup")
        return False


def disable_auto_startup() -> bool:
    try:
        with reg.OpenKey(
            reg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            reg.KEY_SET_VALUE,
        ) as key:
            try:
                reg.DeleteValue(key, AppInfo.NAME)
            except FileNotFoundError:
                # Already disabled
                return True

        return True

    except OSError as error:
        print(f"Failed to disable auto-startup: {error}")
        logging.error("Failed to disable auto-startup")
        return False


def set_run_on_startup(enable: bool = False):
    if enable:
        return enable_auto_startup()
    return disable_auto_startup()
