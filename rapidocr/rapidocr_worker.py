# from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage


class OcrWorker(QObject):
    """
    PyQt6 OCR worker.

    Recommended usage:
        - Convert QPixmap to QImage in GUI thread.
        - Pass QImage to this worker.
        - Worker saves QImage to temp file and calls OCR engine.
    """

    # External connect these
    initialized = pyqtSignal()
    init_failed = pyqtSignal(str)

    # External connect these
    result = pyqtSignal(str, str)  # request_id, text
    error = pyqtSignal(str, str)  # request_id, error

    def __init__(self, engine_kwargs=None):
        super().__init__()
        self.engine_kwargs = engine_kwargs or {}
        self.engine = None
        # Do NOT create RapidOcrEngine here if you want it initialized in worker thread.

    @pyqtSlot()
    def init_engine(self):
        """
        This slot runs in the worker thread if connected to thread.started.
        """
        try:
            from rapidocr import RapidOcrEngine

            self.engine = RapidOcrEngine(**self.engine_kwargs)
            self.initialized.emit()

        except Exception as e:
            self.init_failed.emit(str(e))

    @pyqtSlot(str, QImage)
    def recognize_qimage(self, request_id: str, qimage):
        """
        OCR QImage in worker thread.
        """
        try:
            if self.engine is None:
                raise RuntimeError("OCR engine is not initialized.")
            if qimage is None:
                raise ValueError("qimage is None")
            if hasattr(qimage, "isNull") and qimage.isNull():
                raise ValueError("qimage is null")
            text = self.engine.recognize_qimage(qimage)
            self.result.emit(request_id, text)
        except Exception as e:
            self.error.emit(request_id, str(e))

    @pyqtSlot()
    def close_engine(self):
        """
        Close OCR engine in the same worker thread.
        """
        try:
            if self.engine is not None:
                self.engine.close()
                self.engine = None
        except Exception:
            pass
