import os
import logging
import sys
import subprocess
from PyQt6.QtWidgets import QApplication


def open_system_file(filename):
    """
    open file using system default app.
    """
    if not os.path.exists(filename):
        return
    try:
        os.startfile(filename)
    except Exception as e:
        logging.error(f"Open file failed: {filename}, Error: {e}")


def is_compiled() -> bool:
    """Return True when running as a compiled executable."""
    return "__compiled__" in globals()


def reload_script() -> None:
    """
    Gracefully restart the application.
    Supports:
        - Normal Python execution
        - Nuitka standalone
        - Nuitka onefile
    """
    if is_compiled():
        # Nuitka compiled application.
        #
        # Prefer argv[0] because it represents the executable
        # that the user actually launched.
        executable = os.path.abspath(sys.argv[0])
        args = [
            executable,
            *sys.argv[1:],
        ]
    else:
        # Normal Python execution.
        script_path = os.path.abspath(sys.argv[0])
        args = [
            sys.executable,
            script_path,
            *sys.argv[1:],
        ]
    # print(f"========= Re-Opening app: " f"{os.path.basename(args[0])} =========")
    subprocess.Popen(args)
    # Gracefully exit Qt so aboutToQuit cleanup runs.
    app = QApplication.instance()
    if app is not None:
        app.quit()
