"""
Testes unitários — ML81N (Consulta de FRS)

Conceito: testando transações com session fake
-----------------------------------------------
Transações SAP dependem de SAPSession para toda interação com o programa.
Para testá-las sem o SAP instalado, substituímos SAPSession por FakeSAPSession
— um fake que implementa a mesma interface mas opera em memória.

O teste configura o cenário (quais elementos existem, quais valores retornam)
e verifica dois aspectos:

  1. Resultado: o objeto FRS retornado tem os valores corretos
  2. Comportamento: a transação navegou pelas abas certas, abriu a transação
     correta, enviou as teclas esperadas

Conceito: fixtures de pytest
------------------------------
Fixtures são funções que preparam recursos reutilizáveis entre testes.
Declaradas com @pytest.fixture, são injetadas como parâmetros nos testes.

Usamos fixtures para montar o FakeSAPSession com os elementos da ML81N —
evitando repetição e mantendo cada teste focado no que está sendo verificado.

Conceito: parametrize
----------------------
@pytest.mark.parametrize permite rodar o mesmo teste com múltiplas entradas:
    @pytest.mark.parametrize("icone,esperado", [
        ("S_TL_G", True),
        ("S_TL_R", False),
    ])
    def test_liberada(icone, esperado, session_ml81n):
        ...

Isso é mais conciso do que duplicar testes e torna mais fácil adicionar
novos casos sem modificar a lógica do teste.

Execução:
    pytest tests/unit/test_ml81n.py -v
"""

import pytest

from sap_automation.transactions.mm.ml81n import ML81N
from tests.fixtures.sap_fake import (
    FakeElement,
    FakeSAPSession,
    FakeTabElement,
    FakeTable,
    FakeTabStrip,
)

# ─── Constantes dos caminhos SAP ─────────────────────────────────────────────
# Centralizar os paths evita typos e facilita manutenção — se um path mudar
# no código de produção, só precisa atualizar aqui.

PATH_TABSTRIP = "wnd[0]/usr/tabsTAB_HEADER"
PATH_PEDIDO = "wnd[0]/usr/txtRM11R-BSTNR"
PATH_TEXTO_BREVE = "wnd[0]/usr/txtESSR-TXZ01"
PATH_ACEITE = "wnd[0]/usr/txtRM11R-KZABN_TXT"
PATH_BTN_BUSCA = "wnd[0]/tbar[1]/btn[17]"
PATH_INPUT_FRS = "wnd[1]/usr/ctxtRM11R-LBLNI"
PATH_CATEGORIA = (
    "wnd[0]/usr/tabsTAB_HEADER/tabpREGG/ssubSUB_HEADER:SAPLMLSR:0410/cmbESSR-KNTTP"
)
PATH_RESP_INTERNO = (
    "wnd[0]/usr/tabsTAB_HEADER/tabpREGG/ssubSUB_HEADER:SAPLMLSR:0410/txtESSR-SBNAMAG"
)
PATH_RESP_EXTERNO = (
    "wnd[0]/usr/tabsTAB_HEADER/tabpREGG/ssubSUB_HEADER:SAPLMLSR:0410/txtESSR-SBNAMAN"
)
PATH_VALOR = (
    "wnd[0]/usr/tabsTAB_HEADER/tabpREGW/ssubSUB_VALUES:SAPLMLSR:0450/txtESSR-LWERT"
)
PATH_BTN_FISCAIS = (
    "wnd[0]/usr/tabsTAB_HEADER/tabpESCR/ssubSUBUSCR:SAPLXMLU:0399/btnBT_GERFIS"
)
PATH_TABELA_FISC = "wnd[1]/usr/tblSAPLZGFMM_GERFISTC_FISCAIS_NB1"
PATH_POPUP_ERRO = "wnd[2]/usr/txtMESSTXT1"
PATH_POPUP_FISC = "wnd[1]"


# ─── Factories de sessão ──────────────────────────────────────────────────────
# Funções que montam FakeSAPSession para diferentes cenários de teste.
# Usar factories em vez de fixtures com escopo amplo dá mais controle
# sobre o que cada teste precisa ver.


