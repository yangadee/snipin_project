# nuitka-project: --module
# nuitka-project: --output-dir=.\plugins
## nuitka-project: --no-pyi-file
# nuitka-project: --remove-output
# nuitka-project: --jobs=32

## nuitka-project: --include-module=core.plugins_core.plugin_base

## nuitka-project: --include-module=core.plugins_core.findit_worker

# usage: "python -m nuitka plugins/ocr_findit.py" from "MAIN DIR"

from typing import Callable

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from sdk.models import PluginContext, PluginStatus
from sdk.plugin_base import PluginBase
from plugins.shared.helpers import preprocess_ocr_text


class Ocr_clipboard(PluginBase):
    NAME = "Image -> Ocr -> Clipboard"
    DESCRIPTION = "Scan image, extract text, and copy to clipboard"
    TYPE = "viewer_plugin"
    ICON = "copy"
    VERSION = "2.0.0"
    CAPABILITIES = {"image"}

    def initialize(self, api):
        self.api = api
        self.viewer_pos = QPoint()
        self.clipboard = QApplication.clipboard()
        self._view = None
        self._callback = None

    def run(
        self,
        context: PluginContext,
        *args,
        **kwargs,
    ):
        try:
            if not context:
                return
            callback = context.callback
            self._view = context.view
            if callable(callback):
                self._callback = callback
                self._callback(PluginStatus.RUNNING)
            image = context.copy_image()
            if image.isNull():
                # context.show_status("No image available")
                if self._callback:
                    self._callback(PluginStatus.CANCELLED)
                return
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
        # Copy ocr corrected text to clip board.
        self.clipboard.setText(corrected_ocr_text)
        if self._callback:
            self._callback(PluginStatus.FINISHED)
        if self._view:
            self._view.close()
