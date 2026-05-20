"""
Fixtures de sessão SAP para testes unitários.

Conceito: Test Doubles
-----------------------
Um "test double" é qualquer objeto que substitui uma dependência real
durante os testes. Existem vários tipos:

  Stub    — retorna valores fixos, sem verificar como foi chamado
  Spy     — registra chamadas para verificação posterior
  Mock    — combina stub + spy, com expectativas pré-configuradas
  Fake    — implementação simplificada mas funcional da dependência real

O FakeSAPSession é um *Fake*: implementa a mesma interface que SAPSession
mas sem acessar o SAP real. Isso permite testar toda a lógica de negócio
das transações sem o SAP instalado.

Diferença em relação a MagicMock
----------------------------------
MagicMock aceita qualquer chamada e retorna MagicMock por padrão.
O FakeSAPSession é mais restritivo — lança exceção se um elemento não
foi previamente registrado, exatamente como o SAP real faria.
Isso captura erros de caminho incorreto em tempo de teste.

Estrutura
---------
FakeElement       — simula qualquer elemento GUI do SAP (campo, botão, ícone)
FakeTabStrip      — simula GuiTabStrip, registra navegação entre abas
FakeTable         — simula GuiTableControl, retorna linhas configuráveis
FakeSAPSession    — orquestra os elementos, implementa a API de SAPSession
"""


# ─── FakeElement ──────────────────────────────────────────────────────────────
class FakeElement:
    """
    Simula qualquer elemento GUI do SAP (GuiTextField, GuiButton, etc).

    Atributos configuráveis
    -----------------------
    text      : str  — valor retornado por get_text() / Text
    icon_name : str  — valor de IconName (usado em _has_acceptance da ML81N)
    exists    : bool — se False, session.exists() retorna False para este path

    Rastreamento
    ------------
    pressed   : bool — True se press() foi chamado
    selected  : bool — True se select() foi chamado
    closed    : bool — True se close() foi chamado
    set_calls : list — histórico de valores definidos via set_text()
    """

    def __init__(self, text: str = "", icon_name: str = "", exists: bool = True):
        self.Text = text
        self.IconName = icon_name
        self.exists = exists

        # rastreamento de chamadas
        self.pressed = False
        self.selected = False
        self.closed = False
        self.set_calls: list[str] = []

    # propriedade text como alias de Text para compatibilidade
    @property
    def text(self) -> str:
        return self.Text

    @text.setter
    def text(self, value: str):
        self.Text = value
        self.set_calls.append(value)

    def press(self):
        self.pressed = True

    def select(self):
        self.selected = True

    def close(self):
        self.closed = True

    def __repr__(self):
        return f"FakeElement(text={self.Text!r}, icon={self.IconName!r})"


# ─── FakeTabStrip ─────────────────────────────────────────────────────────────
class FakeTabStrip:
    """
    Simula GuiTabStrip — registra quais abas foram selecionadas.

    Permite verificar se a transação navegou pelas abas corretas
    e na ordem correta durante os testes.

    Uso
    ---
        tabstrip = FakeTabStrip(["DdsBásicos", "Vals.", "Dados adic."])
        session.add_tabstrip("wnd[0]/usr/tabsTAB_HEADER", tabstrip)

        # após rodar a transação:
        assert tabstrip.history == ["DdsBásicos", "Vals.", "Dados adic."]
        assert tabstrip.current == "Dados adic."
    """

    def __init__(self, tabs: list[str]):
        """
        Parâmetros
        ----------
        tabs : list[str] — nomes das abas disponíveis neste TabStrip
        """
        self._tabs = tabs
        self._current: str | None = tabs[0] if tabs else None
        self.history: list[str] = []

    @property
    def current(self) -> str | None:
        """Nome da aba atualmente selecionada."""
        return self._current

    @property
    def names(self) -> list[str]:
        """Nomes de todas as abas disponíveis."""
        return list(self._tabs)

    def select(self, name: str):
        """
        Simula a seleção de uma aba.
        Lança ValueError se a aba não existir — igual ao TabStrip real.
        """
        if name not in self._tabs:
            raise ValueError(f"Aba não encontrada: {name!r}. Disponíveis: {self._tabs}")
        self._current = name
        self.history.append(name)

    def was_selected(self, name: str) -> bool:
        """Retorna True se a aba foi selecionada ao menos uma vez."""
        return name in self.history

    def __repr__(self):
        return f"FakeTabStrip(current={self._current!r}, tabs={self._tabs})"


