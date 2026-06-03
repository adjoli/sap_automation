import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

from .base.table_reader import TableReader


# ----------------------------------
# TIPOS / CONTRATOS
# ----------------------------------
@dataclass(frozen=True)
class Column:
    """
    Representa uma coluna da GuiTableControl.

    Mantém índice, nome e validade juntos para evitar
    indexação implícita entre estruturas paralelas.
    """

    index: int
    name: str
    is_valid: bool


class ColumnValidator(Protocol):
    """
    Protocolo para estratégias de validação de coluna.

    Recebe o objeto de coluna SAP e o total de linhas da tabela.
    Retorna True se a coluna deve ser incluída na extração.
    """

    def __call__(self, sap_column: object, total_rows: int) -> bool: ...


# ----------------------------------
# VALIDATORS PRONTOS PARA USO
# ----------------------------------
def validate_by_count(sap_column: object, total_rows: int) -> bool:
    """
    Validator padrão: aceita apenas colunas cujo .Count
    é igual ao total de linhas da tabela.

    Adequado para tabelas com colunas parcialmente preenchidas
    (ex: ME23N com 37 colunas heterogêneas).
    """
    try:
        return sap_column.Count == total_rows
    except Exception:
        return False


def validate_all(sap_column: object, total_rows: int) -> bool:
    """
    Validator permissivo: aceita todas as colunas sem critério.

    Adequado para tabelas simples onde todas as colunas
    são legíveis (ex: ML81N com 5 colunas).
    """
    return True