def make_session(
    numero_frs: str = "1001904414",
    pedido: str = "4501926505",
    texto_breve: str = "Medição fevereiro/26",
    categoria: str = "D",
    resp_interno: str = "JOAO.SILVA",
    resp_externo: str = "MARIA SANTOS",
    valor: str = "18.407,49",
    aceito: bool = True,
    fiscais: list[dict] | None = None,
    frs_existe: bool = True,
) -> FakeSAPSession:
    """
    Monta uma FakeSAPSession com todos os elementos necessários para ML81N.

    Parâmetros permitem configurar diferentes cenários sem duplicar código.
    """
    if fiscais is None:
        fiscais = [
            {"Sel.": "X", "Chave": "98765", "Nome": "JOAO SILVA"},
        ]

    session = FakeSAPSession()

    # elementos de navegação
    session.add(PATH_BTN_BUSCA, FakeElement())
    session.add(PATH_INPUT_FRS, FakeElement())

    # se frs_existe=False, o popup de erro aparece
    if not frs_existe:
        session.add(PATH_POPUP_ERRO, FakeElement("FRS não encontrada"))

    # campos do cabeçalho
    session.add(PATH_PEDIDO, FakeElement(pedido))
    session.add(PATH_TEXTO_BREVE, FakeElement(texto_breve))
    session.add(
        PATH_ACEITE,
        FakeElement(icon_name="S_TL_G" if aceito else "S_TL_R"),
    )

    # campos das abas
    session.add(PATH_CATEGORIA, FakeElement(categoria))
    session.add(PATH_RESP_INTERNO, FakeElement(resp_interno))
    session.add(PATH_RESP_EXTERNO, FakeElement(resp_externo))
    session.add(PATH_VALOR, FakeElement(valor))
    session.add(PATH_BTN_FISCAIS, FakeElement())

    # tabstrip, abas e tabela de fiscais
    tab_names = ["DdsBásicos", "Vals.", "Dados adic."]
    tab_suffixes = ["tabpREGG", "tabpREGW", "tabpESCR"]
    tabstrip = FakeTabStrip(tab_names)
    session.add_tabstrip(PATH_TABSTRIP, tabstrip)

    for suffix, name in zip(tab_suffixes, tab_names):
        session.add(f"{PATH_TABSTRIP}/{suffix}", FakeTabElement(tabstrip, name))

    session.add_table(PATH_TABELA_FISC, FakeTable(fiscais))

    return session


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def session():
    """Sessão padrão com FRS existente e todos os dados preenchidos."""
    return make_session()


@pytest.fixture
def frs(session):
    """FRS retornada por ML81N.run() com a sessão padrão."""
    tx = ML81N(session, "1001904414")
    return tx.run()


# ─── Testes de resultado ──────────────────────────────────────────────────────


class TestML81NResultado:
    """
    Testes do objeto FRS retornado por ML81N.run().

    Verificam que os campos do modelo foram populados corretamente
    a partir dos valores configurados na FakeSAPSession.
    """

    def test_retorna_objeto_frs(self, frs):
        """run() deve retornar um objeto FRS, não None ou dict."""
        from sap_automation.models.mm import FRS

        assert isinstance(frs, FRS)

    def test_numero_frs(self, frs):
        """O número da FRS deve ser o passado no construtor."""
        assert frs.numero == "1001904414"

    def test_pedido(self, frs):
        """O número do pedido deve ser lido de PATH_PEDIDO."""
        assert frs.pedido == "4501926505"

    def test_texto_breve(self, frs):
        """O texto breve deve ser lido de PATH_TEXTO_BREVE."""
        assert frs.texto_breve == "Medição fevereiro/26"

    def test_categoria(self, frs):
        """A categoria deve ser lida da aba DdsBásicos."""
        assert frs.categoria == "D"

    def test_resp_interno(self, frs):
        """O responsável interno deve ser lido da aba DdsBásicos."""
        assert frs.resp_interno == "JOAO.SILVA"

    def test_resp_externo(self, frs):
        """O responsável externo deve ser lido da aba DdsBásicos."""
        assert frs.resp_externo == "MARIA SANTOS"

    def test_valor_convertido(self, frs):
        """
        O valor no formato BR (18.407,49) deve ser convertido para float.
        O field_validator do modelo FRS faz essa conversão.
        """
        assert frs.valor == pytest.approx(18407.49)

    def test_fiscais_populados(self, frs):
        """A lista de fiscais deve conter os fiscais com Sel.='X'."""
        assert len(frs.fiscais) == 1
        assert frs.fiscais[0].chave == "98765"
        assert frs.fiscais[0].nome == "JOAO SILVA"


# ─── Testes de status de liberação ───────────────────────────────────────────


class TestML81NLiberacao:
    """Testes do campo liberada — detectado pelo IconName do campo de aceite."""

    @pytest.mark.parametrize(
        "icon_name,esperado",
        [
            ("S_TL_G", True),  # semáforo verde = liberada
            ("S_TL_R", False),  # semáforo vermelho = não liberada
            ("", False),  # sem ícone = não liberada
        ],
    )
    def test_liberada_por_icone(self, icon_name, esperado):
        """
        liberada deve ser True apenas quando IconName == 'S_TL_G'.

        Conceito: parametrize
        ----------------------
        Em vez de três testes separados com lógica duplicada, usamos
        @parametrize para rodar o mesmo teste com diferentes entradas.
        Cada par (icon_name, esperado) gera um caso de teste independente.
        """
        session = make_session(aceito=(icon_name == "S_TL_G"))
        # ajusta o ícone manualmente para casos intermediários
        session._elements[PATH_ACEITE].IconName = icon_name

        frs = ML81N(session, "1001904414").run()
        assert frs.liberada == esperado


# ─── Testes de fiscais ────────────────────────────────────────────────────────


