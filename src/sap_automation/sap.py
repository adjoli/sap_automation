from sap_automation.client.config import SAPConfig
from sap_automation.client.connection import SAPConnection
from sap_automation.transactions.mm import ML81N


class SAP:
    def __init__(self, config: SAPConfig):
        self.config = config
        self._connection = SAPConnection(config)
        self.session = None

        # módulos
        self.mm = self.MM(self)

    def connect(self):
        self.session = self._connection.connect()
        return self

    # -------------------------
    # MÓDULOS (MM, PM, etc.)
    # -------------------------

    class MM:
        def __init__(self, sap):
            self.sap = sap

        def ml81n(self, frs: str):
            return ML81N(self.sap.session, frs).execute()
