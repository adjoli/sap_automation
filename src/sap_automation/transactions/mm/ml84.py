import logging
from enum import StrEnum

from sap_automation.components import MultiSelection
from sap_automation.models.mm import ML84Item
from sap_automation.parsers import parse_ml84
from sap_automation.services.exporter import SAPExporter
from sap_automation.transactions import Transaction


# ---------------------------------------
# STATUS DO ACEITE DE FRS (RADIO BUTTONS)
# ---------------------------------------
class ML84Status(StrEnum):
    NAO_ACEITO = "wnd[0]/usr/radP_KZAB_N"
    ACEITO = "wnd[0]/usr/radP_KZAB_J"
    TODOS = "wnd[0]/usr/radP_KZAB_A"


# ----------------------------------
# FILTROS DISPONÍVEIS
# ----------------------------------
class ML84Filter(StrEnum):
    FRS = "LBLNI"
    PEDIDO = "EBELN"
    REQ_COMPRA = "BANFN"
    FORNECEDOR = "LIFNR"
    CENTRO = "WERKS"


# -- OUTROS FILTROS DISPONÍVEIS --
# BSART - TIPO DOCUMENTO
# EBELN - DATA DOCUMENTO
# EKGRP - GRUPO DE COMPRAS
# EKORG - ORGANIZAÇÃO COMPRAS
# ERDAT - DATA DE CRIAÇÃO
# FKNUM - NUM CUSTOS FRETE
# LBLNE - NÚMERO EXTERNO
# MATKL - GRUPO DE MERCADORIAS
# SPEC  - REL. SERVIÇOS MODELO
# WARPL - PLANO MANUTENÇÃO


# ----------------------------------------------
# HELPER PARA RESOLVER BOTÃO DE SELEÇÃO MÚLTIPLA
# ----------------------------------------------
def build_button_id(field: ML84Filter) -> str:
    return f"wnd[0]/usr/btn%_S_{field}_%_APP_%-VALU_PUSH"


# =======================
# CLASSE PRINCIPAL
# =======================
class ML84(Transaction):
    def __init__(self, session):
        super().__init__(session)
        self.logger = logging.getLogger("sap.mm.ml84")

        self._filters: dict[ML84Filter, list[str]] = {}
        self._status: ML84Status = ML84Status.TODOS

    # ----------------------------------
    # CONFIGURAÇÃO DE FILTROS
    # ----------------------------------
    def add_filter(self, field: ML84Filter, values: list[str]):
        self._filters[field] = values
        return self

    # helpers opcionais (ergonomia)
    def filter_frs(self, values: list[str]):
        return self.add_filter(ML84Filter.FRS, values)

    def filter_pedidos(self, values: list[str]):
        return self.add_filter(ML84Filter.PEDIDO, values)

    def filter_req_compras(self, values: list[str]):
        return self.add_filter(ML84Filter.REQ_COMPRA, values)

    def filter_fornecedor(self, values: list[str]):
        return self.add_filter(ML84Filter.FORNECEDOR, values)

    def filter_centros(self, values: list[str]):
        return self.add_filter(ML84Filter.CENTRO, values)

    # ----------------------------------
    # STATUS
    # ----------------------------------
    def status(self, status: ML84Status | str):
        if isinstance(status, str):
            match value := status.lower():
                case "aceito" | "accepted":
                    self._status = ML84Status.ACEITO
                case "nao_aceito" | "não_aceito" | "not_accepted":
                    self._status = ML84Status.NAO_ACEITO
                case "todos" | "tudo" | "all":
                    self._status = ML84Status.TODOS
                case _:
                    raise ValueError(f"Status inválido: {value}")

        return self

    # ----------------------------------
    # EXECUÇÃO
    # ----------------------------------
    def start(self):
        self.logger.info("Iniciando ML84")
        self.session.start_transaction("ML84")

    # def execute(self) -> list[ML84Item]:
    def execute(self):
        self._apply_filters()
        self._apply_status()
        self._run()

        html = SAPExporter(self.session).export_html()

        self.logger.info("ML84 executada com sucesso")

        return parse_ml84(html)

    # ----------------------------------
    # PASSOS INTERNOS
    # ----------------------------------
    def _apply_filters(self):
        for field, values in self._filters.items():
            btn_id = build_button_id(field)

            self.logger.debug(f"Abrindo seleção múltipla: {field.name}")

            self.session.find(btn_id).press()

            multi = MultiSelection(self.session)

            multi.clear()
            multi.include_values(values)
            multi.apply()

    # ----------
    def _apply_status(self):
        self.logger.debug(f"Aplicando status: {self._status.name}")

        self.session.set_radio(self._status.value)

    # ----------
    def _run(self):
        # F8
        self.session.send_vkey(8)
