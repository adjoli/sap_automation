import subprocess
import time

import win32com.client
import win32gui
from pythoncom import CoInitialize, com_error

from .session import SAPSession


class SAPConnection:
    def __init__(self, config):
        self.config = config
        self._application = None

    def connect(self) -> SAPSession:
        self._application = self._get_engine()

        if self._application.Connections.count == 0:
            self._open_connection()

        connection = self._application.Children(0)
        session = connection.Children(0)

        return SAPSession(session)

    # ----------------------------------------
    # CORE
    # ----------------------------------------
    def _get_engine(self):
        try:
            CoInitialize()
            return win32com.client.GetObject("SAPGUI").GetScriptingEngine
        except com_error:
            self._start_sap()
            return win32com.client.GetObject("SAPGUI").GetScriptingEngine

    # ----------------------------------------
    def _start_sap(self):
        subprocess.Popen(self.config.saplogon_path)

        timeout = 15
        start = time.time()

        while time.time() - start < timeout:
            if win32gui.FindWindow(None, self.config.sap_window):
                return
            time.sleep(0.5)

        raise TimeoutError("SAP Logon não iniciou")

    # ----------------------------------------
    def _open_connection(self):
        conn_name = self._resolve_env()

        self._application.OpenConnection(conn_name, True)

        connection = self._application.Children(0)
        session = connection.Children(0)

        self._login(session)

    # ----------------------------------------
    def _resolve_env(self):
        if self.config.environment == "QAS":
            return "TEQ - SAP ECC Transpetro QAS"
        return "F04 - SAP Scripting Transpetro PRD"

    # ----------------------------------------
    def _login(self, session):
        session.findById("wnd[0]/usr/txtRSYST-MANDT").text = self.config.client
        session.findById("wnd[0]/usr/txtRSYST-BNAME").text = self.config.user
        session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = self.config.password
        session.findById("wnd[0]/usr/txtRSYST-LANGU").text = self.config.language
        session.findById("wnd[0]").sendVKey(0)