# ─── FakeTabElement ────────────────────────────────────────────────────────────
class FakeTabElement(FakeElement):
    """
    Simula uma aba (GuiTab) dentro de um GuiTabStrip.

    Quando .select() é chamado, além de marcar o elemento como selecionado,
    também delega ao FakeTabStrip correspondente — permitindo que os testes
    verifiquem a navegação entre abas via tabstrip.was_selected().
    """

    def __init__(self, tabstrip: "FakeTabStrip", tab_name: str):
        super().__init__()
        self._fake_tabstrip = tabstrip
        self._tab_name = tab_name

    def select(self):
        super().select()
        self._fake_tabstrip.select(self._tab_name)

    def __repr__(self):
        return (
            f"FakeTabElement(tab_name={self._tab_name!r}, "
            f"tabstrip.current={self._fake_tabstrip.current!r})"
        )


# ─── FakeScrollbar ────────────────────────────────────────────────────────────
class FakeScrollbar:
    """Simula GuiScrollbar do SAP."""

    def __init__(self, range_val: int = 0, position: int = 0):
        self.Range = range_val
        self.Position = position


# ─── FakeTableColumn ──────────────────────────────────────────────────────────
class FakeTableColumn:
    """Simula GuiTableColumn do SAP."""

    def __init__(self, title: str, count: int):
        self.Title = title
        self.Count = count


# ─── FakeTableCell ────────────────────────────────────────────────────────────
class FakeTableCell:
    """Simula o retorno de GetCell do GuiTableControl SAP."""

    def __init__(self, text: str = "", is_checkbox: bool = False, selected: bool = False):
        self.Type = "GuiCheckBox" if is_checkbox else "GuiTextField"
        self.Text = text
        self.Selected = selected


# ─── FakeTableColumns ─────────────────────────────────────────────────────────
class FakeTableColumns:
    """Simula a coleção de colunas (Columns) de GuiTableControl."""

    def __init__(self, column_names: list[str], total_rows: int):
        self._names = column_names
        self._total_rows = total_rows

    @property
    def Count(self) -> int:
        return len(self._names)

    def ElementAt(self, index: int) -> FakeTableColumn:
        return FakeTableColumn(
            title=self._names[index] if index < len(self._names) else f"col_{index}",
            count=self._total_rows,
        )


# ─── FakeTable ────────────────────────────────────────────────────────────────
class FakeTable:
    """
    Simula GuiTableControl — retorna linhas configuráveis.

    Permite testar lógica que depende do conteúdo de tabelas SAP
    sem precisar do SAP real. Implementa atributos e métodos que
    TableControl (components/table.py) espera de um GuiTableControl:
    VisibleRowCount, VerticalScrollbar, HorizontalScrollbar, Columns, GetCell.

    Uso
    ---
        tabela = FakeTable([
            {"Sel.": "X", "Chave": "12345", "Nome": "João Silva"},
            {"Sel.": "",  "Chave": "67890", "Nome": "Maria Santos"},
        ])
        session.add_table("wnd[1]/usr/tblSAPLZGFMMTC_FISCAIS", tabela)
    """

    def __init__(self, rows: list[dict]):
        """
        Parâmetros
        ----------
        rows : list[dict] — linhas da tabela, cada uma como {coluna: valor}
        """
        self._rows = rows
        self.accessed = False

        # Interface compatível com GuiTableControl do SAP
        self.VisibleRowCount = len(rows)
        self.VerticalScrollbar = FakeScrollbar(range_val=max(0, len(rows) - 1))
        self.HorizontalScrollbar = FakeScrollbar(range_val=0)
        self._column_names = list(rows[0].keys()) if rows else []
        self.Columns = FakeTableColumns(self._column_names, len(rows))

    def GetCell(self, row: int, col_index: int) -> FakeTableCell:
        """Simula GetCell(row, col) do GuiTableControl SAP."""
        if row >= len(self._rows) or col_index >= len(self._column_names):
            return FakeTableCell()

        col_name = self._column_names[col_index]
        value = self._rows[row].get(col_name, "")

        if col_name == "Sel.":
            return FakeTableCell(is_checkbox=True, selected=(value == "X"))

        return FakeTableCell(text=str(value) if value is not None else "")

    def to_list(self) -> list[dict]:
        """Retorna as linhas configuradas. Registra que a tabela foi acessada."""
        self.accessed = True
        return list(self._rows)

    def __repr__(self):
        return f"FakeTable(rows={len(self._rows)})"


