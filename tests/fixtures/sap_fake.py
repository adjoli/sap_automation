"""
Fixtures de sessão SAP para testes unitários.

Conceito: Test Doubles
-----------------------
Um "test double" é qualquer objeto que substitui uma dependência real
durante os testes. O FakeSAPSession é um *Fake*: implementa a mesma
interface que SAPSession mas sem acessar o SAP real.

Estrutura
---------
FakeElement       — simula qualquer elemento GUI do SAP
FakeTabElement    — simula uma aba dentro de um FakeTabStrip
FakeTabStrip      — simula GuiTabStrip, registra navegação entre abas
FakeTable         — simula GuiTableControl, retorna linhas configuráveis
FakeScrollbar     — simula scrollbar (stub vazio)
FakeTableColumn   — simula coluna de tabela
FakeTableCell     — simula célula de tabela
FakeSAPSession    — orquestra os elementos, implementa a API de SAPSession
"""


# ─── FakeElement ──────────────────────────────────────────────────────────────


class FakeElement:
    """Simula qualquer elemento GUI do SAP (GuiTextField, GuiButton, etc)."""

    def __init__(self, text: str = "", icon_name: str = "", exists: bool = True):
        self.Text = text
        self.text = text
        self.IconName = icon_name
        self.exists = exists
        self.pressed = False
        self.selected = False
        self.closed = False
        self.set_calls: list[str] = []

    def press(self):
        self.pressed = True

    def select(self):
        self.selected = True

    def close(self):
        self.closed = True

    def __repr__(self):
        return f"FakeElement(text={self.Text!r}, icon={self.IconName!r})"


# ─── FakeTabElement ───────────────────────────────────────────────────────────


class FakeTabElement:
    """
    Simula uma aba individual (GuiTab) dentro de um FakeTabStrip.
    Ao ser selecionado, atualiza a aba ativa no TabStrip pai.
    """

    def __init__(self, tabstrip: "FakeTabStrip", name: str):
        self._tabstrip = tabstrip
        self.Text = name
        self.selected = False

    def select(self):
        self._tabstrip.select(self.Text)
        self.selected = True

    def __repr__(self):
        return f"FakeTabElement(name={self.Text!r})"


# ─── FakeTabStrip ─────────────────────────────────────────────────────────────


class FakeTabStrip:
    """
    Simula GuiTabStrip — registra navegação entre abas.

    Expõe SelectedTab para compatibilidade com TabStrip.current()
    e TabStrip.current_explorer(), que acessam tabstrip.SelectedTab
    diretamente.

    Uso
    ---
        tabstrip = FakeTabStrip(["DdsBásicos", "Vals.", "Dados adic."])
        session.add_tabstrip("wnd[0]/usr/tabsTAB_HEADER", tabstrip)

        # após rodar a transação:
        assert tabstrip.history == ["DdsBásicos", "Vals."]
        assert tabstrip.current == "Vals."
    """

    def __init__(self, tabs: list[str]):
        self._tabs = tabs
        self._current: str | None = tabs[0] if tabs else None

        # registra a aba inicial no histórico — TabStrip.select() faz skip
        # quando a aba já está ativa (evita rerender), então a primeira aba
        # nunca passaria por select(). Pré-registrar garante was_selected()
        # funciona para a aba que já estava ativa ao criar o tabstrip.
        self.history: list[str] = [tabs[0]] if tabs else []

        # SelectedTab expõe a aba atual como objeto com atributo Text
        # — necessário para TabStrip.current() e current_explorer()
        self.SelectedTab = _FakeSelectedTab(self._current)

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def names(self) -> list[str]:
        return list(self._tabs)

    def select(self, name: str):
        if name not in self._tabs:
            raise ValueError(f"Aba não encontrada: {name!r}. Disponíveis: {self._tabs}")
        self._current = name
        self.history.append(name)
        # atualiza SelectedTab para refletir a nova aba ativa
        self.SelectedTab = _FakeSelectedTab(name)

    def was_selected(self, name: str) -> bool:
        return name in self.history

    # compatibilidade com TabStrip.tabs (itera Children)
    @property
    def Children(self):
        return _FakeChildren(
            [_FakeTabChild(name, name == self._current, self) for name in self._tabs]
        )

    def __repr__(self):
        return f"FakeTabStrip(current={self._current!r}, tabs={self._tabs})"


