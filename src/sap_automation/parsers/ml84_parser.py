import re
from typing import List

from bs4 import BeautifulSoup

from sap_automation.models.mm import ML84Item

# ─── HELPERS ──────────────────────────────────────────────────────────────────


def _clean(text: str) -> str:
    """Remove &nbsp; e espaços extras."""
    return text.replace("\xa0", " ").strip()


def _parse_valor(text: str) -> float:
    """Extrai valor monetário no formato brasileiro (1.234,56 → 1234.56)."""
    m = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", text)
    return float(m.group().replace(".", "").replace(",", ".")) if m else 0.0


def _parse_data(text: str) -> str | None:
    """Extrai data no formato DD.MM.YYYY."""
    m = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
    return m.group() if m else None


# ─── PARSER PRINCIPAL ─────────────────────────────────────────────────────────
def parse_ml84(html: str) -> List[ML84Item]:
    soup = BeautifulSoup(html, "html.parser")

    tbodies = soup.find_all("tbody")

    # precisa ter pelo menos 3
    if len(tbodies) < 3:
        return []

    # remove header e footer
    content_tbodies = tbodies[1:-1]

    # ----------------------------
    # CASO SEM RESULTADO
    # ----------------------------
    if len(content_tbodies) == 1:
        rows = content_tbodies[0].find_all("tr")
        if len(rows) == 1:
            text = _clean(rows[0].get_text()).lower()
            if "não" in text and "dados" in text:
                return []

    results = []

    # ----------------------------
    # CADA TBODY = 1 FRS
    # ----------------------------
    for tbody in content_tbodies:
        rows = tbody.find_all("tr")

        if len(rows) < 3:
            continue

        row_pedido, row_item, row_frs = rows[:3]

        # ── PEDIDO ─────────────────
        td_ped = row_pedido.find("td")
        texto_ped = _clean(td_ped.get_text(" "))

        pedido_num = (
            _clean(td_ped.find("nobr").get_text()) if td_ped.find("nobr") else None
        )

        font_sap = td_ped.find("font", face="SAPDings")
        fornecedor_num = None
        if font_sap:
            nobr_sap = font_sap.find("nobr")
            fornecedor_num = nobr_sap.get("title") if nobr_sap else None

        m_nome = re.search(r"X\s+(.+?)\s+BRL", texto_ped)
        fornecedor_nome = m_nome.group(1).strip() if m_nome else None

        data_doc = _parse_data(texto_ped)

        # ── ITEM ──────────────────
        td_item = row_item.find("td")
        texto_item = _clean(td_item.get_text(" "))

        m_item = re.match(r"\s*(\d+)", texto_item)
        item_num = m_item.group(1) if m_item else None

        m_centro = re.search(r"\b([A-Z]\d+)\b", texto_item)
        centro = m_centro.group(1) if m_centro else None

        valor_pedido = _parse_valor(texto_item)
        data_remessa = _parse_data(texto_item)

        # ── FRS ───────────────────
        td_frs = row_frs.find("td")

        frs_num = (
            _clean(td_frs.find("nobr").get_text()) if td_frs.find("nobr") else None
        )

        aceito = any("s_s_tl_g" in img.get("src", "") for img in td_frs.find_all("img"))

        nobrs = td_frs.find_all("nobr")
        ultimo = _clean(nobrs[-1].get_text()) if nobrs else ""

        valor_frs = _parse_valor(ultimo)
        criado_em = _parse_data(ultimo)

        texto_breve = re.split(r"\d{1,3}(?:\.\d{3})*,\d{2}", ultimo)[0].strip()

        results.append(
            ML84Item(
                frs=frs_num,
                aceito=aceito,
                pedido=pedido_num,
                item=item_num,
                centro=centro,
                fornecedor_num=fornecedor_num,
                fornecedor_nome=fornecedor_nome,
                data_doc=data_doc,
                valor_pedido=valor_pedido,
                data_remessa=data_remessa,
                texto_breve=texto_breve,
                valor=valor_frs,
                criado_em=criado_em,
            )
        )

    return results
