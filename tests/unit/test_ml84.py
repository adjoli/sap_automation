"""
Testes unitários — ML84 (Listagem de FRS)

Conceito: mockando dependências externas
-----------------------------------------
A ML84 tem duas dependências que não podemos exercitar em testes unitários:

  1. SAPExporter — cria arquivos temporários e acessa o SAP real
  2. pyperclip    — acessa a área de transferência do sistema operacional

Estratégia para cada uma:

  SAPExporter: substituímos export_html() com mocker.patch, fazendo-a
  retornar diretamente o HTML da fixture. Elimina arquivo temporário
  e necessidade de SAP conectado.

  pyperclip: substituímos pyperclip.copy() com mocker.patch para evitar
  que os testes modifiquem a área de transferência real da máquina —
  efeito colateral inaceitável em testes unitários.

Conceito: isolamento de efeitos colaterais
-------------------------------------------
Testes unitários não devem modificar estado externo ao processo:
  - Sistema de arquivos (exceto diretórios temporários gerenciados)
  - Área de transferência
  - Rede / banco de dados
  - Variáveis de ambiente (use monkeypatch para isso)

mocker.patch() é a ferramenta para isolar esses efeitos.

Execução:
    pytest tests/unit/test_ml84.py -v
"""

from pathlib import Path

import pytest

from sap_automation.transactions.mm.ml84 import ML84, ML84Filter, ML84Status
from tests.fixtures.sap_fake import FakeElement, FakeSAPSession

# ─── Paths das fixtures HTML ──────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
HTML_COM_RESULTADOS = FIXTURES_DIR / "ml84_com_resultados.htm"
HTML_VAZIO = FIXTURES_DIR / "ml84_vazio.htm"

# ─── Paths SAP usados pela ML84 ───────────────────────────────────────────────
PATH_BTN_FRS = "wnd[0]/usr/btn%_S_LBLNI_%_APP_%-VALU_PUSH"
PATH_BTN_PEDIDO = "wnd[0]/usr/btn%_S_EBELN_%_APP_%-VALU_PUSH"
PATH_BTN_FORNEC = "wnd[0]/usr/btn%_S_LIFNR_%_APP_%-VALU_PUSH"
PATH_BTN_REQ = "wnd[0]/usr/btn%_S_BANFN_%_APP_%-VALU_PUSH"
PATH_BTN_CENTRO = "wnd[0]/usr/btn%_S_WERKS_%_APP_%-VALU_PUSH"
PATH_MULTI_CLEAR = "wnd[1]/tbar[0]/btn[16]"
PATH_MULTI_APPLY = "wnd[1]/tbar[0]/btn[8]"
PATH_MULTI_PASTE = "wnd[1]/tbar[0]/btn[24]"
PATH_TAB_INCLUDE = "wnd[1]/usr/tabsTAB_STRIP/tabpSIVA"


# ─── Factory de sessão ────────────────────────────────────────────────────────


def make_session() -> FakeSAPSession:
    """
    Monta FakeSAPSession com os elementos necessários para ML84.

    Registra botões de filtro e elementos do popup MultiSelection.
    set_radio() é suportado nativamente pelo FakeSAPSession.
    """
    session = FakeSAPSession()

    # botões de abertura dos filtros
    session.add(PATH_BTN_FRS, FakeElement())
    session.add(PATH_BTN_PEDIDO, FakeElement())
    session.add(PATH_BTN_FORNEC, FakeElement())
    session.add(PATH_BTN_REQ, FakeElement())
    session.add(PATH_BTN_CENTRO, FakeElement())

    # elementos do popup MultiSelection (wnd[1])
    session.add(PATH_MULTI_CLEAR, FakeElement())
    session.add(PATH_MULTI_APPLY, FakeElement())
    session.add(PATH_MULTI_PASTE, FakeElement())
    session.add(PATH_TAB_INCLUDE, FakeElement())

    return session


def patch_exporter(mocker, html: str):
    """
    Helper: substitui SAPExporter.export_html() pelo HTML fornecido.
    Evita repetição nos testes de execução.
    """
    mocker.patch(
        "sap_automation.transactions.mm.ml84.SAPExporter.export_html",
        return_value=html,
    )


# ─── Testes de status ─────────────────────────────────────────────────────────


