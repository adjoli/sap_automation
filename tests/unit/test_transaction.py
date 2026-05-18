"""
Testes unitários — Transaction (classe base)

Conceito: testando comportamento, não apenas valores
-----------------------------------------------------
Nos testes anteriores (parser, config), verificávamos *valores retornados*
por funções puras. Aqui o foco é diferente: queremos verificar *comportamento*
— quais métodos foram chamados, em que ordem, com quais argumentos.

Para isso usamos dois recursos complementares:

1. pytest-mock (fixture `mocker`)
   Fornece mocker.MagicMock() — objetos "espiões" que registram toda interação:
       session = mocker.MagicMock()
       session.go_home()                  # chamada registrada automaticamente
       session.go_home.assert_called()    # verifica que foi chamado

   Diferente de unittest.mock direto, mocker garante que todos os patches
   são revertidos automaticamente ao fim de cada teste.

2. Subclasses concretas de Transaction
   Como Transaction é ABC (abstract), não pode ser instanciada diretamente.
   Criamos subclasses mínimas que implementam execute() de formas diferentes
   para cada cenário de teste.

Conceito: o padrão AAA (Arrange, Act, Assert)
----------------------------------------------
Cada teste segue três etapas implícitas:
    Arrange  — prepara objetos, mocks e estado inicial
    Act      — executa a ação sendo testada
    Assert   — verifica o resultado ou comportamento esperado

Conceito: pytest.raises com match
----------------------------------
Quando o comportamento correto é lançar uma exceção específica:
    with pytest.raises(ValueError, match="mensagem esperada"):
        codigo_que_deve_falhar()

O parâmetro match verifica a mensagem via regex — garante que a exceção
certa está sendo propagada, não apenas qualquer ValueError.

Execução:
    pytest tests/unit/test_transaction.py -v
"""

import pytest

from sap_automation.transactions.base import Transaction

# ─── Subclasses de teste ──────────────────────────────────────────────────────
# Como Transaction é abstrata, criamos implementações mínimas para cada cenário.
# Isso é preferível a mockar a própria Transaction, pois exercita a herança
# real — exatamente como ML81N, ML84 e ME23N fazem em produção.


class TransacaoSimples(Transaction):
    """
    Implementação mínima que retorna um valor fixo.
    Usada para testar o fluxo feliz do ciclo de vida.
    """

    RETORNO = {"numero": "4500012345", "status": "ok"}

    def execute(self):
        return self.RETORNO


class TransacaoComStart(Transaction):
    """
    Implementação que registra chamadas a start() e execute().
    Usada para verificar a ordem de execução do ciclo de vida.
    """

    def __init__(self, session):
        super().__init__(session)
        self.chamadas = []

    def start(self):
        self.chamadas.append("start")

    def execute(self):
        self.chamadas.append("execute")
        return "resultado"


class TransacaoComFalha(Transaction):
    """
    Implementação que lança exceção em execute().
    Usada para verificar que cleanup() é chamado mesmo em caso de erro.
    """

    def execute(self):
        raise ValueError("Erro simulado na execução")


class TransacaoComFalhaNoStart(Transaction):
    """
    Implementação que lança exceção em start().
    Usada para verificar que cleanup() cobre falhas em start() também.
    """

    def start(self):
        raise RuntimeError("Erro simulado no start")

    def execute(self):
        return "nunca chega aqui"


# ─── Testes ───────────────────────────────────────────────────────────────────


class TestTransactionCicloDeVida:
    """
    Testes do ciclo de vida definido em Transaction.run().

    O ciclo esperado é:
        go_home() → start() → execute() → cleanup() [sempre, via finally]

    O finally garante que cleanup() é chamado independente do resultado
    de execute() — seja sucesso ou exceção.
    """

    def test_run_retorna_resultado_de_execute(self, mocker):
        """
        run() deve retornar exatamente o que execute() retornar.

        Transaction.run() é o único ponto de entrada público.
        O código cliente recebe o retorno de run() — que deve ser
        transparentemente o retorno de execute().
        """
        session = mocker.MagicMock()
        tx = TransacaoSimples(session)

        resultado = tx.run()

        assert resultado == TransacaoSimples.RETORNO

    def test_run_chama_go_home_antes_de_start(self, mocker):
        """
        go_home() deve ser chamado antes de start() e execute().

        Garante que o SAP está no Easy Access antes de abrir qualquer
        transação — evita comportamento inesperado se outra tela estiver aberta.
        """
        session = mocker.MagicMock()
        tx = TransacaoComStart(session)

        tx.run()

        session.go_home.assert_called()
        assert tx.chamadas[0] == "start"
        assert tx.chamadas[1] == "execute"

    def test_run_chama_start_antes_de_execute(self, mocker):
        """
        start() deve ser chamado antes de execute().

        Usamos self.chamadas para registrar a sequência real de execução
        em vez de depender de mocks, o que torna o teste mais legível.
        """
        session = mocker.MagicMock()
        tx = TransacaoComStart(session)

        tx.run()

        assert tx.chamadas == ["start", "execute"]

    def test_cleanup_chamado_apos_execute_com_sucesso(self, mocker):
        """
        cleanup() deve ser chamado após execute() bem-sucedido.

        cleanup() chama go_home() — verificamos indiretamente pelo número
        de chamadas: 1 no início do run() + 1 no cleanup() = 2 total.
        """
        session = mocker.MagicMock()
        tx = TransacaoSimples(session)

        tx.run()

        assert session.go_home.call_count == 2

    def test_cleanup_chamado_mesmo_quando_execute_falha(self, mocker):
        """
        cleanup() deve ser chamado mesmo quando execute() lança exceção.

        Este é o comportamento mais crítico do ciclo de vida — garante que
        o SAP nunca fica preso em uma tela intermediária após um erro.

        Implementado via try/finally em Transaction.run().
        """
        session = mocker.MagicMock()
        tx = TransacaoComFalha(session)

        with pytest.raises(ValueError):
            tx.run()

        session.go_home.assert_called()

    def test_excecao_de_execute_e_propagada(self, mocker):
        """
        Exceções lançadas por execute() devem ser propagadas ao chamador.

        O finally em run() não engole exceções — apenas garante que
        cleanup() seja executado antes de propagá-las.

        O parâmetro match= verifica a mensagem via regex, garantindo que
        a exceção correta está sendo propagada.
        """
        session = mocker.MagicMock()
        tx = TransacaoComFalha(session)

        with pytest.raises(ValueError, match="Erro simulado na execução"):
            tx.run()

    def test_cleanup_chamado_mesmo_quando_start_falha(self, mocker):
        """
        cleanup() deve ser chamado mesmo quando start() lança exceção.

        O try/finally envolve todo o bloco incluindo start(), portanto
        falhas em start() também acionam o cleanup.
        """
        session = mocker.MagicMock()
        tx = TransacaoComFalhaNoStart(session)

        with pytest.raises(RuntimeError):
            tx.run()

        session.go_home.assert_called()

    def test_excecao_de_start_e_propagada(self, mocker):
        """
        Exceções lançadas por start() devem ser propagadas ao chamador.
        """
        session = mocker.MagicMock()
        tx = TransacaoComFalhaNoStart(session)

        with pytest.raises(RuntimeError, match="Erro simulado no start"):
            tx.run()


