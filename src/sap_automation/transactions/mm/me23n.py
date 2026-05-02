import logging

from sap_automation.components.table import TableControl, validate_by_count
from sap_automation.core.converters import parse_sap_date
from sap_automation.models.mm.pedido import ItemPedido, Pedido
from sap_automation.parsers import parse_me23n_items
from sap_automation.transactions.base import Transaction


class ME23N(Transaction):
    def __init__(self, session, numero: str):
        super().__init__(session)
        self.numero = numero
        self.logger = logging.getLogger("sap.mm.me23n")

    # ----------------------------------
    # START
    # ----------------------------------

    def start(self):
        self.logger.info("Iniciando ME23N")
        self.session.start_transaction("ME23N")

    # ----------------------------------
    # EXECUÇÃO
    # ----------------------------------

    def execute(self) -> Pedido:
        self.logger.info(f"Abrindo pedido {self.numero}")

        self._open_document()

        header = self._read_header()
        itens = self._read_items()

        return Pedido(
            numero=self.numero,
            fornecedor=header.get("fornecedor"),
            data=header.get("data"),
            valor_total=header.get("valor_total", 0.0),
            itens=itens,
        )

    # ----------------------------------
    # PASSOS INTERNOS
    # ----------------------------------
    def _open_document(self):
        # botão "Outro documento"
        self.session.find("wnd[0]/tbar[1]/btn[17]").press()

        # campo do pedido
        self.session.set_text(
            "wnd[1]/usr/subSUB0:SAPLMEGUI:0003/ctxtMEPO_SELECT-EBELN", self.numero
        )

        # confirmar
        self.session.send_vkey(0, window="wnd[1]")

    # ----------
    def _read_header(self):
        data = {}

        fornecedor = self.session.get_text(
            "wnd[0]/usr/subSUB0:SAPLMEGUI:0019/subSUB0:SAPLMEGUI:0030/subSUB1:SAPLMEGUI:1105/ctxtMEPO_TOPLINE-SUPERFIELD"
        )
        data_pedido = self.session.get_text(
            "wnd[0]/usr/subSUB0:SAPLMEGUI:0019/subSUB0:SAPLMEGUI:0030/subSUB1:SAPLMEGUI:1105/ctxtMEPO_TOPLINE-BEDAT"
        )

        data["fornecedor"] = fornecedor
        data["data"] = parse_sap_date(data_pedido)

        return data

    # ----------
    def _read_items(self) -> list[ItemPedido]:
        self.logger.debug("Lendo itens do pedido")

        table = TableControl(
            self.session,
            id="wnd[0]/usr/subSUB0:SAPLMEGUI:0019/subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211",
            column_validator=validate_by_count,
        )

        rows = table.to_list()

        return parse_me23n_items(rows)
