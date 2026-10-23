"""
Main Qt Thread
    |
    |  request_mmbe.emit("12NC")
    v
SAP QThread
    |
    +-- SAPHandler
          |
          +-- _get_session()
          +-- _create_session()
          +-- mmbe()
          +-- future SAP operations
                MB51()
                MD04()
                ...
    GUI
    |
    v
    SAPController.execute(operation, options)
    |
    | request.emit(operation, options)
    v
    SAPHandler.execute(operation, options)
    |
    v
    SAPHandler._zih3(options)
"""

import logging
import os
import time
import subprocess
import pythoncom
import win32com.client  # type: ignore
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from plugins.shared.sap.models import SAPOperation, SAPOptions

import ctypes

user32 = ctypes.windll.user32

SAP_LOGON_EXE = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"
SAP_CONNECTION = "04.R3 PRD"
MAX_SESSIONS = 6


class SAPHandler(QObject):
    """
    Worker handling all SAP GUI automation.
    This object should live entirely inside its own QThread.
    """

    # ------------------------------------------------------------
    # Output signals
    # ------------------------------------------------------------
    connected = pyqtSignal()
    # finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    # Could be useful later for returning data
    result = pyqtSignal(object)
    finished = pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self._sap_gui_auto = None
        self._application = None
        self._connection = None
        self._session = None
        self._handlers = {
            SAPOperation.MMBE: self._mmbe,
            SAPOperation.ZMRN: self._zmrn,
            SAPOperation.ZPACK: self._zpack,
            SAPOperation.IW73: self._iw73,
            SAPOperation.ZSTS: self._zsts,
            SAPOperation.IE03: self._ie03,
            SAPOperation.ZIH3: self._zih3,
            SAPOperation.ZLPR: self._zlpr,
        }

    # ============================================================
    # Thread lifecycle
    # ============================================================
    @pyqtSlot()
    def initialize(self):
        """
        Called after the worker thread starts.
        COM must be initialized in the thread that uses it.
        """
        pythoncom.CoInitialize()

    @pyqtSlot()
    def shutdown(self):
        """
        Clean up SAP COM references and COM initialization.
        """
        self._session = None
        self._connection = None
        self._application = None
        self._sap_gui_auto = None
        pythoncom.CoUninitialize()

    @pyqtSlot(object, object)
    def execute(self, operation: SAPOperation, options: SAPOptions):
        try:
            handler = self._handlers.get(operation)
            if handler is None:
                raise ValueError(f"Unknown SAP operation: {operation}")
            self.status.emit(f"Running {operation.name}...")
            result = handler(options)
            self.finished.emit(operation, result)
        except Exception as exc:
            self.error.emit(f"{operation.name} failed: " f"{type(exc).__name__}: {exc}")

    # ============================================================
    # SAP GUI initialization
    # ============================================================
    def _is_process_running(self, process_name: str) -> bool:
        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"IMAGENAME eq {process_name}",
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
        return process_name.lower() in result.stdout.lower()

    def _start_sap_gui(self):
        """
        Start SAP Logon minimized if it is not already running.
        """
        SW_SHOWMINNOACTIVE = 7
        if self._is_process_running("saplogon.exe"):
            return
        if not os.path.isfile(SAP_LOGON_EXE):
            raise FileNotFoundError(
                f"SAP Logon executable not found:\n {SAP_LOGON_EXE}"
            )
        self.status.emit("Starting SAP Logon...")
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.Popen([SAP_LOGON_EXE], startupinfo=startupinfo)

    def _wait_for_sap_gui(self, timeout: float = 30.0):
        """
        Wait until SAP exposes its SAPGUI COM object.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                return win32com.client.GetObject("SAPGUI")
            except Exception:
                time.sleep(0.2)
        raise TimeoutError(
            "SAP Logon started but SAP GUI scripting "
            "did not become available within 30 seconds."
        )

    # ============================================================
    # SAP connection/session handling
    # ============================================================
    def _wait_for_new_session(
        self, connection, old_ids: set[str], timeout: float = 30.0
    ):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                count = connection.Children.Count
                for i in range(count):
                    session = connection.Children(i)
                    if session.Id not in old_ids:
                        return session
            except Exception:
                pass
            time.sleep(0.2)
        raise TimeoutError("Timed out waiting for new SAP session.")

    def _wait_for_first_session(self, connection, timeout: float = 30.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                count = connection.Children.Count
                if count > 0:
                    return connection.Children(count - 1)
            except Exception:
                pass
            time.sleep(0.2)
        raise TimeoutError("Timed out waiting for SAP session.")

    # def __get_session(self):
    #     """
    #     Python equivalent of Login_SAPGUI().
    #     Start SAP Logon if necessary and return a usable session.
    #     """
    #     # --------------------------------------------------------
    #     # Start SAP Logon
    #     # --------------------------------------------------------
    #     self._start_sap_gui()
    #     # --------------------------------------------------------
    #     # Connect to SAP GUI scripting
    #     # --------------------------------------------------------
    #     sap_gui_auto = self._wait_for_sap_gui()
    #     application = sap_gui_auto.GetScriptingEngine
    #     # Keep references
    #     self._sap_gui_auto = sap_gui_auto
    #     self._application = application
    #     # --------------------------------------------------------
    #     # Existing SAP connection
    #     # --------------------------------------------------------
    #     if application.Children.Count > 0:
    #         connection = application.Children(0)
    #         self._connection = connection
    #         count = connection.Children.Count
    #         if count == 0:
    #             raise RuntimeError("SAP connection exists but has no sessions.")
    #         session = connection.Children(count - 1)
    #         # ----------------------------------------------------
    #         # Already session manager
    #         # ----------------------------------------------------
    #         if session.Info.Transaction == "SESSION_MANAGER":
    #             self._session = session
    #             self.connected.emit()
    #             return session
    #         # ----------------------------------------------------
    #         # Maximum sessions reached
    #         # ----------------------------------------------------
    #         if count >= MAX_SESSIONS:
    #             self.status.emit(
    #                 "Maximum number of SAP GUI sessions reached. "
    #                 "Using the existing session."
    #             )
    #             try:
    #                 if session.Info.Transaction != "SESSION_MANAGER":
    #                     session.EndTransaction()
    #             except Exception:
    #                 pass
    #             self._session = session
    #             self.connected.emit()
    #             return session
    #         # ----------------------------------------------------
    #         # Create new session
    #         # ----------------------------------------------------
    #         before_ids = {connection.Children(i).Id for i in range(count)}
    #         self.status.emit("Creating new SAP session...")
    #         session.CreateSession()
    #         session = self._wait_for_new_session(connection, before_ids)
    #         self._session = session
    #         self.connected.emit()
    #         return session
    #     # --------------------------------------------------------
    #     # No SAP connection yet
    #     # --------------------------------------------------------
    #     self.status.emit(f"Opening SAP connection: {SAP_CONNECTION}")
    #     connection = application.OpenConnection(SAP_CONNECTION, False)
    #     self._connection = connection
    #     session = self._wait_for_first_session(connection, timeout=30)
    #     self._session = session
    #     self.connected.emit()
    #     return session

    def _get_session(self):
        """
        Return the cached SAP session when possible.
        Only reconnect/discover SAP GUI if the cached session
        is no longer valid.
        """
        # ============================================================
        # Fast path: reuse cached session
        # ============================================================
        if self._session is not None:
            try:
                # Minimal COM call to verify the COM object is alive.
                _ = self._session.Id
                return self._session
            except Exception:
                # SAP closed, session closed, COM object invalid, etc.
                self._session = None
        # ============================================================
        # Slow path: discover/connect/create SAP session
        # ============================================================
        return self._connect_session()

    def _connect_session(self):
        """
        Discover SAP GUI and create/acquire a session.
        This is the expensive path and should normally only happen:
            - first SAP operation
            - SAP GUI restarted
            - cached session was closed
        """
        # ------------------------------------------------------------
        # Start SAP Logon if necessary
        # ------------------------------------------------------------
        self._start_sap_gui()
        # ------------------------------------------------------------
        # Connect to SAP GUI scripting
        # ------------------------------------------------------------
        sap_gui_auto = self._wait_for_sap_gui()
        application = sap_gui_auto.GetScriptingEngine
        self._sap_gui_auto = sap_gui_auto
        self._application = application
        # ------------------------------------------------------------
        # Existing SAP connection
        # ------------------------------------------------------------
        logging.debug("application Children Count %d", application.Children.Count)
        if application.Children.Count > 0:
            connection = application.Children(0)
            logging.debug("Use application connection: %s", connection.Description)
            self._connection = connection
            if connection.DisabledByServer:
                raise RuntimeError(
                    "SAP GUI scripting is disabled by the application server."
                )

            count = connection.Children.Count
            """
            2026/10/20 fix: make it robust when connection report zero-session.
            if count == 0:
                raise RuntimeError("SAP connection exists but has no sessions.")
            session = connection.Children(count - 1)      
            """
            # Connection exists, but its first session may not be ready yet.
            logging.debug("connection Children Count %d", count)
            if count == 0:
                self.status.emit("Waiting for the first SAP session...")
                session = self._wait_for_first_session(connection, timeout=30)
                # Refresh the count after waiting.
                count = connection.Children.Count
            else:
                session = connection.Children(count - 1)

            # --------------------------------------------------------
            # Already SESSION_MANAGER
            # --------------------------------------------------------
            if session.Info.Transaction == "SESSION_MANAGER":
                return self._cache_session(session)
            # --------------------------------------------------------
            # Maximum number of sessions
            # --------------------------------------------------------
            if count >= MAX_SESSIONS:
                self.status.emit(
                    "Maximum number of SAP GUI sessions reached. "
                    "Using the existing session."
                )
                logging.debug(
                    "Maximum number of SAP GUI sessions reached. Using the existing session."
                )
                try:
                    session.EndTransaction()
                except Exception:
                    pass
                return self._cache_session(session)
            # --------------------------------------------------------
            # Create a dedicated new session
            # --------------------------------------------------------
            before_ids = {connection.Children(i).Id for i in range(count)}
            self.status.emit("Creating new SAP session...")
            logging.debug("Creating new SAP session...")
            session.CreateSession()
            session = self._wait_for_new_session(connection, before_ids)
            return self._cache_session(session)
        # ------------------------------------------------------------
        # No SAP connection
        # ------------------------------------------------------------
        self.status.emit(f"Opening SAP connection: {SAP_CONNECTION}")
        connection = application.OpenConnection(SAP_CONNECTION, False)
        self._connection = connection
        session = self._wait_for_first_session(connection, timeout=30)
        return self._cache_session(session)

    def _cache_session(self, session):
        """
        Store and return the active SAP session.
        """
        self._session = session
        self.connected.emit()
        return session

    # ============================================================
    # Common helpers
    # ============================================================

    def force_focus_sap(self, wnd):
        hwnd = wnd.Handle
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)

    def _open_transaction(self, session, transaction: str):
        """
        Open an SAP transaction through the command field.
        Explicitly terminates the current transaction and launches the requested one
        """
        wnd = session.findById("wnd[0]")
        # hwnd = wnd.Handle
        # user32.ShowWindow(hwnd, 0)  # SW_HIDE
        # session.findById("wnd[0]/tbar[0]/okcd").text = f"/n{transaction}"
        session.StartTransaction(transaction)
        self.force_focus_sap(wnd)

        # wnd.sendVKey(0)

        # wnd = session.findById("wnd[0]")
        # user32.ShowWindow(wnd.Handle, 0)  # SW_HIDE
        # user32.ShowWindow(hwnd, 2)   # SW_SHOWMINIMIZED

    def _execute_transaction(self, session):
        """
        Execute current selection screen using the standard
        SAP Execute button (F8).
        """
        # wnd = session.findById("wnd[0]")
        # session.findById("wnd[0]/tbar[1]/btn[8]").press()
        wnd = session.findById("wnd[0]")
        wnd.sendVKey(8)
        self.force_focus_sap(wnd)

    def _transaction_error(self, transaction: str, exc: Exception):
        """
        Common SAP transaction error handling.
        """
        message = f"{transaction} error: " f"{type(exc).__name__}: {exc}"
        self.error.emit(message)

    # ============================================================
    # Transaction handler implements
    # ============================================================
    def _mmbe(self, options: SAPOptions):
        session = self._get_session()
        self._open_transaction(session, "MMBE")
        if options.material:
            session.findById("wnd[0]/usr/ctxtMS_MATNR-LOW").text = options.material
        session.findById("wnd[0]/usr/ctxtMS_WERKS-LOW").text = options.plant or "TW*"
        self._execute_transaction(session)

    def _zmrn(self, options: SAPOptions):
        session = self._get_session()
        self._open_transaction(session, "ZMRN")
        session.findById("wnd[0]/usr/radPA_MRET").select()
        session.findById("wnd[0]/usr/ctxtSO_IWERK-LOW").text = options.plant or "TW*"
        if options.service_order:
            session.findById("wnd[0]/usr/ctxtSO_AUFNR-LOW").text = options.service_order
        if options.machine:
            session.findById("wnd[0]/usr/ctxtSO_MACH-LOW").text = options.machine
        if options.material:
            session.findById("wnd[0]/usr/ctxtSO_MATNR-LOW").text = options.material
        self._execute_transaction(session)

    def _zpack(self, options: SAPOptions):
        session = self._get_session()
        self._open_transaction(session, "ZPACK")
        if options.material:
            session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = options.material
        self._execute_transaction(session)

    def _ie03(self, options: SAPOptions):
        session = self._get_session()
        self._open_transaction(session, "IE03")
        if options.machine:
            session.findById("wnd[0]/usr/ctxtRM63E-EQUNR").text = options.machine
            session.findById("wnd[0]/tbar[0]/btn[0]").press()

    def _zih3(self, options: SAPOptions):
        session = self._get_session()
        self._open_transaction(session, "ZIH3")
        if options.machine:
            session.findById("wnd[0]/usr/ctxtP_EQUNR").text = options.machine
            session.findById("wnd[0]/usr/ctxtP_WERKS").text = options.plant or "NL01"
        self._execute_transaction(session)

    def _zpack(self, options: SAPOptions):
        """
        ZPACK: packaging
        Dangerous goods, Packaging, Cleaning and Handling info.
        """
        transaction = "ZPACK"
        try:
            self.status.emit(f"Opening {transaction}...")
            session = self._get_session()
            self._open_transaction(session, transaction)
            if options.material:
                session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = options.material
            # Original AHK used F8 after WinActivate.
            # Direct SAP scripting is preferable.
            self._execute_transaction(session)
            self.status.emit(f"{transaction} opened.")
        except Exception as exc:
            self._transaction_error(transaction, exc)

    def _iw73(self, options: SAPOptions):
        """
        IW73 Display Service Order.
        """
        transaction = "IW73"
        try:
            self.status.emit(f"Opening {transaction}...")
            session = self._get_session()
            self._open_transaction(session, transaction)
            if options.machine:
                session.findById("wnd[0]/usr/ctxtEQUNR-LOW").text = options.machine
            self._execute_transaction(session)
            self.status.emit(f"{transaction} opened.")
        except Exception as exc:
            self._transaction_error(transaction, exc)

    def _zsts(self, options: SAPOptions):
        """
        ZSTS Survey Table On Service Materials / check Consumable
        """
        transaction = "ZSTS"
        try:
            self.status.emit(f"Opening {transaction}...")
            session = self._get_session()
            self._open_transaction(session, transaction)
            if options.material:
                session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = options.material
            session.findById("wnd[0]/usr/ctxtS_PLANT-LOW").text = "TW*"
            session.findById("wnd[0]/usr/ctxtP_SALES").text = "NL01"
            session.findById("wnd[0]/usr/chkP_PRNT13").selected = True
            session.findById("wnd[0]/usr/chkP_PRNT26").selected = True
            self._execute_transaction(session)
            self.status.emit(f"{transaction} opened.")
        except Exception as exc:
            self._transaction_error(transaction, exc)

    def _zlpr(self, options: SAPOptions):
        session = self._get_session()
        self._open_transaction(session, "ZLPR")
        if options.material:
            session.findById("wnd[0]/usr/ctxtP_CURR").text = "NLD"
            session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = options.material
        self._execute_transaction(session)


# def spy_fields(session):
#     """
#     Inspect fields: eg. ZLPR / ZMRN
#     """
#     try:
#         usr_container = session.findById("wnd[0]/usr/")

#         for i in range(usr_container.Children.Count):
#             child = usr_container.Children(i)
#             obj_id = child.Id
#             obj_type = child.Type
#             obj_text = child.Text if hasattr(child, "Text") else ""
#             # Show obj that has no text, mean input.
#             print(f"[{i}] \t Type: {obj_type} \t ID: {obj_id} \t text: {obj_text}")
#     except Exception as e:
#         print(f"{e}")