# ─── FakeSAPSession ───────────────────────────────────────────────────────────
class FakeSAPSession:
    """
    Implementação fake de SAPSession para testes unitários.

    Implementa a mesma interface pública de SAPSession mas sem acessar
    o SAP real. Elementos, tabstrips e tabelas são registrados previamente
    via métodos add_*() para configurar o cenário de cada teste.

    Rastreamento
    ------------
    Além de simular respostas, a FakeSAPSession registra todas as interações
    para que os testes possam verificar o comportamento da transação:

        session.transactions  — transações abertas via start_transaction()
        session.vkeys         — teclas virtuais enviadas via send_vkey()
        session.home_calls    — número de vezes que go_home() foi chamado

    Rigor intencional
    -----------------
    find() e get_text() lançam exceção para caminhos não registrados.
    Isso é intencional — captura erros de caminho errado em tempo de teste,
    exatamente como o SAP real faria ao não encontrar um elemento.
    """

    def __init__(self):
        self._elements: dict[str, FakeElement] = {}
        self._tabstrips: dict[str, FakeTabStrip] = {}
        self._tables: dict[str, FakeTable] = {}

        # rastreamento de chamadas
        self.transactions: list[str] = []
        self.vkeys: list[int] = []
        self.home_calls: int = 0

    # ------------------------------------------------------------------
    # REGISTRO DE ELEMENTOS (configuração do cenário de teste)
    # ------------------------------------------------------------------

    def add(self, path: str, element: FakeElement) -> "FakeSAPSession":
        """
        Registra um FakeElement em um caminho SAP.

        Retorna self para permitir encadeamento:
            session.add("wnd[0]/usr/txtCAMPO", FakeElement("valor"))
                   .add("wnd[0]/usr/txtOUTRO", FakeElement("outro"))
        """
        self._elements[path] = element
        return self

    def add_tabstrip(self, path: str, tabstrip: FakeTabStrip) -> "FakeSAPSession":
        """
        Registra um FakeTabStrip em um caminho SAP.
        O TabStrip real é acessado via session.find(path) na ML81N.
        """
        self._tabstrips[path] = tabstrip
        return self

    def add_table(self, path: str, table: FakeTable) -> "FakeSAPSession":
        """Registra uma FakeTable em um caminho SAP."""
        self._tables[path] = table
        return self

    # ------------------------------------------------------------------
    # API — compatível com SAPSession
    # ------------------------------------------------------------------

    def find(self, path: str):
        """
        Localiza elemento, tabstrip ou tabela pelo caminho.
        Lança Exception para caminhos não registrados — igual ao SAP real.
        """
        if path in self._elements:
            return self._elements[path]
        if path in self._tabstrips:
            return self._tabstrips[path]
        if path in self._tables:
            return self._tables[path]
        raise Exception(f"Elemento não encontrado: {path!r}")

    def get_text(self, path: str) -> str:
        """Retorna o texto de um elemento registrado."""
        element = self._elements.get(path)
        if element is None:
            raise Exception(f"Elemento não encontrado: {path!r}")
        return element.Text

    def set_text(self, path: str, value: str):
        """Define o texto de um elemento registrado."""
        element = self._elements.get(path)
        if element is None:
            raise Exception(f"Elemento não encontrado: {path!r}")
        element.Text = value
        element.set_calls.append(value)

    def press(self, path: str):
        """Pressiona um botão registrado."""
        element = self._elements.get(path)
        if element is None:
            raise Exception(f"Botão não encontrado: {path!r}")
        element.press()

    def send_vkey(self, key: int):
        """Registra o envio de uma tecla virtual."""
        self.vkeys.append(key)

    def start_transaction(self, code: str):
        """Registra a abertura de uma transação SAP."""
        self.transactions.append(code)

    def go_home(self):
        """Registra chamada ao Easy Access."""
        self.home_calls += 1

    def exists(self, path: str) -> bool:
        """
        Verifica se um elemento existe.
        Retorna False para paths não registrados (elemento não existe).
        """
        return path in self._elements

    # ------------------------------------------------------------------
    # HELPERS DE ASSERÇÃO
    # ------------------------------------------------------------------

    def assert_transaction_opened(self, code: str):
        """
        Verifica que start_transaction(code) foi chamado.
        Lança AssertionError com mensagem clara se não foi.
        """
        assert code in self.transactions, (
            f"Esperava start_transaction({code!r}), "
            f"mas foram abertas: {self.transactions}"
        )

    def assert_vkey_sent(self, key: int):
        """Verifica que send_vkey(key) foi chamado ao menos uma vez."""
        assert key in self.vkeys, (
            f"Esperava send_vkey({key}), mas foram enviados: {self.vkeys}"
        )

    def assert_text_set(self, path: str, value: str):
        """Verifica que set_text(path, value) foi chamado."""
        element = self._elements.get(path)
        assert element is not None, f"Elemento não registrado: {path!r}"
        assert value in element.set_calls, (
            f"Esperava set_text({path!r}, {value!r}), "
            f"mas os valores definidos foram: {element.set_calls}"
        )

    def assert_pressed(self, path: str):
        """Verifica que press(path) foi chamado."""
        element = self._elements.get(path)
        assert element is not None, f"Botão não registrado: {path!r}"
        assert element.pressed, f"Esperava press({path!r}), mas não foi chamado"
