import logging
import re

from sap_automation.components import Section, TableControl, TabStrip
from sap_automation.components.explorer import SAPExplorer
from sap_automation.components.table import validate_by_count
from sap_automation.core.converters import parse_sap_date, parse_sap_float
from sap_automation.parsers.me23n_parser import parse_me23n_items
from sap_automation.screens.base import Screen

# ─── Tab map do cabeçalho ─────────────────────────────────────────────────────
_HEADER_TAB_MAP = {
    "Remessa": "TABHDT1",
    "Condições": "TABHDT2",
    "Textos": "TABHDT3",
    "Endereço": "TABHDT4",
    "Comunicação": "TABHDT5",
    "Parceiro": "TABHDT6",
    "Dados adicionais": "TABHDT7",
    "Dados organizacionais": "TABHDT9",
    "Status": "TABHDT10",
    "Dados do cliente": "TABHDT11",
    "Estratégia de liberação": "TABHDT12",
    "Detalhes externos": "TABHDT13",
}

# ─── Sufixo fixo após o prefixo variável ──────────────────────────────────────
_SUFIXO_HEADER_TABS = (
    "/subSUB1:SAPLMEVIEWS:1100"
    "/subSUB2:SAPLMEVIEWS:1200"
    "/subSUB1:SAPLMEGUI:1102"
    "/tabsHEADER_DETAIL"
)