class _FakeSelectedTab:
    """Objeto retornado por FakeTabStrip.SelectedTab — expõe Text e Id."""

    def __init__(self, name: str | None):
        self.Text = name or ""
        self.Id = f"tabp_{name}" if name else ""


class _FakeTabChild:
    """Representa uma aba individual no Children do FakeTabStrip."""

    def __init__(self, name: str, selected: bool, tabstrip: "FakeTabStrip"):
        self.Text = name
        self.Id = f"tabp_{name}"
        self.selected = selected
        self._tabstrip = tabstrip

    def select(self):
        """Propaga a seleção para o FakeTabStrip, registrando no histórico."""
        self._tabstrip.select(self.Text)
        self.selected = True


class _FakeChildren:
    """Simula a coleção Children de um GuiTabStrip."""

    def __init__(self, items):
        self._items = items

    def __iter__(self):
        return iter(self._items)

    def Count(self):
        return len(self._items)

    def ElementAt(self, index):
        return self._items[index]


# ─── FakeTable ────────────────────────────────────────────────────────────────


class FakeTable:
    """Simula GuiTableControl — retorna linhas configuráveis."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.accessed = False

        # atributos acessados por TableControl
        self.VerticalScrollbar = _FakeScrollbarObj(len(rows))
        self.HorizontalScrollbar = _FakeScrollbarObj()
        self.VisibleRowCount = len(rows)

        # Columns — necessário para validação de colunas
        col_names = list(rows[0].keys()) if rows else []
        self.Columns = _FakeColumns(col_names)

    def GetCell(self, row: int, col_index: int):
        """
        Simula GuiTableControl.GetCell(row, col_index).

        Colunas cujo nome é "Sel." são tratadas como GuiCheckBox —
        retornam Selected=True quando o valor for "X".
        Demais colunas são tratadas como GuiTextField.
        """
        col_names = list(self._rows[row].keys())
        col_name = col_names[col_index]
        value = self._rows[row][col_name]

        # checkboxes SAP retornam Selected (bool), não Text
        if col_name == "Sel.":
            return FakeTableCell(value == "X", is_checkbox=True)

        return FakeTableCell(value)

    def to_list(self) -> list[dict]:
        self.accessed = True
        return list(self._rows)

    def __repr__(self):
        return f"FakeTable(rows={len(self._rows)})"


class _FakeScrollbarObj:
    """
    Stub do scrollbar vertical de GuiTableControl.

    Atributos usados por TableControl:
        Range    — total_row_count = Range + 1, portanto Range = n_rows - 1
        Maximum  — linha máxima de scroll
        Position — posição atual do scroll
    """

    def __init__(self, n_rows: int = 0):
        # TableControl.total_row_count = vbar.Range + 1
        # Para n linhas: Range deve ser n - 1
        self.Range = max(0, n_rows - 1)
        self.Maximum = max(0, n_rows - 1)
        self.Position = 0


# ─── Stubs de componentes de tabela ───────────────────────────────────────────


class FakeScrollbar:
    """Stub vazio para scrollbar — sem comportamento relevante para testes."""

    pass


class _FakeColumns:
    """Simula a coleção Columns de GuiTableControl."""

    def __init__(self, names: list[str]):
        self._names = names

    @property
    def Count(self):
        return len(self._names)

    def ElementAt(self, index):
        return _FakeColumn(self._names[index])


class _FakeColumn:
    """Simula uma coluna de GuiTableControl."""

    def __init__(self, name: str):
        self.Name = name
        self.Title = name


class FakeTableColumn:
    def __init__(self, name: str, cells: list[str]):
        self.name = name
        self._cells = cells

    def __getitem__(self, index):
        return self._cells[index]


class FakeTableCell:
    """
    Simula uma célula de GuiTableControl.

    TableControl._get_cell() acessa cell.Type para distinguir checkboxes
    de campos de texto. Para checkboxes, retorna cell.Selected (bool).
    Para demais tipos, retorna cell.Text (str).
    """

    def __init__(self, value, is_checkbox: bool = False):
        self._is_checkbox = is_checkbox
        if is_checkbox:
            self.Type = "GuiCheckBox"
            self.Selected = bool(value)
            self.Text = str(value)
        else:
            self.Type = "GuiTextField"
            self.Text = str(value) if value is not None else ""
            self.Selected = False


# ─── FakeSAPSession ───────────────────────────────────────────────────────────


class FakeSAPSession:
    """
    Implementação fake de SAPSession para testes unitários.

    Elementos, tabstrips e tabelas são registrados previamente via add_*()
    para configurar o cenário de cada teste.

    Rastreamento
    ------------
    transactions  — transações abertas via start_transaction()
    vkeys         — teclas virtuais enviadas via send_vkey()
    home_calls    — número de vezes que go_home() foi chamado
    radios_set    — paths de radio buttons selecionados via set_radio()
    """

    def __init__(self):
        self._elements: dict[str, FakeElement] = {}
        self._tabstrips: dict[str, FakeTabStrip] = {}
        self._tables: dict[str, FakeTable] = {}

        # rastreamento
        self.transactions: list[str] = []
        self.vkeys: list[int] = []
        self.home_calls: int = 0
        self.radios_set: list[str] = []

    # ------------------------------------------------------------------
    # REGISTRO
    # ------------------------------------------------------------------

    def add(self, path: str, element: FakeElement) -> "FakeSAPSession":
        self._elements[path] = element
        return self

    def add_tabstrip(self, path: str, tabstrip: FakeTabStrip) -> "FakeSAPSession":
        self._tabstrips[path] = tabstrip
        return self

    def add_table(self, path: str, table: FakeTable) -> "FakeSAPSession":
        self._tables[path] = table
        return self

    # ------------------------------------------------------------------
    # API — compatível com SAPSession
    # ------------------------------------------------------------------

    def find(self, path: str):
        if path in self._elements:
            return self._elements[path]
        if path in self._tabstrips:
            return self._tabstrips[path]
        if path in self._tables:
            return self._tables[path]
        raise Exception(f"Elemento não encontrado: {path!r}")

    def get_text(self, path: str) -> str:
        return self._elements[path].Text

    def set_text(self, path: str, value: str):
        element = self._elements.get(path)
        if element is None:
            raise Exception(f"Elemento não encontrado: {path!r}")
        element.Text = value
        element.text = value
        element.set_calls.append(value)

    def press(self, path: str):
        element = self._elements.get(path)
        if element is None:
            raise Exception(f"Botão não encontrado: {path!r}")
        element.press()

    def send_vkey(self, key: int, window: str = "wnd[0]"):
        self.vkeys.append(key)

    def start_transaction(self, code: str):
        self.transactions.append(code)

    def go_home(self):
        self.home_calls += 1

    def exists(self, path: str) -> bool:
        return path in self._elements

    def set_radio(self, path: str):
        self.radios_set.append(path)

    def get_status_bar(self) -> str:
        return ""

    # ------------------------------------------------------------------
    # HELPERS DE ASSERÇÃO
    # ------------------------------------------------------------------

    def assert_transaction_opened(self, code: str):
        assert code in self.transactions, (
            f"Esperava start_transaction({code!r}), mas foram: {self.transactions}"
        )

    def assert_vkey_sent(self, key: int):
        assert key in self.vkeys, f"Esperava send_vkey({key}), mas foram: {self.vkeys}"

    def assert_text_set(self, path: str, value: str):
        element = self._elements.get(path)
        assert element is not None, f"Elemento não registrado: {path!r}"
        assert value in element.set_calls, (
            f"Esperava set_text({path!r}, {value!r}), mas foi: {element.set_calls}"
        )

    def assert_pressed(self, path: str):
        element = self._elements.get(path)
        assert element is not None, f"Botão não registrado: {path!r}"
        assert element.pressed, f"Esperava press({path!r}), mas não foi chamado"
