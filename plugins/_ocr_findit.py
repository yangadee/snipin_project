# nuitka-project: --module
# nuitka-project: --output-dir=.\plugins
## nuitka-project: --no-pyi-file
# nuitka-project: --remove-output
# nuitka-project: --jobs=32

# nuitka-project: --include-module=plugins.shared

## nuitka-project: --include-module=ui.custom_popup
## nuitka-project: --include-module=ui.cursor_follower


## nuitka-project: --include-module=requests
## nuitka-project: --include-module=requests.packages
## nuitka-project: --include-module=bs4

## nuitka-project: --follow-import-to=bs4
## nuitka-project: --follow-import-to=webbrowser
## nuitka-project: --follow-import-to=urllib3,email,http,hmac,queue
## nuitka-project: --follow-import-to=requests
##  nuitka-project: --include-package=requests
##  nuitka-project: --include-package=urllib3
## nuitka-project: --follow-import-to=bs4
# usage: "python -m nuitka plugins/ocr_findit.py" from "MAIN DIR"

import logging
import time
from typing import Callable

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication
from sdk.models import PluginStatus

from plugins.shared.widgets import PopupMenu, CursorFollower
from sdk import PluginBase
from plugins.shared.findit import Findit
from plugins.shared.helpers import (
    extract_search_items,
    preprocess_ocr_text,
    send_ctrl_c,
)


class Ocr_Findit(PluginBase):
    NAME = "image -> Ocr -> Findit"
    DESCRIPTION = (
        "Scans images for SO, 12NC, error codes, procedures,...etc\n-> ASML Findit"
    )
    TYPE = "viewer_plugin"
    ICON = "search"
    VERSION = "1.2.2"
    CAPABILITIES = {"image", "hotkey"}
    DEFAULT_HOTKEY = "Alt+F"

    def initialize(self, api):
        self.api = api
        self.viewer_pos = QPoint()
        self.wait_cursor = CursorFollower()
        self.clipboard = QApplication.clipboard()

    def _get_selected_text(self) -> str:
        time.sleep(0.5)
        send_ctrl_c()
        time.sleep(0.5)
        return self.clipboard.text()

    def run(
        self,
        context=None,
        callback: Callable | None = None,
        *args,
        **kwargs,
    ):
        try:
            if callback:
                self._callback = callback
                self._callback(PluginStatus.RUNNING)

            if context is None:
                # Hotkey mode
                text = self._get_selected_text()
                self.findit_handler(text)
                self._ref_pos = QCursor.pos()
            else:
                image = context.copy_image()
                self._ref_pos = context.cursor_pos
                self.api.ocr_service.recognize_image(image, self.ocr_ready_callback)

        except Exception:
            if self._callback:
                self._callback(PluginStatus.ERROR)
            raise

    def ocr_ready_callback(self, ocr_text, error):
        if not ocr_text:
            if self._callback:
                self._callback(PluginStatus.CANCELLED)
            return
        corrected_ocr_text = preprocess_ocr_text(ocr_text)
        self.findit_handler(corrected_ocr_text)

    def findit_handler(self, text):
        target_items = extract_search_items(text)
        # print("target", target_items)
        if not target_items:
            if self._callback:
                self._callback(PluginStatus.CANCELLED)
            return
        self.search_worker = Findit(target_items)
        self.search_worker.finished.connect(lambda: logging.debug("Findit finished"))
        self.search_worker.result_readay.connect(self.handle_result)
        self.search_worker.start()
        self.wait_cursor.start()

    def handle_result(self, data_list: list):
        self.popup = PopupMenu(data_list, self._ref_pos)
        self.popup.show()
        self.wait_cursor.stop()

        if self._callback:
            self._callback(PluginStatus.FINISHED)
