import logging

from sap_automation.components.explorer import SAPExplorer


class Section:
    """
    Representa uma seção expansível/colapsável no padrão EnjoySAP.

    Seções são containers que podem ser recolhidos pelo usuário para organizar
    a tela. São identificadas por um botão com ícone DAAREX (recolhida) ou
    DAARSO (expandida).

    Estrutura interna observada no SAP GUI
    ---------------------------------------
    GuiSimpleContainer               ← container (passado para Section())
    ├── GuiSimpleContainer
    │     └── GuiButton              ← botão expand/collapse (self.button)
    │           IconName: DAAREX     ← seção recolhida
    │           IconName: DAARSO     ← seção expandida
    └── GuiSimpleContainer
          └── <conteúdo real>        ← self.content (só acessível quando expandida)

    Uso típico
    ----------
    # Acesso por ID fixo (preferido quando o ID é estável)
    section = Section(session.find("wnd[0]/usr/.../subSUB1:SAPLMEVIEWS:4000"))
    section.expand()

    # Acesso via explorer (quando o ID não é conhecido)
    containers = explorer.find_collapsible_sections()
    section = Section(containers[0])
    section.expand()

    Limitação importante — ME23N
    ----------------------------
    A ME23N permite no máximo 2 seções expandidas simultaneamente.
    Ao expandir uma terceira, o SAP recolhe automaticamente uma das anteriores.
    Nunca tente expandir todas de uma vez.
    """

    ICON_EXPANDED = "DAARSO"
    ICON_COLLAPSED = "DAAREX"

    def __init__(self, container):
        """
        Parâmetros
        ----------
        container : objeto SAP GUI (GuiSimpleContainer)
            O container pai da seção, conforme retornado por
            SAPExplorer.find_collapsible_sections() ou session.find(id).
        """
        self.container = container
        self.logger = logging.getLogger("sap.components.section")

    # ------------------------------------------------------------------
    # COMPONENTES INTERNOS
    # ------------------------------------------------------------------

    @property
    def button(self):
        """
        GuiButton que controla o estado expand/collapse da seção.

        Localização na árvore:
            container.Children[0].Children[0]
        """
        return self.container.Children.ElementAt(0).Children.ElementAt(0)

    @property
    def content(self):
        """
        Conteúdo real da seção (TabStrip, tabela, campos, etc).

        Localização na árvore:
            container.Children[1].Children[0]

        Atenção: só existe na árvore SAP quando a seção está expandida.
        Acessar quando recolhida lança com_error.
        """
        return self.container.Children.ElementAt(1).Children.ElementAt(0)

    @property
    def explorer(self) -> SAPExplorer:
        """
        SAPExplorer com raiz no conteúdo desta seção.

        Use para buscar componentes dentro da seção após expandi-la.
        Acessar quando recolhida lança com_error.
        """
        return SAPExplorer(self.content)

    # ------------------------------------------------------------------
    # ESTADO
    # ------------------------------------------------------------------

    @property
    def icon_name(self) -> str:
        """IconName atual do botão. Retorna string vazia em caso de erro."""
        try:
            return getattr(self.button, "IconName", "")
        except Exception:
            return ""

    @property
    def is_expanded(self) -> bool:
        """True se a seção estiver expandida (ícone DAARSO)."""
        return self.icon_name == self.ICON_EXPANDED

    @property
    def is_collapsed(self) -> bool:
        """True se a seção estiver recolhida (ícone DAAREX)."""
        return self.icon_name == self.ICON_COLLAPSED

    # ------------------------------------------------------------------
    # COMPORTAMENTO
    # ------------------------------------------------------------------

    def expand(self):
        """
        Expande a seção se estiver recolhida.
        No-op se já estiver expandida — evita rerenderização desnecessária.
        """
        if self.is_collapsed:
            self.logger.debug("Expandindo seção")
            self.button.press()

    def collapse(self):
        """
        Recolhe a seção se estiver expandida.
        No-op se já estiver recolhida — evita rerenderização desnecessária.
        """
        if self.is_expanded:
            self.logger.debug("Recolhendo seção")
            self.button.press()

    def toggle(self):
        """Alterna o estado da seção sem verificar o estado atual."""
        self.button.press()

    # ------------------------------------------------------------------
    # DEBUG
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """
        Retorna um dicionário leve com o estado atual da seção.

        Seguro para usar como Watch Expression no VSCode — não gera output
        no console e não invalida iterações de loop.

        Exemplo de uso no VSCode:
            # Watch Expression:
            section.info()
            [s.info() for s in screen.sections]

        Retorna
        -------
        dict com as chaves:
            expanded        : bool — seção expandida
            collapsed       : bool — seção recolhida
            icon            : str  — IconName do botão ("DAARSO", "DAAREX" ou "?")
            button_id       : str  — ID SAP do botão
            container_id    : str  — ID SAP do container pai
            container_type  : str  — tipo SAP do container pai
            children_count  : int  — número de filhos do container (-1 se erro)
            error           : str | None — mensagem de erro, se houver
        """
        result = {
            "expanded": False,
            "collapsed": False,
            "icon": "?",
            "button_id": "?",
            "container_id": "?",
            "container_type": "?",
            "children_count": -1,
            "error": None,
        }

        try:
            result["container_id"] = getattr(self.container, "Id", "?")
            result["container_type"] = getattr(self.container, "Type", "?")
            result["children_count"] = self.container.Children.Count
        except Exception as e:
            result["error"] = f"container inválido: {e}"
            return result

        try:
            result["icon"] = self.icon_name
            result["button_id"] = getattr(self.button, "Id", "?")
            result["expanded"] = self.is_expanded
            result["collapsed"] = self.is_collapsed
        except Exception as e:
            result["error"] = f"botão inválido: {e}"

        return result

    def dump(self):
        """
        Imprime a árvore interna da seção via SAPExplorer.
        Só funciona quando a seção está expandida.
        """
        self.explorer.dump()
