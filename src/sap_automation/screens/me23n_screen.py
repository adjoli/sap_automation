from functools import cached_property

from sap_automation.components import Section, TableControl, TabStrip
from sap_automation.components.table import validate_by_count
from sap_automation.core.converters import parse_sap_date
from sap_automation.parsers.me23n_parser import parse_me23n_items
from sap_automation.screens.base import Screen


class ME23NScreen(Screen):
    @cached_property
    def sections(self):
        containers = self.explorer.find_collapsible_sections()

        return [Section(container) for container in containers]

    # ----------
    def expand_sections(self):
        for section in self.sections:
            section.expand()

    # ----------
    def find_field(
        self,
        id_contains: str,
    ):
        return self.explorer.find_first(id_contains=id_contains)

    # ----------
    def read_header(self):
        result = {}

        fornecedor_field = self.find_field("MEPO_TOPLINE-SUPERFIELD")
        data_field = self.find_field("ctxtMEPO_TOPLINE-BEDAT")

        result["fornecedor"] = fornecedor_field.Text if fornecedor_field else None
        result["data"] = parse_sap_date(data_field.Text) if data_field else None

        section_header = Section(
            self.find_field(id_contains="subSUB1:SAPLMEVIEWS:1100")
        ).expand()

        tabs_header = TabStrip(self.explorer, id_contains="tabsHEADER_DETAIL")

        # aba TEXTOS
        tabs_header.select("Textos")

        # aba DADOS DO CLIENTE
        tabs_header.select("Dados do cliente")

        # aba STATUS
        tabs_header.select("Status")
        status_field = self.find_field(id_contains="txtMEPO1232-STATUS02")
        result["status"] = status_field.Text if status_field else None

        return result

        # return {
        #     "fornecedor": (fornecedor_field.Text if fornecedor_field else None),
        #     "data": parse_sap_date(data_field.Text if data_field else None),
        #     "status": (status_field.Text if status_field else None),
        # }

    # ----------
    @property
    def items_table(self):
        table_obj = self.explorer.find_first(
            type="GuiTableControl",
            id_contains="SAPLMEGUITC",
        )

        if not table_obj:
            raise RuntimeError("Tabela de itens não encontrada")

        return TableControl(
            self.session,
            table_obj.Id,
            column_validator=validate_by_count,
        )

    # ----------
    def read_items(self):
        rows = self.items_table.to_list()

        return parse_me23n_items(rows)
