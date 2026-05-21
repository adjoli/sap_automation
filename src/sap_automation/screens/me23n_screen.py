import re

from sap_automation.components import Section, TableControl, TabStrip
from sap_automation.components.explorer import SAPExplorer
from sap_automation.components.table import validate_by_count
from sap_automation.core.converters import parse_sap_date, parse_sap_float
from sap_automation.parsers.me23n_parser import parse_me23n_items
from sap_automation.screens.base import Screen

# ─── IDs fixos da ME23N ───────────────────────────────────────────────────────
# Verificados como estáveis entre execuções e pedidos diferentes.
# Obtidos via SAP Tracker com um pedido aberto na ME23N.
# Se uma atualização do SAP alterar esses IDs, basta atualizar as constantes abaixo.

_ID_TOPO = (
    "wnd[0]/usr/subSUB0:SAPLMEGUI:0013/subSUB0:SAPLMEGUI:0030/subSUB1:SAPLMEGUI:1105"
)
"""Container do topo — campos de fornecedor, data e número do pedido."""

_ID_SECAO0 = (
    "wnd[0]/usr"
    "/subSUB0:SAPLMEGUI:0013"
    "/subSUB1:SAPLMEVIEWS:1100"
    "/subSUB1:SAPLMEVIEWS:4000"
)
"""Container da seção [0] — detalhes do cabeçalho (contém o TabStrip de abas)."""

_ID_HEADER_TABS = (
    "wnd[0]/usr"
    "/subSUB0:SAPLMEGUI:0013"
    "/subSUB1:SAPLMEVIEWS:1100"
    "/subSUB2:SAPLMEVIEWS:1200"
    "/subSUB1:SAPLMEGUI:1102"
    "/tabsHEADER_DETAIL"
)
"""TabStrip principal do cabeçalho do pedido."""

_ID_TLC_TAB = (
    "wnd[0]/usr"
    "/subSUB0:SAPLMEGUI:0013"
    "/subSUB1:SAPLMEVIEWS:1100"
    "/subSUB2:SAPLMEVIEWS:1200"
    "/subSUB1:SAPLMEGUI:1102"
    "/tabsHEADER_DETAIL"
    "/tabpTABHDT11"
    "/ssubTABSTRIPCONTROL2SUB:SAPLMEGUI:1227"
    "/ssubCUSTOMER_DATA_HEADER:SAPLXM06:0101"
    "/tabsTABSTRIP_0101"
)
"""TabStrip interno da aba 'Dados do cliente' — contém a aba TLC."""

_ID_TABELA = (
    "wnd[0]/usr"
    "/subSUB0:SAPLMEGUI:0013"
    "/subSUB2:SAPLMEVIEWS:1100"
    "/subSUB2:SAPLMEVIEWS:1200"
    "/subSUB1:SAPLMEGUI:1211"
    "/tblSAPLMEGUITC_1211"
)
"""GuiTableControl da tabela de itens do pedido."""

# ─── Tab map do cabeçalho ─────────────────────────────────────────────────────
# Sufixos descobertos via SAP Tracker — parte após "tabp" no ID completo da aba.
# Exemplo: .../tabsHEADER_DETAIL/tabpTABHDT10 → sufixo = "TABHDT10"
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


