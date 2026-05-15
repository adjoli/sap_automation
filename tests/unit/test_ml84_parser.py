"""
Testes unitários — parse_ml84

Conceito: testes de parser (função pura)
-----------------------------------------
Um parser é uma função pura: recebe dados brutos (HTML) e retorna
objetos estruturados. Não tem estado, não acessa o SAP, não tem
efeitos colaterais.

Isso o torna ideal para testes unitários:
  - Entrada e saída completamente controláveis
  - Execução rápida (sem I/O externo)
  - Fácil de isolar e reproduzir falhas

Estratégia de fixtures
-----------------------
Usamos dois tipos de fixture neste arquivo:

1. Fixtures de arquivo real (HTML exportado pelo SAP):
   - ml84_com_resultados.htm — 3 FRS reais, todos aceitos
   - ml84_vazio.htm          — lista sem resultados
   Ficam em tests/fixtures/ e são lidas pelo conftest.py.
   Garantem que o parser funciona com HTML real do SAP.

2. HTML mínimo embutido (para casos específicos):
   Quando queremos testar um comportamento pontual (ex: aceito=False,
   texto_breve vazio) sem depender do HTML real, criamos um HTML mínimo
   que contém apenas a estrutura necessária.
   Isso torna o teste legível e independente das fixtures.

Conceito: pytest.approx para floats
--------------------------------------
Valores de ponto flutuante não devem ser comparados com == devido a
imprecisões de representação binária.
  assert 0.1 + 0.2 == 0.3  → FALHA (0.30000000000000004)
  assert 0.1 + 0.2 == pytest.approx(0.3)  → PASSA

Para valores monetários grandes a diferença pode ser perceptível,
então sempre use pytest.approx() ao comparar floats nos testes.

Execução:
    pytest tests/unit/test_ml84_parser.py -v
"""

from pathlib import Path

import pytest

# Importa a função a ser testada — sem dependência de SAP
from sap_automation.parsers.ml84_parser import parse_ml84

# ─── Paths das fixtures ───────────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
HTML_COM_RESULTADOS = FIXTURES_DIR / "ml84_com_resultados.htm"
HTML_VAZIO = FIXTURES_DIR / "ml84_vazio.htm"

# ─── HTML mínimo para testes isolados ────────────────────────────────────────
# Representa a estrutura real do SAP com uma única FRS.
# Usado quando queremos testar um comportamento específico sem depender
# do HTML real (ex: aceito=False, ausência de ícone).
HTML_UMA_FRS_ACEITA = """
<html><body><blockquote><p>
<table class="list">
  <tbody>
    <tr><td>Pedido</td></tr>
    <tr><td>Item</td></tr>
    <tr><td>FolhRegSrv</td></tr>
  </tbody>
  <tbody>
    <tr><td>
      <nobr>4501926505</nobr>
      <nobr>&nbsp;OC01&nbsp;</nobr>
      <font face="SAPDings"><nobr title="9000013096">X</nobr></font>
      <nobr>&nbsp;C.HENRIQUE BODEMEIER &amp; CIA LTDA&nbsp;BRL&nbsp;27.02.2026&nbsp;</nobr>
    </td></tr>
    <tr><td>
      <nobr>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;1</nobr>
      <nobr>&nbsp;T053&nbsp;090400&nbsp;18.407,49&nbsp;06.03.2026&nbsp;</nobr>
    </td></tr>
    <tr><td>
      <nobr>1001904414</nobr>
      <img src="s_s_tl_g.gif">
      <nobr>&nbsp;Medição fevereiro/26&nbsp;18.407,49&nbsp;02.03.2026</nobr>
    </td></tr>
  </tbody>
  <tbody></tbody>
</table>
</p></blockquote></body></html>
"""

HTML_UMA_FRS_NAO_ACEITA = HTML_UMA_FRS_ACEITA.replace(
    'src="s_s_tl_g.gif"', 'src="s_b_spce.gif"'
)


# ─── Testes com HTML mínimo (isolados) ───────────────────────────────────────


