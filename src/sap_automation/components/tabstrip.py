import logging


class TabStrip:
    """
    Wrapper sobre GuiTabStrip com três modos de construção.

    O modo correto depende do conhecimento prévio sobre os IDs do TabStrip:

    Modo 1 — from_path (IDs estáveis, sem tab_map)
    -----------------------------------------------
    Use quando o ID do TabStrip é fixo e as abas são acessadas por nome
    percorrendo os children. Adequado para ML81N, ML84.

        tabs = TabStrip.from_path(session, "wnd[0]/usr/tabsTAB_HEADER")

    Modo 2 — from_path_with_map (IDs estáveis + sufixos de aba conhecidos)
    -----------------------------------------------------------------------
    Use quando o ID do TabStrip é fixo E os sufixos de ID das abas são conhecidos.
    Todas as operações usam session.find() direto — zero walk, máxima performance.
    Adequado para ME23N após mapeamento via SAP Tracker.

        tabs = TabStrip.from_path_with_map(
            session,
            "wnd[0]/usr/.../tabsHEADER_DETAIL",
            tab_map={
                "Status":  "TABHDT10",
                "Textos":  "TABHDT3",
            }
        )

    Modo 3 — from_explorer (IDs dinâmicos, sufixos desconhecidos)
    --------------------------------------------------------------
    Use como fallback quando o ID do TabStrip muda entre rerenderizações
    e os sufixos das abas não são conhecidos. Relocaliza via walk a cada acesso.
    Mais lento — use apenas quando os modos anteriores não são aplicáveis.

        tabs = TabStrip.from_explorer(explorer, id_contains="tabsTABSTRIP_0101")

    Construtor legado
    -----------------
    TabStrip(session, path) é mantido para compatibilidade com ML81N.
    Equivalente a from_path(session, path).

    Performance
    -----------
    Os modos 1 e 2 usam session.find() — O(1), ~0ms.
    O modo 3 usa walk recursivo — O(n), ~2-3s em telas complexas.

    Evitando com_error após rerenderização
    ---------------------------------------
    Após select() de uma aba, o SAP pode rerenderizar e invalidar objetos
    COM capturados anteriormente. Por isso:
    - Nunca guarde o retorno de current_object entre operações de navegação.
    - Sempre chame current_explorer() APÓS o select(), não antes.
    """

    def __init__(self, session, path: str):
        """
        Construtor legado — mantido para compatibilidade com ML81N.
        Equivalente a TabStrip.from_path(session, path).
        """
        self._session = session
        self._path = path
        self._mode = "fixed"
        self._tab_map = {}
        self.logger = logging.getLogger("sap.components.tabstrip")

    # ------------------------------------------------------------------
    # CONSTRUTORES
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, session, path: str) -> "TabStrip":
        """
        Modo 1: ID do TabStrip fixo, acesso às abas via children.

        Parâmetros
        ----------
        session : SAPSession
        path    : str — ID completo do GuiTabStrip (ex: "wnd[0]/usr/tabsTAB_HEADER")
        """
        instance = cls.__new__(cls)
        instance._session = session
        instance._path = path
        instance._mode = "fixed"
        instance._tab_map = {}
        instance.logger = logging.getLogger("sap.components.tabstrip")
        return instance

    @classmethod
    def from_path_with_map(
        cls,
        session,
        path: str,
        *,
        tab_map: dict[str, str],
    ) -> "TabStrip":
        """
        Modo 2: ID do TabStrip fixo + sufixos de aba conhecidos.

        Todas as operações (select, exists, current_explorer) usam
        session.find() diretamente — sem walk algum.

        Parâmetros
        ----------
        session : SAPSession
        path    : str — ID completo do GuiTabStrip
        tab_map : dict[str, str]
            Mapeamento {nome_da_aba: sufixo_do_id}.
            O sufixo é a parte após "tabp" no ID completo da aba.
            Exemplo: .../tabsHEADER_DETAIL/tabpTABHDT10 → sufixo = "TABHDT10"

            Abas fora do mapa ainda funcionam — são acessadas via children
            como fallback.

        Como descobrir os sufixos
        -------------------------
        No SAP Tracker, selecione cada aba e observe o ID completo.
        A parte após o ID do TabStrip + "/tabp" é o sufixo.
        """
        instance = cls.__new__(cls)
        instance._session = session
        instance._path = path
        instance._mode = "cached"
        instance._tab_map = {k.lower(): v for k, v in tab_map.items()}
        instance.logger = logging.getLogger("sap.components.tabstrip")
        return instance

    @classmethod
    def from_explorer(
        cls,
        explorer,
        *,
        id_contains: str | None = None,
    ) -> "TabStrip":
        """
        Modo 3: localização dinâmica via SAPExplorer (fallback).

        Relocaliza o GuiTabStrip via walk a cada acesso.
        Use apenas quando o ID do TabStrip não é estável ou conhecido.

        Parâmetros
        ----------
        explorer    : SAPExplorer — escopo de busca
        id_contains : str — trecho estável do ID do GuiTabStrip
        """
        instance = cls.__new__(cls)
        instance._explorer = explorer
        instance._id_contains = id_contains
        instance._mode = "explorer"
        instance._tab_map = {}
        instance.logger = logging.getLogger("sap.components.tabstrip")
        return instance

    @classmethod
    def from_explorer_cached(
        cls,
        session,
        explorer,
        *,
        id_contains: str,
        tab_map: dict[str, str],
    ) -> "TabStrip":
        """
        Localiza o GuiTabStrip UMA VEZ via explorer e converte para modo cached.

        Útil quando o ID do TabStrip não é conhecido de antemão mas é estável
        após ser descoberto. Após a localização inicial, comporta-se como
        from_path_with_map — sem walk nas operações subsequentes.

        Parâmetros
        ----------
        session     : SAPSession
        explorer    : SAPExplorer — usado apenas para a localização inicial
        id_contains : str — trecho estável do ID do GuiTabStrip
        tab_map     : dict[str, str] — mapeamento {nome_da_aba: sufixo}
        """
        node = explorer.find_first(type="GuiTabStrip", id_contains=id_contains)
        if not node:
            raise RuntimeError(
                f"GuiTabStrip não encontrado (id_contains={id_contains!r})"
            )

        instance = cls.__new__(cls)
        instance._session = session
        instance._path = node.Id
        instance._mode = "cached"
        instance._tab_map = {k.lower(): v for k, v in tab_map.items()}
        instance.logger = logging.getLogger("sap.components.tabstrip")
        instance.logger.debug(f"TabStrip localizado e cacheado: {node.Id}")
        return instance

    # ------------------------------------------------------------------
    # ACESSO AO OBJETO SAP
    # ------------------------------------------------------------------

    @property
    def _tabstrip(self):
        """
        Retorna o objeto GuiTabStrip do SAP.

        fixed/cached → session.find(path)     — O(1)
        explorer     → walk recursivo          — O(n)
        """
        if self._mode in ("fixed", "cached"):
            return self._session.find(self._path)
        else:
            node = self._explorer.find_first(
                type="GuiTabStrip",
                id_contains=self._id_contains,
            )
            if not node:
                raise RuntimeError(
                    "GuiTabStrip não encontrado"
                    + (
                        f" (id_contains={self._id_contains!r})"
                        if self._id_contains
                        else ""
                    )
                )
            return node

    def _tab_path(self, name: str) -> str | None:
        """
        Retorna o ID completo de uma aba pelo nome usando o tab_map.
        Retorna None se o nome não estiver mapeado.
        """
        suffix = self._tab_map.get(name.lower())
        if not suffix:
            return None
        return f"{self._path}/tabp{suffix}"

    # ------------------------------------------------------------------
    # TABS
    # ------------------------------------------------------------------

    @property
    def tabs(self) -> list[dict]:
        """
        Retorna lista de dicionários descrevendo cada aba disponível.

        Cada item contém:
            id       : str  — ID SAP completo da aba
            name     : str  — texto exibido na aba
            selected : bool — True se for a aba atualmente selecionada
            object   : obj  — objeto GuiTab SAP
        """
        tabstrip = self._tabstrip
        selected_tab = tabstrip.SelectedTab

        result = []
        for tab in tabstrip.Children:
            try:
                result.append(
                    {
                        "id": tab.Id,
                        "name": tab.Text.strip(),
                        "selected": tab.Id == selected_tab.Id,
                        "object": tab,
                    }
                )
            except Exception:
                continue
        return result

    @property
    def names(self) -> list[str]:
        """Lista com os nomes de todas as abas disponíveis."""
        return [tab["name"] for tab in self.tabs]

    # ------------------------------------------------------------------
    # ABA ATUAL
    # ------------------------------------------------------------------

    @property
    def current(self) -> str | None:
        """Nome da aba atualmente selecionada, ou None em caso de erro."""
        try:
            return self._tabstrip.SelectedTab.Text.strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # EXISTÊNCIA
    # ------------------------------------------------------------------

    def exists(self, name: str, *, case_sensitive: bool = False) -> bool:
        """
        Verifica se uma aba existe pelo nome.

        No modo cached, consulta o tab_map antes de acessar o SAP —
        custo zero se o nome estiver mapeado.
        """
        if self._tab_map:
            key = name if case_sensitive else name.lower()
            if key in self._tab_map:
                return True

        names = self.names
        if case_sensitive:
            return name in names
        return name.lower() in [n.lower() for n in names]

    # ------------------------------------------------------------------
    # SELECT
    # ------------------------------------------------------------------

    def select(self, name: str, *, case_sensitive: bool = False):
        """
        Seleciona uma aba pelo nome.

        Comportamento
        -------------
        1. Se a aba já estiver selecionada, retorna imediatamente (evita rerender).
        2. No modo cached, se o nome estiver no tab_map, usa session.find() direto.
        3. Caso contrário, percorre children como fallback.

        Parâmetros
        ----------
        name           : str  — nome da aba conforme exibido na tela
        case_sensitive : bool — padrão False

        Lança
        -----
        ValueError se a aba não for encontrada.
        """
        current = self.current
        if current:
            match = (
                current == name if case_sensitive else current.lower() == name.lower()
            )
            if match:
                return

        if self._mode == "cached":
            path = self._tab_path(name)
            if path:
                self.logger.debug(f"Selecionando aba '{name}' via ID direto")
                self._session.find(path).select()
                return

        for tab in self.tabs:
            tab_name = tab["name"]
            match = (
                tab_name == name if case_sensitive else tab_name.lower() == name.lower()
            )
            if match:
                self.logger.debug(f"Selecionando aba '{tab_name}' via children")
                tab["object"].select()
                return

        raise ValueError(f"Aba não encontrada: {name!r}. Disponíveis: {self.names}")

    def select_if_exists(self, name: str) -> bool:
        """
        Seleciona a aba apenas se ela existir.

        Retorna
        -------
        bool — True se a aba foi selecionada, False se não existia.
        """
        if not self.exists(name):
            return False
        self.select(name)
        return True

    # ------------------------------------------------------------------
    # EXPLORER CONTEXTUAL
    # ------------------------------------------------------------------

    def current_explorer(self):
        """
        Retorna um SAPExplorer com raiz na aba atualmente selecionada.

        Sempre obtém o SelectedTab diretamente do GuiTabStrip fresco —
        nunca usa objetos capturados antes do último select(), que podem
        ter sido invalidados pela rerenderização do SAP.

        Uso correto
        -----------
            tabs.select("Status")
            explorer = tabs.current_explorer()   # APÓS o select
            campo = explorer.find_first(id_contains="MEPO1232-STATUS02")

        Erro comum (com_error -2147417851)
        -----------------------------------
            explorer = tabs.current_explorer()   # capturado ANTES
            tabs.select("Status")                # SAP rerenderiza
            campo = explorer.find_first(...)     # objeto stale → erro
        """
        from sap_automation.components.explorer import SAPExplorer

        try:
            selected = self._tabstrip.SelectedTab
        except Exception as e:
            raise RuntimeError(f"Não foi possível obter a aba selecionada: {e}")

        if not selected:
            raise RuntimeError("Nenhuma aba selecionada.")

        return SAPExplorer(selected)

    def explorer_for(self, name: str):
        """
        Atalho: seleciona a aba e retorna o explorer dela em uma chamada.

        Equivalente a:
            tabs.select(name)
            return tabs.current_explorer()
        """
        self.select(name)
        return self.current_explorer()

    # ------------------------------------------------------------------
    # DEBUG
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """
        Retorna um dicionário leve com o estado atual do TabStrip.

        Seguro para Watch Expression no VSCode — não gera output no console
        e não invalida iterações de loop.

        Retorna
        -------
        dict com as chaves:
            mode     : str       — "fixed", "cached" ou "explorer"
            path     : str|None  — ID do TabStrip (modos fixed/cached)
            current  : str|None  — nome da aba selecionada
            tabs     : list[str] — nomes de todas as abas
            count    : int       — número de abas
            tab_map  : dict      — mapeamento name→sufixo configurado
        """
        try:
            current = self.current
            tab_names = self.names
        except Exception as e:
            return {"error": str(e), "mode": self._mode}

        return {
            "mode": self._mode,
            "path": getattr(self, "_path", None),
            "current": current,
            "tabs": tab_names,
            "count": len(tab_names),
            "tab_map": dict(self._tab_map),
        }

    def dump(self):
        """Imprime as abas disponíveis marcando a selecionada com ✓."""
        current = self.current
        for name in self.names:
            marker = "✓" if name == current else " "
            print(f"[{marker}] {name}")

    def __repr__(self):
        return f"TabStrip(mode={self._mode!r}, current={self.current!r})"
