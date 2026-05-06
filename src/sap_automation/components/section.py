import logging

from sap_automation.components import SAPExplorer


class Section:
    """
    Representa uma section expansível da ME23N/EnjoySAP.

    Estrutura observada:

        GuiSimpleContainer
        ├── botão expand/collapse
        └── conteúdo

    O botão controla o estado visual da section
    através da propriedade IconName.
    """

    ICON_EXPANDED = "DAARSO"
    ICON_COLLAPSED = "DAAREX"

    def __init__(self, container):
        self.container = container

        self.logger = logging.getLogger("sap.components.section")

    # ----------
    @property
    def button(self):
        """
        O componente GuiButton que expande/retrai a seção encontra-se:
          * No PRIMEIRO dos componentes GuiSimpleContainer
          * É o primeiro elemento deste Container
        """
        return self.container.Children.ElementAt(0).Children.ElementAt(0)

    # ----------
    @property
    def content(self):
        """
        O conteúdo da Section encontra-se:
          * No SEGUNDO dos componentes GuiSimpleContainer
          * É o primeiro elemento deste Container
        """
        return self.container.Children.ElementAt(1).Children.ElementAt(0)

    # ----------
    @property
    def explorer(self):
        """
        Explorer contextual da section.
        """
        return SAPExplorer(self.content)

    # ----------------------------------
    # ESTADO
    # ----------------------------------
    @property
    def icon_name(self) -> str:
        return getattr(self.button, "IconName", "")

    @property
    def is_expanded(self):
        return self.icon_name == self.ICON_EXPANDED

    # ----------
    @property
    def is_collapsed(self):
        return self.icon_name == self.ICON_COLLAPSED

    # ----------------------------------
    # COMPORTAMENTO
    # ----------------------------------
    def expand(self):
        if self.is_collapsed:
            self.logger.debug("Expandindo seção")
            self.button.press()

    # ----------
    def collapse(self):
        if self.is_expanded:
            self.logger.debug("Recolhendo seção")
            self.button.press()

    # ----------
    def toggle(self):
        self.button.press()

    # ----------------------------------
    # INSPEÇÃO DE CONTEÚDO
    # ----------------------------------
    def contains_table(self) -> bool:
        """
        Verifica se a section contém GuiTableControl.
        """

        return bool(self.explorer.find_first(type="GuiTableControl"))

    # ----------
    def contains_tabstrip(self) -> bool:
        """
        Verifica se a section contém GuiTabStrip.
        """

        return bool(self.explorer.find_first(type="GuiTabStrip"))

    # ----------------------------------
    # DEBUG
    # ----------------------------------
    def dump(self):
        """
        Dump da árvore interna da section.
        """

        self.explorer.dump()