class TestTransactionCleanup:
    """
    Testes do método cleanup() isoladamente.

    cleanup() tem um comportamento especial: engole exceções de go_home().
    Isso evita que um erro ao voltar ao Easy Access mascare o erro original
    de execute() — a exceção que o usuário precisa ver é a do execute().
    """

    def test_cleanup_chama_go_home(self, mocker):
        """cleanup() deve chamar session.go_home()."""
        session = mocker.MagicMock()
        tx = TransacaoSimples(session)

        tx.cleanup()

        session.go_home.assert_called_once()

    def test_cleanup_nao_propaga_excecao_de_go_home(self, mocker):
        """
        cleanup() não deve propagar exceções de go_home().

        Cenário: go_home() falha (ex: SAP GUI foi fechado durante a execução).
        O cleanup deve falhar silenciosamente — não queremos mascarar a exceção
        original de execute() com um erro de cleanup.

        mocker.MagicMock() com side_effect simula o erro de go_home.
        """
        session = mocker.MagicMock()
        session.go_home.side_effect = Exception("SAP GUI não responde")
        tx = TransacaoSimples(session)

        tx.cleanup()  # não deve lançar exceção

    def test_cleanup_e_idempotente(self, mocker):
        """
        cleanup() pode ser chamado múltiplas vezes sem efeitos colaterais.

        run() chama go_home() no início e cleanup() no finally — ambos
        chamam go_home(). Não deve haver problema em chamar go_home() 2x.
        """
        session = mocker.MagicMock()
        tx = TransacaoSimples(session)

        tx.cleanup()
        tx.cleanup()

        assert session.go_home.call_count == 2


class TestTransactionStart:
    """
    Testes do método start().

    start() é opcional — a implementação padrão é um no-op (pass).
    Subclasses sobrescrevem quando precisam abrir uma transação específica.
    """

    def test_start_padrao_e_noop(self, mocker):
        """
        A implementação padrão de start() não deve fazer nada.

        Subclasses que não precisam de navegação especial herdam esse
        comportamento sem precisar sobrescrever o método.
        """
        session = mocker.MagicMock()
        tx = TransacaoSimples(session)

        tx.start()

        session.start_transaction.assert_not_called()
        session.go_home.assert_not_called()

    def test_start_pode_ser_sobrescrito(self, mocker):
        """
        Subclasses devem conseguir sobrescrever start() para abrir transações.

        Verifica o padrão usado por ML81N, ML84, ME23N — que chamam
        session.start_transaction() em start().
        """
        session = mocker.MagicMock()

        class TransacaoComCodigo(Transaction):
            def start(self):
                self.session.start_transaction("ML84")

            def execute(self):
                return []

        tx = TransacaoComCodigo(session)
        tx.start()

        session.start_transaction.assert_called_once_with("ML84")


class TestTransactionAbstrata:
    """
    Testes do contrato abstrato — execute() deve ser obrigatoriamente implementado.
    """

    def test_nao_pode_instanciar_sem_execute(self, mocker):
        """
        Transaction é abstrata — instanciar sem implementar execute() deve
        lançar TypeError.

        @abstractmethod em execute() garante que subclasses que esquecerem
        de implementá-lo falhem na instanciação, não em tempo de execução.
        """
        session = mocker.MagicMock()

        class TransacaoSemExecute(Transaction):
            pass

        with pytest.raises(TypeError):
            TransacaoSemExecute(session)

    def test_pode_instanciar_com_execute_implementado(self, mocker):
        """
        Subclasse com execute() implementado deve ser instanciável normalmente.
        """
        session = mocker.MagicMock()
        tx = TransacaoSimples(session)
        assert tx is not None
        assert tx.session is session
