# --- Nuitka compile config （Do not remove) ---
# nuitka-project: --standalone
## nuitka-project: --lto=yes
## nuitka-project: --mingw64
# nuitka-project: --output-dir=dist
# nuitka-project: --enable-plugin=pyqt6
# nuitka-project: --windows-console-mode=disable

# nuitka-project: --output-filename="Snipin"
## nuitka-project: --company-name=""
# nuitka-project: --file-description="Snipin Tool"
# nuitka-project: --product-name="Snipin Tool"
# nuitka-project: --file-version=1.3.4
# nuitka-project: --product-version=1.3.4
# nuitka-project: --copyright="AD"
# nuitka-project: --windows-icon-from-ico="resources/icons/snipin_ico.ico"

# nuitka-project:  --include-package=rapidocr
# nuitka-project:  --include-package=comtypes
## nuitka-project:  --include-package=comtypes.gen
# nuitka-project:  --include-package=sdk
# nuitka-project:  --include-package=requests,certifi
## nuitka-project:  --include-module=comtypes.stream
# nuitka-project:  --include-raw-dir=rapidocr=rapidocr
# nuitka-project:  --include-raw-dir=plugins=plugins


# nuitka-project: --follow-import-to=requests,urllib3,rapidocr,comtypes,certifi
# nuitka-project: --follow-import-to=sdk
# nuitka-project: --nofollow-import-to=unittest,doctest,pytest,comtypes.test,certifi.tests,win32.tests
# nuitka-project: --nofollow-import-to=numpy.tests,numpy.testing
# nuitka-project: --nofollow-import-to=PyQt6.Qt6.plugins.imageformats
# nuitka-project: --nofollow-import-to=setuptools,comtypes.gen
# nuitka-project: --noinclude-pytest-mode=nofollow
# nuitka-project: --noinclude-setuptools-mode=nofollow
# nuitka-project: --include-windows-runtime-dlls=no

# nuitka-project: --python-flag=no_docstrings
# nuitka-project: --python-flag=-O
# nuitka-project: --python-flag=no_site
# nuitka-project: --python-flag=no_asserts
# nuitka-project: --deployment


## nuitka-project: --show-progress
## nuitka-project: --remove-output
# nuitka-project: --report=compilation_report_1.3.4.a.xml
# nuitka-project: --jobs=32

# Prevent conflict in module "plugins" between runtime & compiled.
## nuitka-project: --nofollow-import-to=plugins
## nuitka-project: --nofollow-import-to=mock,IPython,notebook

# --- Nuitka compile config end ---

"""
How to compile:
- python -m nuitka main_snipin_1.0.0
"""

"""
┌──────────────────────────────┐
│        SnipAppController     │
│  hotkeys / tray / lifecycle  │
│                              │
│  viewers[]                   │
│  overlays[]                  │
│  closed_pin_image_queue[]    │
└──────────────┬───────────────┘
               │
               │ start area snip
               ▼
┌──────────────────────────────┐
│          SnipOverlay         │
│  fullscreen selection layer  │
│                              │
│  captures screen             │
│  selects crop rect           │
│  creates embedded editor     │
└──────────────┬───────────────┘
               │ editor_created
               ▼
┌──────────────────────────────┐
│        PinGraphicsView        │
│ embedded editor or pin window │
│                              │
│  QGraphicsScene              │
│  screenshot pixmap           │
│  drawing items               │
│  toolbar                     │
└──────────────┬───────────────┘
               │ owns
               ▼
┌──────────────────────────────┐
│        FloatingToolbar       │
│  tools + sub settings        │
│                              │
│  ColorPalette                │
│  width/font/fill controls    │
└──────────────────────────────┘
"""

# ============================================================
# MAIN
# ============================================================
import os

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
# os.environ["QT_FONT_DPI"] = "96"

import sys

# print("Executable at:", sys.executable)

from PyQt6.QtCore import QLockFile, QDir
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from utils.setup_logging import setup_logging
import logging
from resources.icon_provider import icon_provider
from core.app_info import AppInfo

# from core.app_controller import SnipAppController

LOCK_FILE_NAME = "6fcca8eff72a460cce761be6db25be53f164e8bc6f45c8d7198a692f09df7edc"
_GLOBAL_LOCK: QLockFile = None

if __name__ == "__main__":
    log_file = setup_logging()
    lock_path = os.path.join(QDir.tempPath(), LOCK_FILE_NAME)
    _GLOBAL_LOCK = QLockFile(lock_path)

    # Long-lived application lock.
    _GLOBAL_LOCK.setStaleLockTime(0)

    if not _GLOBAL_LOCK.tryLock(100):  # Wait maximum 100ms for old file handle releases
        print("SnipApp is already running. Exiting current instance.")
        logging.info("Snip Tool is already running. Exiting current instance.")
        sys.exit(0)
    try:
        app = QApplication(sys.argv)

        # app.setStyle(QStyleFactory.create("Fusion"))

        palette = app.palette()

        # Backgrounds
        palette.setColor(QPalette.ColorRole.Window, QColor("#f5f5f5"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f3f3f3"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#f0f0f0"))

        # Text
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#303030"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#303030"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#303030"))

        # Selection
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#0078d4"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

        palette.setColor(QPalette.ColorRole.Light, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Midlight, QColor("#e5e5e5"))
        palette.setColor(QPalette.ColorRole.Mid, QColor("#9a9a9a"))
        palette.setColor(QPalette.ColorRole.Dark, QColor("#707070"))
        palette.setColor(QPalette.ColorRole.Shadow, QColor("#505050"))

        app.setPalette(palette)
        # app.setStyleSheet("""
        #     QMessageBox QPushButton {
        #         color: #000000 !important;
        #         background-color: #f0f0f0 !important;
        #         border: 1px solid #707070;
        #         border-radius: 4px;
        #         padding: 5px 15px;
        #         min-width: 65px;
        #     }
        #     QMessageBox QPushButton:hover {
        #         background-color: #e5e5e5 !important;
        #     }
        # """)
        # app.setStyle("Fusion")
        app.setQuitOnLastWindowClosed(False)
        app_icon = icon_provider.icon(AppInfo.APPICON)
        app.setWindowIcon(app_icon)
        app.setApplicationName(AppInfo.NAME)
        app.setApplicationVersion(AppInfo.VERSION)
        app.setApplicationDisplayName(AppInfo.NAME)

        # Import AFTER QApplication() has initialized Qt DPI
        from core.app_controller import SnipAppController

        controller = SnipAppController(app)
        # Safe shutdown
        app.aboutToQuit.connect(controller.shutdown)
        sys.exit(app.exec())
    finally:
        if _GLOBAL_LOCK is not None:
            _GLOBAL_LOCK.unlock()
