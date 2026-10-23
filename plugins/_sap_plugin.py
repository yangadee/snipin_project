# Usage:
# Embedded nuitka option might not work for package.
# python -m nuitka --mode=package --remove-output --include-package=win_mouse_gesture sap_plugin

import logging
import time
from typing import Callable

from sdk.models import PluginStatus
from plugins.shared.helpers import extract_items, preprocess_ocr_text, send_ctrl_c
from plugins.shared.sap import SAPController, SAPOptions, SAP_OPERATIONS
from sdk.plugin_base import PluginBase

from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import QApplication, QMenu


class SAPPlugin(PluginBase):
    NAME = "SAP plugin"
    DESCRIPTION = "Scan images and search in SAP LOGON"
    ICON = "sap"
    VERSION = "1.2.2"
    DEFAULT_HOTKEY = "Alt+S"
    CAPABILITIES = {"image", "hotkey"}

    def initialize(self, api):
        self.api = api
        self.sap = SAPController()
        self.sap.status.connect(self.on_sap_status)
        self.sap.error.connect(self.on_sap_error)
        # self.sap.finished.connect(self.on_sap_finished)
        self.clipboard = QApplication.clipboard()

        # material = "SERV.631.47632"
        # machine = "GG03"
        # service_order = "SO53608051"
        # service_order = "SO53608051"

    def run(
        self,
        context=None,
        callback: Callable | None = None,
        *args,
        **kwargs,
    ):
        if callback:
            self._callback = callback
            self._callback(PluginStatus.RUNNING)

        if context is None:
            # Hotkey mode
            text = self._get_selected_text()
            self.sap_handler(text)
        else:
            # Image/context mode
            self._get_context_text(context)

    def _get_selected_text(self) -> str:
        time.sleep(0.5)  # break after hotkey trigger.
        send_ctrl_c()
        time.sleep(0.5)  # Waiting for clipboard ready
        return self.clipboard.text()

    def _get_context_text(self, context) -> None:
        if not context:
            return
        image = context.copy_image()
        self.viewer_global_rect = context.cursor_pos
        self.api.ocr_service.recognize_image(image, self.ocr_ready_callback)

    def ocr_ready_callback(self, ocr_text, *_):
        if not ocr_text:
            if self._callback:
                self._callback(PluginStatus.CANCELLED)
            return
        corrected_ocr_text = preprocess_ocr_text(ocr_text)
        self.sap_handler(corrected_ocr_text)
        if self._callback:
            self._callback(PluginStatus.FINISHED)

    def sap_handler(self, text):
        if not text:
            if self._callback:
                self._callback(PluginStatus.CANCELLED)
            return
        items = extract_items(text)
        if not items:
            if self._callback:
                self._callback(PluginStatus.CANCELLED)
        options = SAPOptions(
            material=(items.material_12NC[0] if items.material_12NC else ""),
            machine=(items.machine_nr[0] if items.machine_nr else ""),
            service_order=(items.service_order[0] if items.service_order else ""),
        )
        menu = QMenu()
        sap_menu = self.build_sap_menu(menu=menu, options=options)
        if sap_menu is not None:
            menu.addMenu(sap_menu)
        menu.exec(QCursor.pos())

    def get_available_operations(self, options: SAPOptions) -> list:
        available = []
        for operation, info in SAP_OPERATIONS.items():
            if any(getattr(options, field, "") for field in info.inputs):
                available.append(operation)
        return available

    def build_sap_menu(self, menu: QMenu, options: SAPOptions):
        operations = self.get_available_operations(options)
        if not operations:
            return None
        for operation in operations:
            info = SAP_OPERATIONS[operation]
            action = menu.addAction(info.title)
            action.triggered.connect(
                lambda checked=False, op=operation, opts=options: self.sap.execute(
                    op, opts
                )
            )

    def on_sap_status(self, message):
        logging.info("[SAP] %s", message)

    def on_sap_error(self, message):
        logging.warning("[SAP ERROR] %s", message)

    # def on_sap_finished(self, transaction):
    #     print(f"SAP transaction finished: {transaction}")

    def cleanup(self):
        self.sap.stop()
        return super().cleanup()
