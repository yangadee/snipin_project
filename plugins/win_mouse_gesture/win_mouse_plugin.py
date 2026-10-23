# nuitka-project: --module
# nuitka-project: --output-dir=.\plugins
## nuitka-project: --no-pyi-file
# nuitka-project: --remove-output
# nuitka-project: --jobs=32

# nuitka-project: --include-module=core.plugin_base
# nuitka-project: --include-module=ui.custom_popup
# nuitka-project: --include-module=ui.cursor_follower
# nuitka-project: --include-module=plugins.core
## nuitka-project: --follow-import-to=plugins

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
# nuitka-project: --report=compilation_report.xml

# execute "python -m nuitka clipboard_findit.py" from "MAIN DIR"

# Usage:
# Embedded nuitka option might not work for package.
# python -m nuitka --mode=package --remove-output --include-package=win_mouse_gesture plugins\win_mouse_gesture

import time
import logging

# import from app.
from sdk import PluginBase

from plugins.shared.findit import Findit
from plugins.shared.helpers import extract_search_items, preprocess_ocr_text
from plugins.shared.widgets import PopupMenu, CursorFollower, FinditSAPUI

# Native
from .win_mouse_detector import WinMouseDragDetector
from .native_ruberband import NativeRubberBand

# Qt
from PyQt6.QtCore import QRect, QPoint, pyqtSlot
from PyQt6.QtGui import QCursor, QGuiApplication, QPixmap
from PyQt6.QtWidgets import QApplication


class WinGesture(PluginBase):
    NAME = "Win + Mouse Gesture"
    DESCRIPTION = (
        "Win + mouse left -> On The fly snip\nWin + mouse right -> OCR / Findit"
    )
    ICON = "cursor"
    CAPABILITIES = {"background"}

    def initialize(self, api):
        self.api = api
        self.wait_cursor = CursorFollower()
        self.popup_pos = QPoint()
        self.popup_ui = FinditSAPUI()

        # ---------------------------------------------
        # Dedicated native hook thread
        # ---------------------------------------------
        # self.overlay = SelectionPopup()
        self.detector = WinMouseDragDetector()
        self.detector.hook_error.connect(self.on_hook_error)
        # self.detector.drag_started.connect(self.start_selection)
        self.detector.drag_moved.connect(self.update_selection)
        self.detector.drag_finished.connect(self.on_drag_finished)
        self.detector.right_drag_finished.connect(self.on_right_drag_finished)
        self.detector.start()
        # self.detector.suspend()

        # Warm up.
        self.clipboard = QApplication.clipboard()
        self.band = NativeRubberBand()
        self._min_selection = 20  # px

    def run(self, *arg, **kwargs):
        """
        instantiate abstract class cleanup()
        """
        return

    def on_hook_error(self, message):
        logging.error("Error during Win Mouse detect: %s", message)

    # def start_selection(self, x0: int, y0: int):
    # global_rect = QRect(QPoint(x0, y0), QPoint(x0, y0)).normalized()
    # self.band._update(global_rect)

    def update_selection(self, x0: int, y0: int, x1: int, y1: int):
        global_rect = QRect(QPoint(x0, y0), QPoint(x1, y1)).normalized()
        self.band._update(global_rect)

    def on_drag_finished(self, x0, y0, x1, y1) -> None:
        """
        mouse drag finished by mouse hook.
        input from topleft and bottom right points
        """
        if self.band:
            self.band.hide()
        rect = QRect(QPoint(x0, y0), QPoint(x1, y1)).normalized()
        if rect.width() < self._min_selection or rect.height() < self._min_selection:
            return
        pixmap = self.capture_rect(rect=rect)
        self.api.create_pin_from_pixmap(pixmap, rect.topLeft())

    def on_right_drag_finished(self, x0, y0, x1, y1) -> None:
        """
        right mouse drag finished by mouse hook.
        input from topleft and bottom right points
        """
        if self.band:
            self.band.hide()
        rect = QRect(QPoint(x0, y0), QPoint(x1, y1)).normalized()
        if rect.width() < 5 or rect.height() < 5:
            return
        pixmap = self.capture_rect(rect=rect)
        self.popup_pos = rect.topLeft()
        self.api.ocr_service.recognize_pixmap(pixmap, self.ocr_ready_callback)

    def capture_rect(self, rect: QRect) -> QPixmap:
        """
        Input Global rect()
        Global rect() - Global screen_rect() ➔ Local ➔ Capture local rect
        """
        screen = QApplication.screenAt(rect.center())
        if screen is None:
            return QPixmap()
        screen_rect = screen.geometry()
        return screen.grabWindow(
            0,
            rect.x() - screen_rect.x(),
            rect.y() - screen_rect.y(),
            rect.width(),
            rect.height(),
        )

    def ocr_ready_callback(self, ocr_text, *_):
        if not ocr_text:
            return
        corrected_ocr_text = preprocess_ocr_text(ocr_text)
        self.show_popup(corrected_ocr_text, self.popup_pos)

    def _ocr_ready_callback(self, ocr_text, error):
        if not ocr_text:
            return
        corrected_ocr_text = preprocess_ocr_text(ocr_text)

        # Optional: Copy ocr corrected text to clip board.
        self.clipboard.setText(corrected_ocr_text)

        target_items = extract_search_items(corrected_ocr_text)
        if not target_items:
            return
        # t0 = time.perf_counter_ns()

        self.search_worker = Findit(target_items)
        self.search_worker.finished.connect(self.wait_cursor.stop)
        self.search_worker.result_readay.connect(self.handle_result)
        self.search_worker.start()
        self.wait_cursor.start()

        # elapsed = time.perf_counter_ns() - t0
        # print(f"Setup thread used time: {elapsed//1_000_000} ms")

    def handle_result(self, data_list: list):
        self.wait_cursor.stop()
        self.popup = PopupMenu(data_list, self.popup_pos)
        self.popup.show()

    # def cancel_selection(self):
    #     if self.band:
    #         self.band.hide()

    def show_popup(self, text="", global_pos=None):
        if not self.popup_ui:
            return
        if text:
            self.popup_ui.set_query(text)
        if global_pos is None:
            cursor_pos = QCursor.pos()
            screen = (
                QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            )
            rect = screen.availableGeometry()
            # Center popup on this screen
            x = rect.center().x() - self.popup_ui.width() // 2
            y = rect.center().y() - self.popup_ui.height() // 2
        else:
            screen = (
                QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
            )
            rect = screen.availableGeometry()
            # Start at requested global position
            x = global_pos.x()
            y = global_pos.y()
            # Keep entire popup inside that screen
            x = min(max(x, rect.left()), rect.right() - self.popup_ui.width() + 1)
            y = min(max(y, rect.top()), rect.bottom() - self.popup_ui.height() + 1)

        self.popup_ui.move(x, y)
        self.popup_ui.show()
        self.popup_ui.activateWindow()
        self.popup_ui.setFocus()

    def shutdown(self):
        # self.overlay.close()
        # Stop native message loop.
        if self.detector is not None:
            self.detector.stop()
            self.detector.wait()
            self.detector.deleteLater()
            self.detector = None

    def cleanup(self):
        """
        instantiate abstract class cleanup()
        """
        self.shutdown()
        if self.popup_ui:
            self.popup_ui.shutdown()
        return super().cleanup()
