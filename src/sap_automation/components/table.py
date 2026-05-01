import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Protocol

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

    A estratégia de validação de colunas é injetável via `column_validator`,
    permitindo adaptar o comportamento a diferentes transações sem
    alterar a classe ou criar acoplamento entre contextos.

    Uso básico (aceita todas as colunas):
        table = TableControl(session, id="...")

    Com validação por count (ignora colunas parciais):
        table = TableControl(session, id="...", column_validator=validate_by_count)

    Com estratégia customizada:
        def meu_validator(col, total):
            return col.Count == total and col.Title.strip() != ""

        table = TableControl(session, id="...", column_validator=meu_validator)
    """

    def __init__(
        self,
        session,
        id: str,
        column_validator: ColumnValidator | None = None,
    ):
        self.session = session
        self.id = id
        self.logger = logging.getLogger("sap.components.tablecontrol")

        # Validator padrão: permissivo (comportamento original do ML81N)
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
        return self.vbar.Range + 1

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
        - converte "" → None
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

        Recebe col_index (int) em vez de um objeto Column para
        manter o método agnóstico ao modelo de colunas.
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
    # ITERAÇÃO COMPLETA (COM SCROLL)
    # ----------------------------------

    def _iter_rows(self):
        """
        Itera pelos índices reais de todas as linhas da tabela,
        fazendo scroll vertical conforme necessário.
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
    # LEITURA COMPLETA
    # ----------------------------------

    def to_list(self) -> list[dict]:
        """
        Extrai todas as linhas não-vazias da tabela como lista de dicts.

        Cada chave do dict é o título da coluna válida.
        O índice SAP real da coluna é usado internamente via Column.index,
        garantindo mapeamento correto independente de colunas inválidas
        intercaladas.
        """
        data = []

        for row in self._iter_rows():
            row_data = {
                col.name: self._get_cell(row, col.index) for col in self.valid_columns
            }

            if self._is_empty_row(row_data):
                continue

            data.append(row_data)

        return data

    # ----------------------------------
    # DATAFRAME (OPCIONAL)
    # ----------------------------------

    def to_dataframe(self):
        import pandas as pd

        return pd.DataFrame(self.to_list())
