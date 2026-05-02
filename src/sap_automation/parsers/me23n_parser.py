from sap_automation.core.converters import parse_sap_date, parse_sap_float
from sap_automation.models.mm.pedido import ItemPedido


# =================================================
# HELPERS
# =================================================
def get_value(row: dict, *keys):
    for key in keys:
        value = row.get(key)

        if value not in (None, ""):
            return value

    return None


# =================================================
# PARSER PRINCIPAL
# =================================================
def parse_me23n_items(rows: list[dict]) -> list[ItemPedido]:
    items = []

    for row in rows:
        item = ItemPedido(
            item=get_value(row, "Item", "Itm"),
            material=get_value(row, "Material"),
            descricao=get_value(row, "Texto breve", "Descrição"),
            quantidade=parse_sap_float(
                get_value(row, "Qtd.pedido", "Qtd.", "Quantidade")
            ),
            dt_remessa=parse_sap_date(get_value(row, "Dt.remessa")),
            unidade=get_value(row, "UMP", "Unidade"),
            valor=parse_sap_float(get_value(row, "Preço líq.", "Valor")),
        )

        items.append(item)

    return items
