class SAPExplorer:
    """
    Utilitário para exploração dinâmica da árvore SAP GUI.

    Permite:
    - percorrer hierarquia
    - localizar componentes dinamicamente
    - evitar dependência de IDs absolutos frágeis
    """

    def __init__(self, root):
        self.root = root

    # ----------------------------------
    # WALK RECURSIVO
    # ----------------------------------
    def walk(self, node=None):
        node = node or self.root

        yield node

        try:
            children = node.Children
        except Exception:
            return

        for child in children:
            yield from self.walk(child)

    # ----------------------------------
    # BUSCA GENÉRICA
    # ----------------------------------
    def find_descendants(
        self,
        *,
        type=None,
        id_contains=None,
        text_contains=None,
    ):
        """
        Busca componentes descendentes dinamicamente.

        Parâmetros:
            type:
                Tipo SAP (GuiTableControl, GuiTabStrip...)

            id_contains:
                Trecho presente no ID SAP.

            text_contains:
                Trecho presente no Text.
        """

        result = []

        for node in self.walk():
            # tipo
            if type:
                if getattr(node, "Type", "") != type:
                    continue

            # trecho do ID
            if id_contains:
                node_id = getattr(node, "Id", "")

                if id_contains not in node_id:
                    continue

            # texto
            if text_contains:
                text = str(getattr(node, "Text", ""))

                if text_contains.lower() not in text.lower():
                    continue

            result.append(node)

        return result

    # ----------------------------------
    # PRIMEIRO RESULTADO
    # ----------------------------------
    def find_first(self, **kwargs):
        result = self.find_descendants(**kwargs)

        if not result:
            return None

        return result[0]

    # -------------------
    def find_by_icon(self, icon_name: str):
        result = []

        for node in self.walk():
            if getattr(node, "IconName", "") == icon_name:
                result.append(node)

        return result

    # -------------------
    def find_collapsible_sections(self):
        """
        Localiza containers com estrutura:

            container
            ├── botão expand/collapse
            └── conteúdo

        Detecta pelo IconName:
            DAAREX
            DAARSO
        """
        result = []

        for node in self.walk():
            try:
                children = node.Children
            except Exception:
                continue

            if children.Count != 2:
                continue

            try:
                # button = children.ElementAt(0)
                button = children.ElementAt(0).children.ElementAt(0)

                icon = getattr(button, "IconName", "")

                if icon in ("DAAREX", "DAARSO"):
                    result.append(node)

            except Exception:
                continue

        return result

    # -------------------
    def dump(self):
        """
        Imprime a árvore SAP recursivamente.
        """

        self._dump_node(self.root)

    # -------------------
    def _dump_node(
        self,
        node,
        level=0,
    ):
        indent = "  " * level

        node_type = getattr(node, "Type", "")

        node_id = getattr(node, "Id", "")

        text = getattr(node, "Text", "")

        print(f"{indent}{node_type} | {node_id} | {text}")

        try:
            children = node.Children
        except Exception:
            return

        for child in children:
            self._dump_node(
                child,
                level + 1,
            )