# ----------------------------------
# COMPONENTE
# ----------------------------------
class TableControl(TableReader):
    """
    Abstração sobre GuiTableControl do SAP GUI Scripting.

    Estratégias de leitura
    ----------------------
    wnd[0] (padrão):
        _iter_rows() posiciona vbar.Position por janela e lê GetCell(row, col)
        com índice absoluto. Funciona para todas as tabelas em wnd[0].

    wnd[1] (popups):
        _iter_rows_popup() faz scroll incremental linha a linha via
        vbar.Position += 1, lendo sempre GetCell(0, col) — a linha
        que está no topo da view. Necessário porque tabelas em popups
        não aceitam índice absoluto em GetCell.

    Uso básico:
        table = TableControl(session, id='...')

    Em popup (wnd[1]):
        table = TableControl(session, id='...', window='wnd[1]')

    Com validação por count:
        table = TableControl(session, id='...', column_validator=validate_by_count)
    """

    def __init__(
        self,
        session,
        id: str,
        column_validator: ColumnValidator | None = None,
        window: str = "wnd[0]",
    ):
        self.session = session
        self.id = id
        self.window = window
        self.logger = logging.getLogger("sap.components.tablecontrol")
        self._column_validator: ColumnValidator = column_validator or validate_all

    # ----------------------------------
    # ACESSO AO OBJETO SAP
    # ----------------------------------

    @property
    def table(self):
        return self.session.find(self.id)

    @property
    def hbar(self):
        return self.table.HorizontalScrollbar

    @property
    def vbar(self):
        return self.table.VerticalScrollbar

    # ----------------------------------
    # DIMENSÕES
    # ----------------------------------

    @property
    def visible_row_count(self) -> int:
        return self.table.VisibleRowCount

    @property
    def total_row_count(self) -> int:
        """
        Total de linhas da tabela.

        wnd[0]: usa vbar.Range + 1 — comportamento original, funciona
                corretamente para tabelas em wnd[0].
        wnd[1]: usa vbar.Range + 1 — RowCount em popups inclui linhas
                fantasma que inflam o total.
        """
        try:
            return self.vbar.Range + 1
        except Exception:
            return self.visible_row_count

    # ----------------------------------
    # COLUNAS
    # ----------------------------------

    @cached_property
    def _columns(self) -> list[Column]:
        """
        Descobre todas as colunas da tabela e aplica o validator
        para marcar cada uma como válida ou não.

        O índice SAP real é preservado em Column.index, garantindo
        que GetCell(row, col.index) sempre aponte para a coluna correta,
        independentemente de quantas colunas inválidas existam antes dela.
        """
        total = self.total_row_count
        result = []

        for i in range(self.table.Columns.Count):
            try:
                sap_col = self.table.Columns.ElementAt(i)
                name = sap_col.Title.strip() or f"col_{i}"
                is_valid = self._column_validator(sap_col, total)

                if not is_valid:
                    self.logger.debug(
                        f"Coluna ignorada [{i}] '{name}' "
                        f"(validator={self._column_validator.__name__})"
                    )

            except Exception as e:
                self.logger.debug(f"Erro ao inspecionar coluna {i}: {e}")
                name = f"col_{i}"
                is_valid = False

            result.append(Column(index=i, name=name, is_valid=is_valid))

        return result

    @cached_property
    def valid_columns(self) -> list[Column]:
        """Colunas que passaram pelo validator."""
        return [c for c in self._columns if c.is_valid]

    @cached_property
    def column_count(self) -> int:
        """Número de colunas válidas."""
        return len(self.valid_columns)

    # ----------------------------------
    # NORMALIZAÇÃO
    # ----------------------------------

    def _normalize(self, value):
        """
        Normaliza valores vindos do SAP:
        - remove espaços
        - converte '' → None
        """
        if isinstance(value, str):
            value = value.strip()
            return value if value else None
        return value

    # ----------------------------------
    # LEITURA DE CÉLULA
    # ----------------------------------

    def _get_cell(self, row: int, col_index: int):
        """
        Lê o valor de uma célula pelo índice SAP real da coluna.
        row é índice absoluto (wnd[0]) ou relativo à view (wnd[1]).
        """
        try:
            cell = self.table.GetCell(row, col_index)
        except Exception:
            return None

        match getattr(cell, "Type", ""):
            case "GuiCheckBox":
                return cell.Selected
            case "GuiButton":
                return None
            case _:
                return self._normalize(getattr(cell, "Text", None))

    # ----------------------------------
    # DETECÇÃO DE LINHA VAZIA
    # ----------------------------------

    def _is_empty_row(self, row_data: dict) -> bool:
        """
        Uma linha é considerada vazia quando NÃO possui
        nenhum valor textual/numérico relevante.

        False em checkbox NÃO conta como conteúdo.
        """
        for value in row_data.values():
            if value is None:
                continue
            if value is False:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return False
        return True

    # ----------------------------------
    # ITERAÇÃO — wnd[0]
    # ----------------------------------

    def _iter_rows(self):
        """
        Itera pelos índices reais de todas as linhas da tabela.

        Posiciona vbar por janelas de linhas visíveis e usa GetCell
        com índice absoluto — funciona para tabelas em wnd[0].
        """
        total = self.total_row_count
        visible = self.visible_row_count

        for start in range(0, total, visible):
            self.vbar.Position = start

            for i in range(visible):
                row_index = start + i
                if row_index >= total:
                    return
                yield row_index

    # ----------------------------------
    # ITERAÇÃO — wnd[1] (popups)
    # ----------------------------------

    def _iter_rows_popup(self):
        """
        Itera pelas linhas de tabelas em popups (wnd[1]).

        Tabelas em popups não aceitam GetCell com índice absoluto.
        Faz scroll incremental linha a linha via vbar.Position += 1,
        sempre lendo a posição 0 da view (linha atual no topo).

        Retorna tuplas (visual_row, absolute_index) onde visual_row
        é sempre 0 — a linha visível no topo após cada scroll.
        """
        total = self.total_row_count
        for nrow in range(total):
            yield 0  # sempre lê a linha 0 da view visível
            if nrow < total - 1:
                self.vbar.Position += 1

    # ----------------------------------
    # LEITURA COMPLETA
    # ----------------------------------

    def to_list(self) -> list[dict]:
        """
        Extrai todas as linhas não-vazias da tabela como lista de dicts.

        Seleciona automaticamente a estratégia de iteração conforme window:
        - wnd[0]: índice absoluto via _iter_rows()
        - wnd[1]: scroll incremental via _iter_rows_popup()
        """
        data = []

        iterator = (
            self._iter_rows_popup() if self.window == "wnd[1]" else self._iter_rows()
        )

        for row in iterator:
            row_data = {
                col.name: self._get_cell(row, col.index) for col in self.valid_columns
            }
            if not self._is_empty_row(row_data):
                data.append(row_data)

        return data

    # ----------------------------------
    # DATAFRAME (OPCIONAL)
    # ----------------------------------

    def to_dataframe(self):
        import pandas as pd

        return pd.DataFrame(self.to_list())
