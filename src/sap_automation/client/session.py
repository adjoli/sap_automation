import logging
import time

from sap_automation.core.retry import retry
from sap_automation.types import VKEY


class SAPSession:
    def __init__(self, session):
        self._session = session
        self.logger = logging.getLogger("sap_automation.client.session")

    # ----------------------------------
    # CORE
    # ----------------------------------
    @retry(max_attempts=3, delay=0.5)
    def find(self, path: str):
        return self._session.findById(path)

    # -------
    def exists(self, path: str) -> bool:
        try:
            self.find(path)
            return True
        except Exception:
            return False

    # ----------------------------------
    # INTERAÇÕES
    # ----------------------------------
    def get_text(self, path: str) -> str:
        return self.find(path).text

    # -------
    def set_text(self, path: str, value: str):
        self.find(path).text = value

    # -------
    def get_radio(self, path: str) -> bool:
        return self.find(path).selected

    # -------
    def set_radio(self, path: str):
        self.find(path).select()

    # -------
    def press(self, path: str):
        self.find(path).press()

    # -------
    def send_vkey(self, key: int):
        self.find("wnd[0]").sendVKey(key)

    # ----------------------------------
    # TRANSAÇÃO
    # ----------------------------------
    def start_transaction(self, code: str):
        self.set_text("wnd[0]/tbar[0]/okcd", code)
        self.send_vkey(VKEY["Enter"])

    # -------
    def end_transaction(self):
        self.send_vkey(VKEY["F3"])

    # -------
    def send_command(self, command: str):
        """
        Executa comando SAP (/n, /o, /i, etc.)
        """
        self.find("wnd[0]/tbar[0]/okcd").text = command
        self.send_vkey(0)

    # -------
    def go_home(self):
        self.send_command("/n")

    # ----------------------------------
    # STATUS BAR
    # ----------------------------------

    def get_status_bar(self) -> str:
        try:
            return self.get_text("wnd[0]/sbar")
        except Exception:
            return ""

    # ----------------------------------
    # RETRY SIMPLES (ESSENCIAL)
    # ----------------------------------

    def safe_find(self, path: str, retries=3, delay=0.3):
        for i in range(retries):
            try:
                return self.find(path)
            except Exception as e:
                self.logger.warning(f"[Tentativa {i + 1}/{retries}] erro: {e}")
                time.sleep(delay)
        raise