class TestML84Status:
    """
    Testes do método status() — mapeamento de strings para ML84Status.

    Aceita strings em português e inglês para facilitar o uso pelo código
    cliente sem precisar importar o enum.
    """

    @pytest.mark.parametrize(
        "valor,esperado",
        [
            ("aceito", ML84Status.ACEITO),
            ("accepted", ML84Status.ACEITO),
            ("nao_aceito", ML84Status.NAO_ACEITO),
            ("não_aceito", ML84Status.NAO_ACEITO),
            ("not_accepted", ML84Status.NAO_ACEITO),
            ("todos", ML84Status.TODOS),
            ("tudo", ML84Status.TODOS),
            ("all", ML84Status.TODOS),
        ],
    )
    def test_string_mapeada_para_status(self, valor, esperado):
        """
        Cada string suportada deve ser mapeada para o ML84Status correto.
        Usa parametrize para cobrir todas as variantes sem duplicar código.
        """
        ml84 = ML84(make_session())
        ml84.status(valor)
        assert ml84._status == esperado

    def test_status_invalido_lanca_value_error(self):
        """String não mapeada deve lançar ValueError."""
        with pytest.raises(ValueError, match="inv[aá]lido"):
            ML84(make_session()).status("qualquer_coisa")

    def test_status_default_e_todos(self):
        """Status padrão deve ser ML84Status.TODOS — retorna todas as FRS."""
        assert ML84(make_session())._status == ML84Status.TODOS

    def test_status_aceita_enum_diretamente(self):
        """status() deve aceitar ML84Status diretamente, não apenas strings."""
        ml84 = ML84(make_session())
        ml84.status(ML84Status.ACEITO)
        assert ml84._status == ML84Status.ACEITO


# ─── Testes de filtros ────────────────────────────────────────────────────────


class TestML84Filtros:
    """
    Testes da configuração e aplicação de filtros.

    Verificamos que:
      1. Os filtros são armazenados corretamente no dict interno
      2. Os botões corretos são pressionados ao aplicar cada filtro
      3. pyperclip.copy() recebe os valores no formato correto
    """

    def test_filter_frs_armazena_valores(self):
        """filter_frs() deve armazenar os valores associados a ML84Filter.FRS."""
        ml84 = ML84(make_session()).filter_frs(["1001904414", "1001904415"])
        assert ml84._filters[ML84Filter.FRS] == ["1001904414", "1001904415"]

    def test_filter_pedidos_armazena_valores(self):
        ml84 = ML84(make_session()).filter_pedidos(["4501926505"])
        assert ml84._filters[ML84Filter.PEDIDO] == ["4501926505"]

    def test_filter_fornecedor_armazena_valores(self):
        ml84 = ML84(make_session()).filter_fornecedor(["9000013096"])
        assert ml84._filters[ML84Filter.FORNECEDOR] == ["9000013096"]

    def test_filter_req_compras_armazena_valores(self):
        ml84 = ML84(make_session()).filter_req_compras(["1234567890"])
        assert ml84._filters[ML84Filter.REQ_COMPRA] == ["1234567890"]

    def test_filter_centros_armazena_valores(self):
        ml84 = ML84(make_session()).filter_centros(["T053"])
        assert ml84._filters[ML84Filter.CENTRO] == ["T053"]

    def test_filtros_podem_ser_encadeados(self):
        """
        Os helpers filter_*() retornam self — interface fluente.
        Três filtros encadeados devem resultar em três entradas no dict.
        """
        ml84 = (
            ML84(make_session())
            .filter_frs(["1001904414"])
            .filter_pedidos(["4501926505"])
            .filter_centros(["T053"])
        )
        assert len(ml84._filters) == 3

    def test_sem_filtros_dict_vazio(self):
        """Sem chamar filter_*(), o dict de filtros deve estar vazio."""
        assert ML84(make_session())._filters == {}

    def test_apply_filters_pressiona_botao_frs(self, mocker):
        """
        _apply_filters() deve pressionar o botão do campo FRS
        para abrir a MultiSelection correspondente.
        """
        mocker.patch("pyperclip.copy")
        session = make_session()
        ML84(session).filter_frs(["1001904414"])._apply_filters()
        session.assert_pressed(PATH_BTN_FRS)

    def test_apply_filters_formato_clipboard(self, mocker):
        """
        Os valores devem ser copiados para o clipboard separados por \\r\\n.

        O SAP espera esse formato ao colar valores na MultiSelection.
        Verificamos que pyperclip.copy() não foi chamado com outro separador.
        """
        mock_copy = mocker.patch("pyperclip.copy")
        ML84(make_session()).filter_frs(["1001904414", "1001904415"])._apply_filters()
        mock_copy.assert_called_once_with("1001904414\r\n1001904415")

    def test_apply_filters_chama_clear_e_apply(self, mocker):
        """
        Para cada filtro, clear (limpar seleção anterior) e apply
        (confirmar nova seleção) devem ser chamados.
        """
        mocker.patch("pyperclip.copy")
        session = make_session()
        ML84(session).filter_frs(["1001904414"])._apply_filters()
        session.assert_pressed(PATH_MULTI_CLEAR)
        session.assert_pressed(PATH_MULTI_APPLY)


