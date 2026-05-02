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


# ----------
def to_float(value):
    if value is None:
        return None

    try:
        return float(str(value).replace(".", "").replace(",", "."))
    except Exception:
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
            quantidade=to_float(get_value(row, "Qtd.pedido", "Qtd.", "Quantidade")),
            unidade=get_value(row, "UMP", "Unidade"),
            valor=to_float(get_value(row, "Preço líq.", "Valor")),
        )

        items.append(item)

    return items
