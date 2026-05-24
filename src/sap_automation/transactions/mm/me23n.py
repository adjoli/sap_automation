import logging

from sap_automation.core.types import ReadMode
from sap_automation.exceptions.errors import ConfigError
from sap_automation.models.mm.pedido import Pedido
from sap_automation.screens.me23n_screen import ME23NScreen
from sap_automation.transactions.base import Transaction


class ME23N(Transaction):
    def __init__(self, session, numero: str, mode: ReadMode = ReadMode.DEEP):
        """
        Parâmetros
        ----------
        session : SAPSession
        numero  : str — número do pedido
        mode    : ReadMode — profundidade da extração (padrão: DEEP)

        ReadMode.SHALLOW — apenas cabeçalho (status, liberado, texto_breve, tlc)
        ReadMode.DEEP    — cabeçalho + todos os itens + histórico de pagamento
        """
        super().__init__(session)

        if not numero or not numero.strip():
            raise ConfigError("Número do pedido é obrigatório")

        self.numero = numero.strip()
        self.mode = mode
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

        screen = ME23NScreen(self.session)

        header = screen.read_header()
        items = screen.read_items()

        return Pedido(
            numero=self.numero,
            tipo=header.get("tipo"),
            cod_fornecedor=header.get("cod_fornecedor"),
            desc_fornecedor=header.get("desc_fornecedor"),
            data=header.get("data"),
            texto_breve=header.get("texto_breve"),
            grp_comprador=header.get("grp_comprador"),
            status=header.get("liberado"),
            valor_total=header.get("valor_total"),
            tlc=header.get("tlc"),
            itens=items,
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
