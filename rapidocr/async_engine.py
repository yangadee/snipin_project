from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from .rapidocr_worker import OcrWorker

from uuid import uuid4


class OcrService(QObject):
    """
    High-level OCR engine.

    Public API:
        recognize_pixmap()
    """

    initialized = pyqtSignal()
    init_failed = pyqtSignal(str)

    # For Ouput -> not use
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    recognize_requested = pyqtSignal(str, QImage)

    def __init__(self, engine_kwargs=None, parent=None):
        super().__init__(parent)

        self.engine_kwargs = engine_kwargs or {}
        self.thread = None
        self.worker = None

        self._init_thread()

    def _init_thread(self):
        self.thread = QThread()

        self.worker = OcrWorker(self.engine_kwargs)
        self.worker.moveToThread(self.thread)

        # Init flow
        self.thread.started.connect(self.worker.init_engine)
        self.worker.initialized.connect(self.initialized)
        self.worker.init_failed.connect(self.init_failed)
        self.recognize_requested.connect(self.worker.recognize_qimage)
        # OCR flow
        self.worker.result.connect(self._on_result)
        # Cleanup
        self.thread.finished.connect(self.worker.deleteLater)

        self.thread.start()
        self._callbacks = {}  # request_id -> callback

    def recognize_pixmap(self, pixmap: QPixmap, callback=None):
        """
        Public API: recognize from QPixmap -> Ocr worker thread.
        """
        if pixmap is None or pixmap.isNull():
            self.failed.emit("Invalid pixmap")
            return

        request_id = str(uuid4())
        self._callbacks[request_id] = callback
        qimage = pixmap.toImage()
        # Emit signal into worker thread
        self.recognize_requested.emit(request_id, qimage)

        # self.worker.recognize_qimage(request_id, qimage)

    def recognize_image(self, image_input: QPixmap | QImage, callback=None):
        """
        Public API: recognize from QPixmap or QImage -> Ocr worker thread.
        """
        if image_input is None or image_input.isNull():
            self.failed.emit("Invalid image input")
            return
        if isinstance(image_input, QPixmap):
            qimage = image_input.toImage()
        elif isinstance(image_input, QImage):
            qimage = image_input
        else:
            self.failed.emit("Unsupported image type")
            return
        request_id = str(uuid4())
        self._callbacks[request_id] = callback
        # Emit signal into worker thread
        self.recognize_requested.emit(request_id, qimage)

    def _on_result(self, request_id, text):
        callback = self._callbacks.pop(request_id, None)
        if callable(callback):
            callback(text, None)

    def _on_error(self, request_id, err):
        callback = self._callbacks.pop(request_id, None)
        if callable(callback):
            callback(None, err)

    def close(self):
        try:
            if self.worker:
                self.worker.close_engine()
            if self.thread:
                self.thread.quit()
                self.thread.wait()
        except Exception:
            pass

    def __del__(self):
        self.close()
