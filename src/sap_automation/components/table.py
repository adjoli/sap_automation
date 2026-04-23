import logging


class TableControl:
    def __init__(self, session, table_id: str):
        self.logger = logging.getLogger("sap.tablecontrol")
        self.session = session
        self.table_id = table_id

    # ----------------------------------
    # CORE
    # ----------------------------------

    @property
    def table(self):
        return self.session.find(self.table_id)

    @property
    def vbar(self):
        return self.table.VerticalScrollbar

    @property
    def column_count(self):
        return len(self.table.Columns)
        # return self.table.ColumnCount

    @property
    def column_titles(self):
        return [col.Title for col in self.table.Columns]

    # ----------------------------------
    # LEITURA COMPLETA (ROBUSTA)
    # ----------------------------------

    def to_list(self) -> list[dict]:
        """
        Lê TODAS as linhas da tabela (com scroll).
        Retorna lista de dicts (linha a linha).
        """

        data = []

        total_rows = self.vbar.Range + 1
        col_titles = self.column_titles

        self.logger.debug(f"Lendo {total_rows} linhas da tabela")

        # reset scroll
        self.vbar.Position = 0

        for nrow in range(total_rows):
            row_data = {}

            row = self.table.GetAbsoluteRow(nrow)

            for col_idx, col_name in enumerate(col_titles):
                try:
                    cell = row.ElementAt(col_idx)

                    match cell.Type:
                        case "GuiCheckBox":
                            value = cell.Selected
                        case "GuiButton":
                            value = None
                        case _:
                            value = cell.Text.strip()

                except Exception:
                    value = None

                row_data[col_name] = value

            data.append(row_data)

            # scroll controlado
            if nrow < total_rows - 1:
                self.vbar.Position = nrow + 1

        return data