def _parse_fornecedor(texto: str | None) -> tuple[str | None, str | None]:
    """
    Separa o texto do campo fornecedor em código e descrição.
    Ex: "9000013096 C.HENRIQUE BODEMEIER & CIA LTDA"
    Retorna (cod_fornecedor, desc_fornecedor).
    """
    if not texto or not texto.strip():
        return None, None
    m = re.match(r"^(\d+)\s+(.+)$", texto.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None, texto.strip()


class ME23NScreen(Screen):
    """
    Tela da transação ME23N — Exibir Pedido de Compras.

    O prefixo do ID (subSUB0:SAPLMEGUI:XXXX) varia conforme o tipo do pedido.
    _resolve_prefix() descobre o prefixo correto tentando session.find()
    com os valores conhecidos — sem walk recursivo.

    Adicione novos prefixos em _PREFIXOS_CONHECIDOS conforme encontrar
    novos tipos de pedido via SAP Tracker.
    """

    # Prefixos conhecidos — adicionar novos conforme encontrar via SAP Tracker
    _PREFIXOS_CONHECIDOS = [
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0013",
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0019",
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0020",
    ]

    def __init__(self, session):
        super().__init__(session)
        self.logger = logging.getLogger("sap.screens.me23n")
        self._prefix_cache: str | None = None

    # ------------------------------------------------------------------
    # RESOLUÇÃO DINÂMICA DE IDs
    # ------------------------------------------------------------------

    def _resolve_prefix(self) -> str:
        """
        Descobre o prefixo variável da ME23N tentando session.find()
        com os valores conhecidos de subSUB0:SAPLMEGUI:XXXX.

        Usa acesso direto via ID — sem walk recursivo, sem dependência
        do estado de expansão de seções.

        Se nenhum prefixo conhecido funcionar, adicione o novo valor
        a _PREFIXOS_CONHECIDOS consultando o SAP Tracker com o pedido aberto.
        """
        if self._prefix_cache:
            return self._prefix_cache

        for prefix in self._PREFIXOS_CONHECIDOS:
            candidate = prefix + _SUFIXO_HEADER_TABS
            try:
                self.session.find(candidate)
                self._prefix_cache = prefix
                self.logger.debug(f"Prefixo ME23N: {prefix}")
                return prefix
            except Exception:
                continue

        raise RuntimeError(
            f"Prefixo da ME23N não encontrado entre os conhecidos: "
            f"{self._PREFIXOS_CONHECIDOS}. "
            f"Abra o SAP Tracker com o pedido, localize tabsHEADER_DETAIL "
            f"e adicione o novo prefixo (subSUB0:SAPLMEGUI:XXXX) em "
            f"ME23NScreen._PREFIXOS_CONHECIDOS."
        )

    def _build_ids(self, prefix: str) -> dict:
        """Monta os IDs completos da ME23N a partir do prefixo."""
        return {
            "topo": (f"{prefix}/subSUB0:SAPLMEGUI:0030/subSUB1:SAPLMEGUI:1105"),
            "secao0": (f"{prefix}/subSUB1:SAPLMEVIEWS:1100/subSUB1:SAPLMEVIEWS:4000"),
            "header_tabs": (f"{prefix}{_SUFIXO_HEADER_TABS}"),
            "tlc_tab": (
                f"{prefix}/subSUB1:SAPLMEVIEWS:1100"
                f"/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1102"
                f"/tabsHEADER_DETAIL/tabpTABHDT11"
                f"/ssubTABSTRIPCONTROL2SUB:SAPLMEGUI:1227"
                f"/ssubCUSTOMER_DATA_HEADER:SAPLXM06:0101/tabsTABSTRIP_0101"
            ),
            "tabela": (
                f"{prefix}/subSUB2:SAPLMEVIEWS:1100"
                f"/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211"
                f"/tblSAPLMEGUITC_1211"
            ),
        }

    # ------------------------------------------------------------------
    # SEÇÕES
    # ------------------------------------------------------------------

    def section(self, index: int) -> Section:
        """
        Acessa uma seção colapsável da ME23N pelo índice (0-based).
        [0] Cabeçalho, [1] Itens, [2] Detalhes do item.
        """
        if index == 0:
            prefix = self._resolve_prefix()
            ids = self._build_ids(prefix)
            return Section(self.session.find(ids["secao0"]))

        containers = self.explorer.find_collapsible_sections()
        if index >= len(containers):
            raise IndexError(
                f"Seção {index} não existe. Total encontradas: {len(containers)}"
            )
        return Section(containers[index])

    # ------------------------------------------------------------------
    # TABSTRIP DO CABEÇALHO
    # ------------------------------------------------------------------

    @property
    def header_tabs(self) -> TabStrip:
        """TabStrip do cabeçalho — usa prefixo dinâmico."""
        prefix = self._resolve_prefix()
        ids = self._build_ids(prefix)
        return TabStrip.from_path_with_map(
            self.session,
            ids["header_tabs"],
            tab_map=_HEADER_TAB_MAP,
        )

    # ------------------------------------------------------------------
    # LEITURA DO CABEÇALHO
    # ------------------------------------------------------------------

    def read_header(self) -> dict:
        """
        Lê os dados do cabeçalho do pedido navegando pelas abas relevantes.

        Fluxo
        -----
        1. Resolve prefixo e monta IDs dinamicamente
        2. Expande seção [0]
        3. Lê campos do topo
        4. Navega pelas abas: Status, Textos, Dados do cliente → TLC
        """
        result = {}

        # resolve prefixo e monta IDs — feito uma vez, cacheado
        prefix = self._resolve_prefix()
        ids = self._build_ids(prefix)

        # expande seção [0] para revelar o TabStrip
        self.section(0).expand()

        # campos do topo (seção fixa — sempre visível)
        top_explorer = SAPExplorer(self.session.find(ids["topo"]))
        fields = top_explorer.read_fields(
            "cmbMEPO_TOPLINE-BSART",  # tipo do pedido
            "MEPO_TOPLINE-SUPERFIELD",  # código + nome do fornecedor
            "ctxtMEPO_TOPLINE-BEDAT",  # data do documento
        )
        result["tipo"] = (fields.get("cmbMEPO_TOPLINE-BSART") or "").strip() or None
        cod, desc = _parse_fornecedor(fields.get("MEPO_TOPLINE-SUPERFIELD"))
        result["cod_fornecedor"] = cod
        result["desc_fornecedor"] = desc
        result["data"] = parse_sap_date(fields.get("ctxtMEPO_TOPLINE-BEDAT"))

        tabs = TabStrip.from_path_with_map(
            self.session,
            ids["header_tabs"],
            tab_map=_HEADER_TAB_MAP,
        )

        # aba Dados organizacionais
        tabs.select("Dados organizacionais")
        fields = tabs.current_explorer().read_fields(
            "ctxtMEPO1222-EKGRP",  # grupo comprador
        )
        result["grp_comprador"] = fields.get("ctxtMEPO1222-EKGRP")

        # aba Status
        tabs.select("Status")
        fields = tabs.current_explorer().read_fields(
            "MEPO1232-STATUS02",  # status de liberação
            "txtMEPO1235-VALUE02",  # valor total
        )
        result["liberado"] = fields.get("MEPO1232-STATUS02")
        result["valor_total"] = parse_sap_float(fields.get("txtMEPO1235-VALUE02"))

        # aba Textos
        tabs.select("Textos")
        texto_explorer = tabs.current_explorer()
        texto_node = texto_explorer.find_first(
            id_contains="cntlTEXT_EDITOR_0101/shellcont/shell"
        )
        result["texto_breve"] = (
            getattr(texto_node, "Text", None) if texto_node else None
        )

        # aba Dados do cliente → sub-TabStrip → aba TLC
        tabs.select("Dados do cliente")
        tlc_tabs = TabStrip.from_path(self.session, ids["tlc_tab"])
        if tlc_tabs.exists("TLC"):
            tlc_tabs.select("TLC")
            tlc_node = tlc_tabs.current_explorer().find_first(
                id_contains="txtEKKO_CI-ZZTPCOD_TLC"
            )
            result["tlc"] = getattr(tlc_node, "Text", None) if tlc_node else None
        else:
            result["tlc"] = None

        return result

    # ------------------------------------------------------------------
    # TABELA DE ITENS
    # ------------------------------------------------------------------

    @property
    def items_table(self) -> TableControl:
        """TableControl da tabela de itens — usa prefixo dinâmico."""
        prefix = self._resolve_prefix()
        ids = self._build_ids(prefix)
        return TableControl(
            self.session,
            ids["tabela"],
            column_validator=validate_by_count,
        )

    def read_items(self) -> list:
        """Lê todos os itens da tabela e retorna lista de ItemPedido."""
        return parse_me23n_items(self.items_table.to_list())

    # ------------------------------------------------------------------
    # DETALHES DOS ITENS
    # ------------------------------------------------------------------

    def select_item(self, index: int):
        """Seleciona um item na tabela para abrir seus detalhes."""
        self.items_table.select_row(index)

    @property
    def item_tabs(self) -> TabStrip:
        """TabStrip dos detalhes do item — ID varia conforme item selecionado."""
        return TabStrip.from_explorer(self.explorer, id_contains="tabsITEM_DETAIL")

    def item_has_history(self) -> bool:
        """True se o item selecionado tiver aba 'Histórico' (foi pago)."""
        return self.item_tabs.exists("Histórico")
