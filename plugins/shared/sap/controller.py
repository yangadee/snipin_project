from PyQt6.QtCore import QObject, QThread, pyqtSignal
from .models import SAPOperation, SAPOptions
from .worker import SAPHandler


class SAPController(QObject):
    # ============================================================
    # Commands -> SAP worker
    # ============================================================
    request = pyqtSignal(object, object)
    request_shutdown = pyqtSignal()

    # ============================================================
    # Worker -> application
    # ============================================================
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(object)
    result = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Thread + worker
        # --------------------------------------------------------
        self._thread = QThread(self)
        self._worker = SAPHandler()
        self._worker.moveToThread(self._thread)

        # Initialization
        # --------------------------------------------------------
        self._thread.started.connect(self._worker.initialize)

        # SAP commands
        # --------------------------------------------------------
        self.request.connect(self._worker.execute)

        # Shutdown
        # --------------------------------------------------------
        self.request_shutdown.connect(self._worker.shutdown)

        # Forward worker signals
        # --------------------------------------------------------
        self._worker.status.connect(self.status)
        self._worker.error.connect(self.error)
        self._worker.finished.connect(self.finished)
        self._worker.result.connect(self.result)

        # Start
        self._thread.start()

    # ============================================================
    # Public interface
    # ============================================================
    def execute(self, operation: SAPOperation, options: SAPOptions | None = None):
        if options is None:
            options = SAPOptions()
        self.request.emit(operation, options)

    def stop(self):
        if not self._thread.isRunning():
            return
        self.request_shutdown.emit()
        self._thread.quit()
        if not self._thread.wait(5000):
            self._thread.terminate()
            self._thread.wait()