class TestParseML84Estrutura:
    """
    Testes da estrutura de retorno do parser.
    Usam HTML mínimo para isolar cada comportamento.
    """

    def test_retorna_lista(self):
        """parse_ml84 deve sempre retornar uma lista, nunca None."""
        result = parse_ml84(HTML_UMA_FRS_ACEITA)
        assert isinstance(result, list)

    def test_retorna_lista_vazia_para_html_vazio(self):
        """
        HTML sem dados deve retornar lista vazia.

        O SAP exibe "Lista não contém dados" em um tbody com 1 tr.
        O parser detecta isso pela estrutura, não pelo texto — o que
        garante funcionamento mesmo com outros temas ou idiomas.
        """
        html_sem_dados = """
        <html><body><blockquote><p>
        <table class="list">
          <tbody><tr><td>Cabeçalho</td></tr></tbody>
          <tbody><tr><td>Lista não contém dados</td></tr></tbody>
          <tbody></tbody>
        </table>
        </p></blockquote></body></html>
        """
        result = parse_ml84(html_sem_dados)
        assert result == []

    def test_retorna_lista_vazia_para_html_invalido(self):
        """HTML sem table.list deve retornar lista vazia sem lançar exceção."""
        result = parse_ml84("<html><body>sem tabela</body></html>")
        assert result == []

    def test_retorna_um_item_por_frs(self):
        """Cada tbody de dados deve gerar exatamente um item na lista."""
        result = parse_ml84(HTML_UMA_FRS_ACEITA)
        assert len(result) == 1

    def test_item_tem_todos_os_campos(self):
        """
        Cada item retornado deve ter todos os campos esperados pelo modelo.

        Conceito: teste de contrato de interface.
        Garante que o parser não omite campos silenciosamente ao ser modificado.
        """
        result = parse_ml84(HTML_UMA_FRS_ACEITA)
        item = result[0]
        campos_esperados = {
            "frs",
            "aceito",
            "pedido",
            "item",
            "centro",
            "fornecedor_num",
            "fornecedor_nome",
            "data_doc",
            "valor_pedido",
            "data_remessa",
            "texto_breve",
            "valor",
            "criado_em",
        }
        campos_retornados = set(type(item).model_fields.keys())
        assert campos_esperados == campos_retornados


class TestParseML84Campos:
    """Testes de extração correta de cada campo."""

    def setup_method(self):
        """Parseia o HTML mínimo uma vez para todos os testes desta classe."""
        self.item = parse_ml84(HTML_UMA_FRS_ACEITA)[0]

    def test_numero_frs(self):
        assert self.item.frs == "1001904414"

    def test_pedido(self):
        assert self.item.pedido == "4501926505"

    def test_item_pedido(self):
        assert self.item.item == "1"

    def test_centro(self):
        assert self.item.centro == "T053"

    def test_fornecedor_num_extraido_do_title(self):
        """
        O código do fornecedor fica no atributo title do nobr dentro de font[SAPDings].
        Garante que estamos lendo o atributo correto, não o texto visível.
        """
        assert self.item.fornecedor_num == "9000013096"

    def test_fornecedor_nome(self):
        assert self.item.fornecedor_nome == "C.HENRIQUE BODEMEIER & CIA LTDA"

    def test_data_doc(self):
        assert self.item.data_doc is not None
        assert str(self.item.data_doc) == "2026-02-27"

    def test_data_remessa(self):
        assert self.item.data_remessa is not None
        assert str(self.item.data_remessa) == "2026-03-06"

    def test_criado_em(self):
        assert self.item.criado_em is not None
        assert str(self.item.criado_em) == "2026-03-02"

    def test_valor_frs(self):
        """
        Valor no formato brasileiro (18.407,49) deve ser convertido para float.
        Usa pytest.approx para evitar erros de precisão de ponto flutuante.
        """
        assert self.item.valor == pytest.approx(18407.49)

    def test_valor_pedido(self):
        assert self.item.valor_pedido == pytest.approx(18407.49)

    def test_texto_breve(self):
        assert self.item.texto_breve == "Medição fevereiro/26"


