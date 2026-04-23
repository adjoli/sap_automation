from sap_automation.components import TableControl
from sap_automation.core.logging import get_logger
from sap_automation.models.frs import FRS, Fiscal
from sap_automation.transactions.base import Transaction


class ML81N(Transaction):
    def __init__(self, session, frs: str):
        super().__init__(session)

        if not frs:
            raise ValueError("FRS é obrigatória")

        self.frs = frs
        self.logger = get_logger("sap.mm.ml81n", frs=frs)

    # ----------------------------------
    # API
    # ----------------------------------

    def execute(self) -> FRS:
        self.logger.info("Iniciando ML81N")

        self.session.start_transaction("ML81N")
        self._load_frs()

        data = self._extract_data()

        self.logger.info("ML81N finalizada com sucesso")

        return FRS(**data)

    # ----------------------------------
    # CARREGAMENTO
    # ----------------------------------

    def _load_frs(self):
        self.session.press("wnd[0]/tbar[1]/btn[17]")
        self.session.set_text("wnd[1]/usr/ctxtRM11R-LBLNI", self.frs)
        self.session.send_vkey(0)

        if self.session.exists("wnd[2]/usr/txtMESSTXT1"):
            raise ValueError(f"FRS {self.frs} não existe")

    # ----------------------------------
    # EXTRAÇÃO
    # ----------------------------------

    def _extract_data(self) -> dict:
        data = {"numero": self.frs, "fiscais": []}

        # cabeçalho
        data["pedido"] = self.session.get_text("wnd[0]/usr/txtRM11R-BSTNR")
        data["texto_breve"] = self.session.get_text("wnd[0]/usr/txtESSR-TXZ01")
        data["liberada"] = self._has_acceptance()

        # abas
        self._load_dados_basicos(data)
        self._load_valores(data)
        self._load_fiscais(data)

        return data

    # ----------------------------------
    # REGRAS
    # ----------------------------------

    def _has_acceptance(self) -> bool:
        icon = self.session.find("wnd[0]/usr/txtRM11R-KZABN_TXT")
        return icon.IconName == "S_TL_G"

    # ----------------------------------
    # ABAS
    # ----------------------------------

    def _select_tab(self, tab_id: str):
        self.session.find(tab_id).select()

    # ------------
    def _load_dados_basicos(self, data: dict):
        self._select_tab("wnd[0]/usr/tabsTAB_HEADER/tabpREGG")

        data["categoria"] = self.session.get_text(
            "wnd[0]/usr/tabsTAB_HEADER/tabpREGG/ssubSUB_HEADER:SAPLMLSR:0410/cmbESSR-KNTTP"
        ).strip()

        data["resp_interno"] = self.session.get_text(
            "wnd[0]/usr/tabsTAB_HEADER/tabpREGG/ssubSUB_HEADER:SAPLMLSR:0410/txtESSR-SBNAMAG"
        )

        data["resp_externo"] = self.session.get_text(
            "wnd[0]/usr/tabsTAB_HEADER/tabpREGG/ssubSUB_HEADER:SAPLMLSR:0410/txtESSR-SBNAMAN"
        )

    # ------------
    def _load_valores(self, data: dict):
        self._select_tab("wnd[0]/usr/tabsTAB_HEADER/tabpREGW")

        data["valor"] = self.session.get_text(
            "wnd[0]/usr/tabsTAB_HEADER/tabpREGW/ssubSUB_VALUES:SAPLMLSR:0450/txtESSR-LWERT"
        )

    # ------------
    def _load_fiscais(self, data: dict):
        self._select_tab("wnd[0]/usr/tabsTAB_HEADER/tabpESCR")

        self.session.press(
            "wnd[0]/usr/tabsTAB_HEADER/tabpESCR/ssubSUBUSCR:SAPLXMLU:0399/btnBT_GERFIS"
        )

        try:
            table = TableControl(
                self.session, "wnd[1]/usr/tblSAPLZGFMM_GERFISTC_FISCAIS_NB1"
            )

            fiscais = [
                Fiscal(chave=row.get("Chave"), nome=row.get("Nome"))
                for row in table.to_list()
                if row.get("Sel.")  # CheckBox do fiscal está selecionada
            ]

        except Exception as e:
            self.logger.warning(f"Erro ao ler fiscais: {e}")
            fiscais = []

        data["fiscais"] = fiscais

        # fechar popup
        if self.session.exists("wnd[1]"):
            self.session.find("wnd[1]").close()
