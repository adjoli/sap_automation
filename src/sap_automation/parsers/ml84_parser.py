import re
from datetime import date
from typing import List

from bs4 import BeautifulSoup

from sap_automation.core.converters import parse_sap_date
from sap_automation.models.mm import ML84Item

# ─── HELPERS ──────────────────────────────────────────────────────────────────


def _clean(text: str) -> str:
    """Remove &nbsp; e espaços extras."""
    return text.replace("\xa0", " ").strip()


def _parse_valor(text: str) -> float:
    """Extrai valor monetário no formato brasileiro (1.234,56 → 1234.56)."""
    m = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", text)
    return float(m.group().replace(".", "").replace(",", ".")) if m else 0.0


def _parse_data(text: str) -> date | None:
    """Extrai data no formato DD.MM.YYYY e converte para objeto date."""
    m = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
    return parse_sap_date(m.group()) if m else None


# ─── PARSER PRINCIPAL ─────────────────────────────────────────────────────────


def parse_ml84(html: str) -> List[ML84Item]:
    """
    Parseia o HTML exportado pela transação ML84 do SAP.

    Estrutura do HTML
    -----------------
    O SAP exporta uma tabela com class="list" contendo N tbody:
        [0]      cabeçalho (3 linhas de título) — ignorado
        [1..N-1] dados — um tbody por FRS, cada um com 3 tr:
            tr[0] linha do pedido
            tr[1] linha do item
            tr[2] linha da FRS
        [N]      vazio — ignorado

    Caso sem resultados: tbody[1] tem apenas 1 tr.

    Retorna lista vazia se não houver dados ou se o HTML for inválido.
    """
    soup = BeautifulSoup(html, "html.parser")

    # busca dentro de table.list para não pegar tbodies de outras tabelas
    table = soup.find("table", class_="list")
    if not table:
        return []

    tbodies = table.find_all("tbody")

    # precisa de pelo menos cabeçalho + dados + rodapé
    if len(tbodies) < 3:
        return []

    # descarta cabeçalho (primeiro) e rodapé vazio (último)
    content_tbodies = tbodies[1:-1]

    # caso sem resultado: único tbody de dados com 1 linha
    if len(content_tbodies) == 1:
        rows = content_tbodies[0].find_all("tr")
        if len(rows) == 1:
            return []

    results = []

    for tbody in content_tbodies:
        rows = tbody.find_all("tr")

        if len(rows) < 3:
            continue

        row_pedido, row_item, row_frs = rows[:3]

        # ── LINHA DO PEDIDO ───────────────────────────────────────────────────
        td_ped = row_pedido.find("td")
        texto_ped = _clean(td_ped.get_text(" "))

        pedido_num = (
            _clean(td_ped.find("nobr").get_text()) if td_ped.find("nobr") else None
        )

        # código do fornecedor: atributo title do nobr dentro de font[SAPDings]
        font_sap = td_ped.find("font", face="SAPDings")
        fornecedor_num = None
        if font_sap:
            nobr_sap = font_sap.find("nobr")
            fornecedor_num = nobr_sap.get("title") if nobr_sap else None

        # nome do fornecedor: texto entre "X" (SAPDings) e "BRL"
        m_nome = re.search(r"X\s+(.+?)\s+BRL", texto_ped)
        fornecedor_nome = m_nome.group(1).strip() if m_nome else None

        data_doc = _parse_data(texto_ped)

        # ── LINHA DO ITEM ─────────────────────────────────────────────────────
        td_item = row_item.find("td")
        texto_item = _clean(td_item.get_text(" "))

        m_item = re.match(r"\s*(\d+)", texto_item)
        item_num = m_item.group(1) if m_item else None

        # centro: letra seguida de dígitos (ex: T053)
        m_centro = re.search(r"\b([A-Z]\d+)\b", texto_item)
        centro = m_centro.group(1) if m_centro else None

        valor_pedido = _parse_valor(texto_item)
        data_remessa = _parse_data(texto_item)

        # ── LINHA DA FRS ──────────────────────────────────────────────────────
        td_frs = row_frs.find("td")

        frs_num = (
            _clean(td_frs.find("nobr").get_text()) if td_frs.find("nobr") else None
        )

        # aceite: presença do ícone s_s_tl_g (semáforo verde)
        aceito = any("s_s_tl_g" in img.get("src", "") for img in td_frs.find_all("img"))

        # último nobr: texto breve + valor + data de criação
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
