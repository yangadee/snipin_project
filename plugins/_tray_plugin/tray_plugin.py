# nuitka-project: --module
# nuitka-project: --output-dir=.\plugins
## nuitka-project: --no-pyi-file
# nuitka-project: --remove-output
# nuitka-project: --jobs=32

# nuitka-project: --include-module=core.plugin_base
# nuitka-project: --include-module=ui.custom_popup
# nuitka-project: --include-module=ui.cursor_follower

## nuitka-project: --include-module=core.findit_worker
## nuitka-project: --include-module=requests
## nuitka-project: --include-module=requests.packages
## nuitka-project: --include-module=bs4

## nuitka-project: --follow-import-to=bs4
## nuitka-project: --follow-import-to=webbrowser
## nuitka-project: --follow-import-to=urllib3,email,http,hmac,queue
## nuitka-project: --follow-import-to=requests

##  nuitka-project: --include-package=requests
##  nuitka-project: --include-package=urllib3


# execute "python -m nuitka clipboard_findit.py" from "MAIN DIR"
"""
Usage:
    - Need to run in Main Directory due to dependence:
    python -m nuitka plugins/clipboard_findit.py  (from Main directory)
"""

import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCursor

from plugins.shared.widgets.findit_sap_ui import FinditSAPUI
from sdk import PluginBase
from plugins.shared.findit import Findit
from plugins.shared.helpers import extract_search_items
from plugins.shared.widgets import PopupMenu, CursorFollower

# ----------------------------------
# Declare for win32 copy Ctr+C
# ----------------------------------
user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002
# ----------------------------------


class TrayUI(PluginBase):
    NAME = "Findit / SAP"
    ICON = "search"
    VERSION = "1.0.0"
    DEFAULT_HOTKEY = "Ctrl+w"
    DESCRIPTION = "Find procedure/material/SO/error code... from selection text"
    CAPABILITIES = {"tray"}

    def initialize(self, api):
        self.api = api
        self.wait_cursor = CursorFollower()
        self.clipboard = QApplication.clipboard()
        self.lookup_popup = FinditSAPUI()

    def run(self):

        self.lookup_popup.show()
        self.lookup_popup.raise_()
        # self.current_pos = QCursor.pos()
        # time.sleep(0.5)
        # # Prenvent trigger keyboard right after hotkey release caused conflict.
        # self.send_ctrl_c()
        # time.sleep(0.5)

        # text = self.clipboard.text()
        # if text:
        #     self.findit_callback(text)

    def send_ctrl_c(self):
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    def findit_callback(self, text):
        if not text:
            return
        target_items = extract_search_items(text)
        if not target_items:
            return

        self.search_worker = Findit(target_items)
        self.search_worker.finished.connect(lambda: print("Findit worker finished"))
        self.search_worker.result_readay.connect(self.handle_result)
        self.search_worker.start()
        self.wait_cursor.start()

    def handle_result(self, data_list: list):
        self.wait_cursor.stop()
        self.popup = PopupMenu(data_list, self.current_pos)
        self.popup.show()

    def cleanup(self):
        self.lookup_popup.close()
        return super().cleanup()