def _parse_fornecedor(texto: str | None) -> tuple[str | None, str | None]:
    """
    Separa o texto do campo fornecedor em código e descrição.

    O SAP retorna o fornecedor como "<codigo> <nome>", ex:
        "9000013096 C.HENRIQUE BODEMEIER & CIA LTDA"

    Retorna (cod_fornecedor, desc_fornecedor).
    Se o texto não começar com dígitos, retorna (None, texto).
    Se o texto for vazio ou None, retorna (None, None).
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

    Encapsula toda a lógica de navegação na tela, separando-a da lógica de
    negócio em ME23N.execute(). A Transaction apenas chama os métodos desta
    classe e monta o objeto Pedido com os dados retornados.

    Estratégia de acesso
    --------------------
    Todos os elementos principais são acessados via IDs fixos (session.find),
    eliminando walks recursivos que custariam 2-3s por chamada.

    Os IDs foram verificados como estáveis entre execuções e pedidos.
    O SAPExplorer (walk) é usado apenas onde o ID não é estável —
    atualmente apenas no item_tabs, cujo ID varia conforme o item selecionado.

    Layout da tela
    --------------
    A ME23N tem 4 seções, sendo a primeira fixa (não colapsável):

        [fixa]  Linha do topo     — número do pedido, fornecedor, data
        [0]     Cabeçalho         — TabStrip com abas de dados do pedido
        [1]     Itens             — tabela de itens do pedido
        [2]     Detalhes do item  — TabStrip com abas do item selecionado

    A seção [0] precisa estar expandida antes de acessar o TabStrip do cabeçalho.
    O SAP permite no máximo 2 seções expandidas simultaneamente.

    Abas do cabeçalho
    -----------------
    Mapeadas em _HEADER_TAB_MAP. As abas lidas atualmente são:
        - Status        → campo liberado
        - Textos        → texto breve do pedido
        - Dados do cliente → sub-TabStrip → aba TLC
    """

    # ------------------------------------------------------------------
    # SEÇÕES
    # ------------------------------------------------------------------

    def section(self, index: int) -> Section:
        """
        Acessa uma seção colapsável da ME23N pelo índice (0-based).

        Índices disponíveis:
            [0] Detalhes do cabeçalho — acessada por ID fixo (_ID_SECAO0)
            [1] Itens
            [2] Detalhes do item selecionado

        A seção [0] usa ID fixo para evitar walk. As seções [1] e [2]
        ainda usam find_collapsible_sections() — seus IDs não foram
        verificados. Aplique o mesmo processo de coleta via Tracker
        quando precisar otimizá-las.

        Parâmetros
        ----------
        index : int — índice da seção (0-based)

        Lança
        -----
        IndexError se o índice for inválido.
        """
        if index == 0:
            return Section(self.session.find(_ID_SECAO0))

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
        """
        TabStrip do cabeçalho em modo from_path_with_map.

        Usa _ID_HEADER_TABS (fixo) e _HEADER_TAB_MAP (sufixos conhecidos).
        Todas as operações (select, exists, current_explorer) usam
        session.find() direto — custo ~0ms por operação.

        Pré-condição: seção [0] deve estar expandida.
        """
        return TabStrip.from_path_with_map(
            self.session,
            _ID_HEADER_TABS,
            tab_map=_HEADER_TAB_MAP,
        )

    # ------------------------------------------------------------------
    # LEITURA DO CABEÇALHO
    # ------------------------------------------------------------------

    def read_header(self) -> dict:
        """
        Lê os dados do cabeçalho do pedido navegando pelas abas relevantes.

        Fluxo de navegação
        ------------------
        1. Lê campos do topo (seção fixa — sempre visível)
        2. Expande seção [0] para revelar o TabStrip
        3. Aba Status    → campo liberado
        4. Aba Textos    → texto breve
        5. Aba Dados do cliente → sub-aba TLC

        Retorna
        -------
        dict com as chaves:
            tipo        : str | None  — tipo do documento (ex: "NB", "ZNB")
            fornecedor  : str | None  — código e nome do fornecedor
            data        : date | None — data do documento
            liberado    : str | None  — texto do status de liberação
            valor_total : float | None
            texto_breve : str | None  — texto breve do pedido (aba Textos)
            tlc         : str | None  — tipo de linha de contrato (aba Dados do cliente)
        """
        result = {}

        # ── campos do topo (seção fixa — sempre visível) ──────────────────────
        top_explorer = SAPExplorer(self.session.find(_ID_TOPO))
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

        # ── expande seção [0] para revelar o TabStrip do cabeçalho ───────────
        self.section(0).expand()

        tabs = self.header_tabs

        # ── aba Status ────────────────────────────────────────────────────────
        tabs.select("Status")
        fields = tabs.current_explorer().read_fields(
            "MEPO1232-STATUS02",  # status de liberação (liberado, bloqueado, etc)
            "txtMEPO1235-VALUE02",  # valor total do pedido
        )
        result["liberado"] = fields.get("MEPO1232-STATUS02")
        result["valor_total"] = parse_sap_float(fields.get("txtMEPO1235-VALUE02"))

        # ── aba Textos ────────────────────────────────────────────────────────
        tabs.select("Textos")
        texto_explorer = tabs.current_explorer()
        # texto_node = texto_explorer.find_first(type="GuiTextField")
        texto_node = texto_explorer.find_first(
            id_contains="cntlTEXT_EDITOR_0101/shellcont/shell"
        )
        result["texto_breve"] = (
            getattr(texto_node, "Text", None) if texto_node else None
        )

        # ── aba Dados do cliente → sub-TabStrip → aba TLC ────────────────────
        # tlc_tabs usa _ID_TLC_TAB (fixo) — ID estável mesmo após rerenderização,
        # pois está aninhado dentro de tabpTABHDT11 que já foi selecionado.
        tabs.select("Dados do cliente")
        tlc_tabs = TabStrip.from_path(self.session, _ID_TLC_TAB)
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
        """
        TableControl da tabela de itens do pedido.

        Usa _ID_TABELA (fixo) — acesso direto sem walk.
        O validator validate_by_count é necessário pois a tabela tem
        colunas heterogêneas (nem todas preenchidas em todas as linhas).
        """
        return TableControl(
            self.session,
            _ID_TABELA,
            column_validator=validate_by_count,
        )

    def read_items(self) -> list:
        """
        Lê todos os itens da tabela e retorna lista de ItemPedido.

        Faz scroll automático para capturar itens além da área visível.
        """
        return parse_me23n_items(self.items_table.to_list())

    # ------------------------------------------------------------------
    # DETALHES DOS ITENS
    # ------------------------------------------------------------------

    def select_item(self, index: int):
        """
        Seleciona um item na tabela para abrir seus detalhes na seção [2].

        Parâmetros
        ----------
        index : int — índice do item (0-based)
        """
        self.items_table.select_row(index)

    @property
    def item_tabs(self) -> TabStrip:
        """
        TabStrip dos detalhes do item atualmente selecionado.

        Usa from_explorer (modo dinâmico) pois o ID do TabStrip varia
        conforme o item selecionado. Caso o ID seja verificado como estável,
        migrar para from_path_with_map para melhor performance.

        Pré-condição: um item deve estar selecionado via select_item().
        """
        return TabStrip.from_explorer(self.explorer, id_contains="tabsITEM_DETAIL")

    def item_has_history(self) -> bool:
        """
        Verifica se o item selecionado foi pago.

        A presença da aba 'Histórico' nos detalhes do item indica que
        houve ao menos um pagamento registrado para aquele item.

        Retorna
        -------
        bool — True se a aba 'Histórico' existir, False caso contrário.
        """
        return self.item_tabs.exists("Histórico")
