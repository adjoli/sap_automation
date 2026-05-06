import logging


class TabStrip:
    """
    Wrapper resiliente para GuiTabStrip.

    Não mantém referências persistentes ao objeto SAP,
    evitando problemas de rerenderização/stale objects.

    O componente é redescoberto dinamicamente
    a cada operação através do SAPExplorer.
    """

    def __init__(
        self,
        explorer,
        *,
        id_contains: str | None = None,
    ):
        self.explorer = explorer

        self.id_contains = id_contains

        self.logger = logging.getLogger("sap.components.tabstrip")

    # ----------------------------------
    # TABSTRIP SAP
    # ----------------------------------
    @property
    def tabstrip(self):
        """
        Relocaliza dinamicamente o GuiTabStrip.
        """

        tab = self.explorer.find_first(
            type="GuiTabStrip",
            id_contains=self.id_contains,
        )

        if not tab:
            raise RuntimeError("GuiTabStrip não encontrado")

        return tab

    # ----------------------------------
    # TABS
    # ----------------------------------
    @property
    def tabs(self):
        selected_tab = self.tabstrip.SelectedTab

        result = []

        for tab in self.tabstrip.Children:
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
        """
        Lista nomes das abas.
        """

        return [tab["name"] for tab in self.tabs]

    # ----------------------------------
    # ABA ATUAL
    # ----------------------------------
    @property
    def current(self) -> str | None:
        """
        Retorna nome da aba selecionada.
        """

        for tab in self.tabs:
            if tab["selected"]:
                return tab["name"]

        return None

    # ----------------------------------
    # EXISTÊNCIA
    # ----------------------------------
    def exists(
        self,
        name: str,
        *,
        case_sensitive=False,
    ) -> bool:
        if case_sensitive:
            return name in self.names

        return name.lower() in [n.lower() for n in self.names]

    # ----------------------------------
    # SELECT
    # ----------------------------------
    def select(
        self,
        name: str,
        *,
        case_sensitive=False,
    ):
        """
        Seleciona aba pelo nome.
        """

        current = self.current

        # evita rerender desnecessário
        if current:
            if case_sensitive:
                if current == name:
                    return

            else:
                if current.lower() == name.lower():
                    return

        for tab in self.tabs:
            tab_name = tab["name"]

            match = (
                tab_name == name if case_sensitive else tab_name.lower() == name.lower()
            )

            if match:
                self.logger.debug(f"Selecionando aba '{tab_name}'")

                tab["object"].select()

                return

        raise ValueError(f"Aba não encontrada: {name}")

    # ----------------------------------
    # SELECT IF EXISTS
    # ----------------------------------
    def select_if_exists(
        self,
        name: str,
    ) -> bool:
        """
        Seleciona aba apenas se existir.
        """

        if not self.exists(name):
            return False

        self.select(name)

        return True

    # ----------------------------------
    # DEBUG
    # ----------------------------------
    def dump(self):
        """
        Exibe abas disponíveis.
        """

        current = self.current

        for name in self.names:
            marker = "✓" if name == current else " "

            print(f"[{marker}] {name}")

    # ----------------------------------
    # REPRESENTAÇÃO
    # ----------------------------------
    def __repr__(self):
        return f"{self.__class__.__name__}(current={self.current!r}, tabs={self.names})"