class TestML81NFiscais:
    """Testes da leitura de fiscais — filtragem por checkbox Sel.."""

    def test_fiscal_nao_selecionado_e_ignorado(self):
        """
        Fiscais com Sel.='' (checkbox vazio) não devem aparecer na lista.
        Apenas fiscais com Sel.='X' (selecionados) são responsáveis pela FRS.
        """
        session = make_session(
            fiscais=[
                {"Sel.": "X", "Chave": "11111", "Nome": "Fiscal Ativo"},
                {"Sel.": "", "Chave": "22222", "Nome": "Fiscal Inativo"},
            ]
        )
        frs = ML81N(session, "1001904414").run()

        assert len(frs.fiscais) == 1
        assert frs.fiscais[0].chave == "11111"

    def test_sem_fiscais_retorna_lista_vazia(self):
        """Quando nenhum fiscal está selecionado, fiscais deve ser []."""
        session = make_session(
            fiscais=[
                {"Sel.": "", "Chave": "11111", "Nome": "Fiscal Inativo"},
            ]
        )
        frs = ML81N(session, "1001904414").run()
        assert frs.fiscais == []

    def test_multiplos_fiscais_selecionados(self):
        """Todos os fiscais com Sel.='X' devem aparecer na lista."""
        session = make_session(
            fiscais=[
                {"Sel.": "X", "Chave": "11111", "Nome": "Fiscal A"},
                {"Sel.": "X", "Chave": "22222", "Nome": "Fiscal B"},
                {"Sel.": "", "Chave": "33333", "Nome": "Fiscal C"},
            ]
        )
        frs = ML81N(session, "1001904414").run()

        assert len(frs.fiscais) == 2
        chaves = {f.chave for f in frs.fiscais}
        assert chaves == {"11111", "22222"}

    def test_erro_na_tabela_retorna_lista_vazia(self, mocker):
        """
        Se TableControl lançar exceção, fiscais deve ser [] sem propagar o erro.

        A ML81N trata erros na leitura de fiscais com try/except para não
        interromper a extração dos demais dados da FRS.

        Usamos mocker.patch para forçar a exceção no TableControl.to_list().
        """
        session = make_session()
        mocker.patch(
            "sap_automation.transactions.mm.ml81n.TableControl.to_list",
            side_effect=Exception("Tabela não encontrada"),
        )
        frs = ML81N(session, "1001904414").run()
        assert frs.fiscais == []


# ─── Testes de navegação ──────────────────────────────────────────────────────


class TestML81NNavegacao:
    """
    Testes de comportamento — verifica que a transação navegou corretamente.

    Esses testes complementam os de resultado: mesmo que o FRS esteja correto,
    precisamos garantir que a transação não está tomando atalhos incorretos
    que poderiam falhar com dados diferentes.
    """

    def test_abre_transacao_ml81n(self, session):
        """start() deve abrir a transação ML81N via start_transaction()."""
        ML81N(session, "1001904414").run()
        session.assert_transaction_opened("ML81N")

    def test_define_numero_frs_no_campo(self, session):
        """O número da FRS deve ser escrito no campo de busca."""
        ML81N(session, "1001904414").run()
        session.assert_text_set(PATH_INPUT_FRS, "1001904414")

    def test_pressiona_botao_busca(self, session):
        """O botão de busca (btn[17]) deve ser pressionado."""
        ML81N(session, "1001904414").run()
        session.assert_pressed(PATH_BTN_BUSCA)

    def test_envia_enter_apos_digitar_frs(self, session):
        """Enter (vkey 0) deve ser enviado após digitar o número da FRS."""
        ML81N(session, "1001904414").run()
        session.assert_vkey_sent(0)

    def test_navega_pelas_tres_abas(self, session):
        """
        A transação deve navegar pelas abas DdsBásicos, Vals. e Dados adic.
        nessa ordem.
        """
        ML81N(session, "1001904414").run()
        tabstrip = session._tabstrips[PATH_TABSTRIP]
        assert tabstrip.was_selected("DdsBásicos")
        assert tabstrip.was_selected("Vals.")
        assert tabstrip.was_selected("Dados adic.")

    def test_pressiona_botao_fiscais(self, session):
        """O botão de fiscais deve ser pressionado na aba Dados adic."""
        ML81N(session, "1001904414").run()
        session.assert_pressed(PATH_BTN_FISCAIS)

    def test_go_home_chamado_no_cleanup(self, session):
        """go_home() deve ser chamado ao menos uma vez (no cleanup)."""
        ML81N(session, "1001904414").run()
        assert session.home_calls >= 1


# ─── Testes de validação ──────────────────────────────────────────────────────


class TestML81NValidacao:
    """Testes das regras de validação do construtor e execução."""

    def test_frs_vazia_lanca_value_error(self):
        """
        Instanciar ML81N com FRS vazia deve lançar ValueError.
        Validação no construtor — falha rápida antes de tentar acessar o SAP.
        """
        session = make_session()
        with pytest.raises(ValueError, match="FRS é obrigatória"):
            ML81N(session, "")

    def test_frs_inexistente_lanca_value_error(self):
        """
        Se o SAP exibir o popup de erro (wnd[2]), deve ser lançado ValueError.
        Simula o caso de FRS que não existe no sistema.
        """
        session = make_session(frs_existe=False)
        with pytest.raises(ValueError, match="não existe"):
            ML81N(session, "9999999999").run()
