from sap_automation.client.config import SAPConfig
from sap_automation.client.connection import SAPConnection
from sap_automation.transactions.mm import ML81N, ML84


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

        # ---------------
        def ml81n(self, frs: str):
            # return ML81N(self.sap.session, frs).execute()
            return ML81N(self.sap.session, frs).run()

        # ---------------
        def ml84(
            self,
            frs: list[str] | None = None,
            pedidos: list[str] | None = None,
            fornecedores: list[str] | None = None,
            req_compras: list[str] | None = None,
            centros: list[str] | None = None,
            status: str = "tudo",
        ):
            ml84 = ML84(self.sap.session)

            if frs:
                ml84.filter_frs(frs)

            if pedidos:
                ml84.filter_pedidos(pedidos)

            if req_compras:
                ml84.filter_req_compras(req_compras)

            if fornecedores:
                ml84.filter_fornecedor(fornecedores)

            if centros:
                ml84.filter_centros(centros)

            ml84.status(status)

            return ml84.run()