# ─── Testes de execução ───────────────────────────────────────────────────────


class TestML84Execucao:
    """
    Testes do fluxo completo de execute() com HTML mockado.

    SAPExporter.export_html() é substituído para retornar o HTML
    da fixture diretamente — sem arquivo temporário, sem SAP real.
    """

    def test_abre_transacao_ml84(self, mocker):
        """start() deve abrir a transação ML84."""
        patch_exporter(mocker, "<html></html>")
        session = make_session()
        ML84(session).run()
        session.assert_transaction_opened("ML84")

    def test_envia_f8_para_executar(self, mocker):
        """_run() deve enviar F8 (vkey 8) para executar a pesquisa."""
        patch_exporter(mocker, "<html></html>")
        session = make_session()
        ML84(session).run()
        session.assert_vkey_sent(8)

    def test_aplica_status_via_set_radio(self, mocker):
        """
        _apply_status() deve chamar session.set_radio() com o path
        do radio button do status configurado.
        """
        patch_exporter(mocker, "<html></html>")
        session = make_session()
        ML84(session).status("aceito").run()
        assert ML84Status.ACEITO in session.radios_set

    def test_go_home_chamado_no_cleanup(self, mocker):
        """go_home() deve ser chamado no cleanup após a execução."""
        patch_exporter(mocker, "<html></html>")
        session = make_session()
        ML84(session).run()
        assert session.home_calls >= 1

    def test_retorna_lista_vazia_quando_html_invalido(self, mocker):
        """
        HTML sem table.list deve retornar [] sem lançar exceção.
        Caso defensivo para HTML mal-formado exportado pelo SAP.
        """
        patch_exporter(mocker, "<html><body>sem tabela</body></html>")
        assert ML84(make_session()).run() == []

    @pytest.mark.skipif(
        not HTML_COM_RESULTADOS.exists(),
        reason="Fixture ml84_com_resultados.htm não encontrada em tests/fixtures/",
    )
    def test_retorna_tres_itens_com_html_real(self, mocker):
        """Com o HTML real de 3 FRS, execute() deve retornar 3 itens."""
        patch_exporter(mocker, HTML_COM_RESULTADOS.read_text(encoding="utf-8"))
        assert len(ML84(make_session()).run()) == 3

    @pytest.mark.skipif(
        not HTML_VAZIO.exists(),
        reason="Fixture ml84_vazio.htm não encontrada em tests/fixtures/",
    )
    def test_retorna_lista_vazia_com_html_vazio(self, mocker):
        """Com HTML de lista vazia, execute() deve retornar []."""
        patch_exporter(mocker, HTML_VAZIO.read_text(encoding="utf-8"))
        assert ML84(make_session()).run() == []


# ─── Testes de resultado ──────────────────────────────────────────────────────


@pytest.mark.skipif(
    not HTML_COM_RESULTADOS.exists(),
    reason="Fixture ml84_com_resultados.htm não encontrada em tests/fixtures/",
)
class TestML84Resultado:
    """
    Testes do conteúdo dos ML84Item retornados com HTML real.
    Garantem que o pipeline completo (execute → export → parse) está correto.
    """

    @pytest.fixture
    def resultado(self, mocker):
        patch_exporter(mocker, HTML_COM_RESULTADOS.read_text(encoding="utf-8"))
        return ML84(make_session()).run()

    def test_retorna_instancias_de_ml84item(self, resultado):
        """Todos os itens devem ser instâncias de ML84Item."""
        from sap_automation.models.mm import ML84Item

        assert all(isinstance(i, ML84Item) for i in resultado)

    def test_numeros_frs_corretos(self, resultado):
        """Os números de FRS devem corresponder ao HTML real."""
        assert {i.frs for i in resultado} == {"1001904414", "1001904415", "1001904416"}

    def test_todos_aceitos(self, resultado):
        """No HTML real, todas as FRS estão aceitas."""
        assert all(i.aceito for i in resultado)

    def test_mesmo_pedido_para_todos(self, resultado):
        """As três FRS pertencem ao mesmo pedido."""
        assert {i.pedido for i in resultado} == {"4501926505"}
