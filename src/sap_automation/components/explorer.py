import logging


class SAPExplorer:
    """
    Utilitário para exploração dinâmica da árvore de objetos SAP GUI.

    Percorre recursivamente a hierarquia de componentes a partir de um nó raiz,
    permitindo localizar elementos sem depender de IDs absolutos — que na ME23N
    variam conforme o estado da tela (aba ativa, seção expandida, item selecionado).

    Uso típico
    ----------
    # Escopo amplo — janela inteira (lento em telas complexas)
    explorer = SAPExplorer(session.find("wnd[0]/usr"))

    # Escopo limitado — apenas uma aba (muito mais rápido)
    explorer = tabs.current_explorer()
    campo = explorer.find_first(id_contains="MEPO1232-STATUS02")

    Performance
    -----------
    Cada chamada a find_first() ou find_descendants() percorre todos os nós
    descendentes via COM. Em telas complexas como ME23N, isso pode custar 2-3s.

    Regra: sempre use o menor escopo possível.
    - Prefira SAPExplorer(session.find(id_fixo)) quando o ID do container é estável.
    - Prefira tabs.current_explorer() após select() para limitar ao conteúdo da aba.
    - Reserve o explorer de wnd[0]/usr apenas quando o ID não é conhecido.
    """

    def __init__(self, root):
        """
        Parâmetros
        ----------
        root : objeto SAP GUI
            Nó raiz a partir do qual as buscas serão feitas.
            Pode ser qualquer objeto da árvore: wnd[0]/usr, um GuiTab, um container.
        """
        self.root = root

    # ------------------------------------------------------------------
    # WALK RECURSIVO
    # ------------------------------------------------------------------

    def walk(self, node=None):
        """
        Gerador que percorre todos os nós descendentes em pré-ordem (DFS).

        Parâmetros
        ----------
        node : objeto SAP GUI, opcional
            Nó inicial. Se omitido, usa self.root.

        Yields
        ------
        Cada nó da árvore, incluindo o nó raiz.
        """
        node = node or self.root
        yield node

        try:
            children = node.Children
        except Exception:
            return

        for child in children:
            yield from self.walk(child)

    # ------------------------------------------------------------------
    # BUSCA GENÉRICA
    # ------------------------------------------------------------------

    def find_descendants(
        self,
        *,
        type: str | None = None,
        id_contains: str | None = None,
        text_contains: str | None = None,
    ) -> list:
        """
        Busca todos os nós descendentes que satisfazem os critérios informados.

        Os critérios são combinados com AND — todos os informados devem ser
        satisfeitos para que o nó seja incluído no resultado.

        Parâmetros
        ----------
        type : str, opcional
            Tipo SAP exato do componente.
            Exemplos: "GuiTabStrip", "GuiTextField", "GuiTableControl".

        id_contains : str, opcional
            Trecho que deve estar presente no ID SAP do componente.
            Use a parte estável do ID, ignorando os prefixos dinâmicos (subSUBN).
            Exemplo: "MEPO1232-STATUS02", "tabsHEADER_DETAIL".

        text_contains : str, opcional
            Trecho que deve estar presente no texto do componente (case-insensitive).

        Retorna
        -------
        list
            Lista de objetos SAP GUI que satisfazem os critérios.
            Lista vazia se nenhum for encontrado.
        """
        result = []

        for node in self.walk():
            if type and getattr(node, "Type", "") != type:
                continue
            if id_contains and id_contains not in getattr(node, "Id", ""):
                continue
            if text_contains:
                text = str(getattr(node, "Text", ""))
                if text_contains.lower() not in text.lower():
                    continue
            result.append(node)

        return result

    def find_first(self, **kwargs):
        """
        Retorna o primeiro nó descendente que satisfaz os critérios, ou None.

        Aceita os mesmos parâmetros de find_descendants().

        Retorna
        -------
        objeto SAP GUI ou None
        """
        result = self.find_descendants(**kwargs)
        return result[0] if result else None

    # ------------------------------------------------------------------
    # ESCOPO LIMITADO
    # ------------------------------------------------------------------

    def scoped(self, node) -> "SAPExplorer":
        """
        Cria um novo SAPExplorer com raiz em um nó específico.

        Útil para limitar buscas subsequentes a um sub-container conhecido,
        reduzindo o custo do walk.

        Parâmetros
        ----------
        node : objeto SAP GUI
            Nó que será a raiz do novo explorer.
        """
        return SAPExplorer(node)

    def scoped_at(self, *, id_contains: str) -> "SAPExplorer | None":
        """
        Localiza um nó pelo id_contains e retorna um explorer com raiz nele.

        Atalho para: SAPExplorer(self.find_first(id_contains=id_contains)).
        Retorna None se o nó não for encontrado.

        Parâmetros
        ----------
        id_contains : str
            Trecho do ID do nó que será a nova raiz.
        """
        node = self.find_first(id_contains=id_contains)
        if not node:
            return None
        return SAPExplorer(node)

    # ------------------------------------------------------------------
    # LEITURA DE CAMPOS
    # ------------------------------------------------------------------

    def read_fields(self, *id_suffixes: str) -> dict[str, str | None]:
        """
        Lê o texto de múltiplos campos de uma vez dentro do escopo deste explorer.

        Mais eficiente que chamar find_first() separadamente para cada campo,
        pois faz um único walk e coleta todos os campos encontrados.

        Parâmetros
        ----------
        *id_suffixes : str
            Trechos de ID de cada campo a ser lido.
            Exemplo: "MEPO_TOPLINE-SUPERFIELD", "ctxtMEPO_TOPLINE-BEDAT"

        Retorna
        -------
        dict[str, str | None]
            Dicionário {sufixo: texto_do_campo}.
            Campos não encontrados terão valor None.
        """
        remaining = set(id_suffixes)
        result = {s: None for s in id_suffixes}

        for node in self.walk():
            if not remaining:
                break
            node_id = getattr(node, "Id", "")
            for suffix in list(remaining):
                if suffix in node_id:
                    result[suffix] = getattr(node, "Text", None)
                    remaining.discard(suffix)

        return result

    # ------------------------------------------------------------------
    # BUSCA POR ÍCONE
    # ------------------------------------------------------------------

    def find_by_icon(self, icon_name: str) -> list:
        """
        Localiza todos os nós com um ícone específico.

        Parâmetros
        ----------
        icon_name : str
            Nome do ícone SAP. Exemplos: "DAAREX", "DAARSO", "S_B_OKAY".
        """
        return [
            node for node in self.walk() if getattr(node, "IconName", "") == icon_name
        ]

    # ------------------------------------------------------------------
    # SEÇÕES EXPANSÍVEIS
    # ------------------------------------------------------------------

    def find_collapsible_sections(self) -> list:
        """
        Localiza containers com estrutura de seção expansível (padrão EnjoySAP).

        Uma seção expansível tem a seguinte estrutura interna:

            GuiSimpleContainer
            ├── GuiSimpleContainer
            │     └── GuiButton  ← ícone DAAREX (recolhida) ou DAARSO (expandida)
            └── GuiSimpleContainer
                  └── conteúdo real

        Retorna os containers na ordem em que aparecem na árvore (top-down).
        Use o índice para acessar seções específicas quando o layout é conhecido.

        Retorna
        -------
        list
            Lista de containers GuiSimpleContainer de seções expansíveis.
        """
        logger = logging.getLogger("sap.components.explorer")
        result = []

        for node in self.walk():
            try:
                children = node.Children
            except Exception:
                continue

            if children.Count != 2:
                continue

            try:
                button = children.ElementAt(0).Children.ElementAt(0)
                icon = getattr(button, "IconName", "")

                if icon in ("DAAREX", "DAARSO"):
                    logger.debug(
                        f"Seção encontrada [{len(result)}] "
                        f"icon={icon!r} id={getattr(node, 'Id', '?')!r}"
                    )
                    result.append(node)
            except Exception:
                continue

        logger.debug(f"Total de seções encontradas: {len(result)}")
        return result

    # ------------------------------------------------------------------
    # DEBUG
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """
        Retorna um dicionário leve com informações sobre o nó raiz.

        Seguro para usar como Watch Expression no VSCode — não gera output
        no console e não invalida iterações de loop.

        Retorna
        -------
        dict com as chaves:
            root_type       : tipo SAP do nó raiz
            root_id         : ID SAP do nó raiz
            root_text       : primeiros 60 caracteres do texto do nó raiz
            children_count  : número de filhos diretos (-1 se inacessível)
        """
        try:
            children_count = self.root.Children.Count
        except Exception:
            children_count = -1

        return {
            "root_type": getattr(self.root, "Type", "?"),
            "root_id": getattr(self.root, "Id", "?"),
            "root_text": str(getattr(self.root, "Text", ""))[:60],
            "children_count": children_count,
        }

    def dump(self):
        """
        Imprime a árvore SAP recursivamente a partir da raiz.
        Útil para exploração manual — use com moderação em telas complexas.
        """
        self._dump_node(self.root)

    def _dump_node(self, node, level: int = 0):
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
            self._dump_node(child, level + 1)
