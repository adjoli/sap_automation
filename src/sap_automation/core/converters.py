from datetime import date, datetime


# ---------
def parse_sap_date(value: str | None) -> date | None:
    """
    Converte:
        '17.05.2026'
    para:
        date(2026, 5, 17)
    """

    if not value:
        return None

    try:
        return datetime.strptime(value, "%d.%m.%Y").date()

    except Exception:
        return None


def parse_sap_float(value) -> float | None:
    if not value:
        return None

    try:
        return float(value.replace(".", "").replace(",", "."))
    except Exception:
        return None


# ---------
def format_sap_date(value: date | None) -> str:
    """
    Converte:
        date(2026, 5, 17)

    para:
        '17.05.2026'
    """

    if value is None:
        return ""

    return value.strftime("%d.%m.%Y")
