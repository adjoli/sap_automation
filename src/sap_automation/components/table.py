import logging
from functools import cached_property

from .base.table_reader import TableReader


class TableControl(TableReader):
    def __init__(self, session, id: str):
        self.session = session
        self.id = id
        self.logger = logging.getLogger("sap.components.tablecontrol")

    # ----------------------------------
    # ACESSO BASE
    # ----------------------------------
    @property
    def table(self):
        return self.session.find(self.id)

    @property
    def vertical_scrollbar(self):
        return self.table.VerticalScrollbar

    # ----------------------------------
    # METADADOS
    # ----------------------------------
    @cached_property
    def columns(self) -> list[str]:
        return [col.Title for col in self.table.Columns]

    @cached_property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def visible_row_count(self) -> int:
        return self.table.VisibleRowCount

    @property
    def total_row_count(self) -> int:
        # return self.table.RowCount
        return self.vertical_scrollbar.Range + 1

    # ----------------------------------
    # LEITURA DE CÉLULA
    # ----------------------------------
    def _get_cell(self, row: int, col: int):
        cell = self.table.GetAbsoluteRow(row).ElementAt(col)

        match getattr(cell, "Type", ""):
            case "GuiCheckBox":
                return cell.Selected
            case "GuiButton":
                return None
            case _:
                return getattr(cell, "Text", None)

    # ----------------------------------
    # ITERAÇÃO COMPLETA (COM SCROLL)
    # ----------------------------------
    def _iter_rows(self):
        """
        Itera todas as linhas da tabela (com scroll automático)
        """
        total = self.total_row_count
        visible = self.visible_row_count

        current_position = 0

        for start in range(0, total, visible):
            self.vertical_scrollbar.Position = start

            for i in range(visible):
                row_index = start + i

                if row_index >= total:
                    return

                yield row_index

    # ----------------------------------
    # LEITURA COMPLETA
    # ----------------------------------
    def to_list(self) -> list[dict]:
        data = []

        for row in self._iter_rows():
            row_data = {}

            for col_idx, col_name in enumerate(self.columns):
                value = self._get_cell(row, col_idx)
                row_data[col_name] = value

            data.append(row_data)

        print(len(data))
        return data

    # ----------------------------------
    # DATAFRAME (OPCIONAL)
    # ----------------------------------
    def to_dataframe(self):
        import pandas as pd

        return pd.DataFrame(self.to_list())