class TestParseML84Aceite:
    """Testes do campo aceito — detectado pela presença do ícone s_s_tl_g."""

    def test_aceito_true_quando_icone_presente(self):
        """
        aceito=True quando o ícone s_s_tl_g.gif está na linha da FRS.
        Este ícone representa o "semáforo verde" de aceite no SAP.
        """
        item = parse_ml84(HTML_UMA_FRS_ACEITA)[0]
        assert item.aceito is True

    def test_aceito_false_quando_icone_ausente(self):
        """
        aceito=False quando o ícone não é s_s_tl_g.gif.
        O SAP usa outros ícones (ex: s_b_spce.gif) para FRS não aceitas.
        """
        item = parse_ml84(HTML_UMA_FRS_NAO_ACEITA)[0]
        assert item.aceito is False


# ─── Testes com HTML real do SAP ─────────────────────────────────────────────


@pytest.mark.skipif(
    not HTML_COM_RESULTADOS.exists(),
    reason="Fixture ml84_com_resultados.htm não encontrada em tests/fixtures/",
)
class TestParseML84HTMLReal:
    """
    Testes com o HTML real exportado pelo SAP.

    Conceito: testes de regressão com dados reais
    -----------------------------------------------
    Esses testes usam um HTML capturado de uma execução real para garantir
    que o parser continua funcionando corretamente se o SAP mudar o formato
    do HTML exportado.

    São marcados com skipif para não falhar em ambientes sem a fixture.
    Copie os arquivos para tests/fixtures/ para habilitá-los:
        ml84_com_resultados.htm
        ml84_vazio.htm
    """

    def setup_method(self):
        self.html_com = HTML_COM_RESULTADOS.read_text(encoding="utf-8")
        self.resultado = parse_ml84(self.html_com)

    def test_retorna_tres_itens(self):
        """O HTML real contém 3 FRS — o parser deve retornar exatamente 3."""
        assert len(self.resultado) == 3

    def test_numeros_frs_corretos(self):
        """Os três números de FRS devem corresponder ao HTML exportado."""
        numeros = {item.frs for item in self.resultado}
        assert numeros == {"1001904414", "1001904415", "1001904416"}

    def test_todos_aceitos(self):
        """No HTML real, todas as FRS estão aceitas."""
        assert all(item.aceito for item in self.resultado)

    def test_mesmo_pedido_para_todos(self):
        """As três FRS pertencem ao mesmo pedido."""
        pedidos = {item.pedido for item in self.resultado}
        assert pedidos == {"4501926505"}

    def test_mesmo_fornecedor_para_todos(self):
        """As três FRS pertencem ao mesmo fornecedor."""
        fornecedores = {item.fornecedor_num for item in self.resultado}
        assert fornecedores == {"9000013096"}

    def test_centros_distintos(self):
        """Cada FRS tem um centro diferente."""
        centros = {item.centro for item in self.resultado}
        assert centros == {"T053", "T056", "T051"}

    def test_valores_corretos(self):
        """Valores monetários devem ser convertidos corretamente do formato BR."""
        valores = {item.frs: item.valor for item in self.resultado}
        assert valores["1001904414"] == pytest.approx(18407.49)
        assert valores["1001904415"] == pytest.approx(59700.00)
        assert valores["1001904416"] == pytest.approx(199193.50)

    def test_datas_sao_objetos_date(self):
        """
        Todos os campos de data devem ser objetos date, não strings.

        O modelo ML84Item usa date do Python — o parser deve converter
        as strings DD.MM.YYYY para objetos date antes de instanciar o modelo.
        """
        from datetime import date

        for item in self.resultado:
            if item.data_doc:
                assert isinstance(item.data_doc, date), (
                    f"data_doc de {item.frs} deveria ser date, é {type(item.data_doc)}"
                )
            if item.data_remessa:
                assert isinstance(item.data_remessa, date)
            if item.criado_em:
                assert isinstance(item.criado_em, date)


@pytest.mark.skipif(
    not HTML_VAZIO.exists(),
    reason="Fixture ml84_vazio.htm não encontrada em tests/fixtures/",
)
class TestParseML84HTMLRealVazio:
    """Testes com o HTML real de lista vazia."""

    def test_retorna_lista_vazia(self):
        """HTML real de lista vazia deve retornar []."""
        html = HTML_VAZIO.read_text(encoding="utf-8")
        assert parse_ml84(html) == []
