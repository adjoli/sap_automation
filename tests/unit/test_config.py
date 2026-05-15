"""
Testes de configuração — SAPConfig

Conceito: o que estamos testando aqui?
---------------------------------------
SAPConfig é o portão de entrada da biblioteca. Ela lê variáveis de ambiente,
valida se as obrigatórias estão presentes e fornece os valores corretos para
cada ambiente (PRD/QAS).

Testar a configuração é importante porque:
  - Erros de config falham silenciosamente se não validados (ex: senha errada
    carregada sem exceção, só descobre na conexão com o SAP).
  - A lógica de seleção de senha por ambiente (PRD vs QAS) é não-trivial.
  - O comportamento de fallback dos valores default precisa ser verificado.

Ferramenta: monkeypatch (pytest)
----------------------------------
monkeypatch.setenv() define variáveis de ambiente apenas durante o teste e
as restaura automaticamente ao final — sem efeito colateral entre testes.
É preferível a os.environ[...] = ... que pode vazar entre testes se o teste
falhar antes de restaurar.

Organização por classe
-----------------------
Agrupamos os testes em classes por contexto (carregamento, validação, nomes
de conexão). Isso não muda o comportamento do pytest, mas melhora a leitura
e o agrupamento nos relatórios.

Execução:
    pytest tests/unit/test_config.py -v
"""

import pytest

from sap_automation.client.config import SAPConfig
from sap_automation.exceptions import ConfigError


def config_env_base(monkeypatch, env="PRD"):
    """
    Helper: configura variáveis mínimas válidas para um ambiente.
    Evita repetição nos testes — não é uma fixture, é uma função auxiliar.
    """
    monkeypatch.setenv("SAP_USER", "usuario_teste")
    monkeypatch.setenv("SAP_ENV", env)
    if env == "PRD":
        monkeypatch.setenv("SAP_PASSWD_PRD", "senha_prd")
    else:
        monkeypatch.setenv("SAP_PASSWD_QAS", "senha_qas")


class TestCarregamento:
    """Testes de carregamento correto das variáveis de ambiente."""

    def test_carrega_usuario(self, monkeypatch):
        """SAP_USER deve ser lido corretamente."""
        config_env_base(monkeypatch)
        config = SAPConfig.from_env()
        assert config.user == "usuario_teste"

    def test_carrega_senha_prd(self, monkeypatch):
        """SAP_PASSWD_PRD deve ser usado quando SAP_ENV=PRD."""
        config_env_base(monkeypatch, env="PRD")
        config = SAPConfig.from_env()
        assert config.password == "senha_prd"

    def test_carrega_senha_qas(self, monkeypatch):
        """SAP_PASSWD_QAS deve ser usado quando SAP_ENV=QAS."""
        config_env_base(monkeypatch, env="QAS")
        config = SAPConfig.from_env()
        assert config.password == "senha_qas"

    def test_carrega_ambiente_prd(self, monkeypatch):
        """SAP_ENV=PRD deve definir environment como 'PRD'."""
        config_env_base(monkeypatch, env="PRD")
        config = SAPConfig.from_env()
        assert config.environment == "PRD"

    def test_carrega_ambiente_qas(self, monkeypatch):
        """SAP_ENV=QAS deve definir environment como 'QAS'."""
        config_env_base(monkeypatch, env="QAS")
        config = SAPConfig.from_env()
        assert config.environment == "QAS"

    def test_ambiente_default_e_prd(self, monkeypatch):
        """
        Quando SAP_ENV não está definido, o ambiente padrão deve ser PRD.

        Comportamento seguro: ausência de configuração explícita não deve
        apontar para QAS (ambiente de testes) por engano.
        """
        monkeypatch.setenv("SAP_USER", "usuario_teste")
        monkeypatch.setenv("SAP_PASSWD_PRD", "senha_prd")
        monkeypatch.delenv("SAP_ENV", raising=False)

        config = SAPConfig.from_env()
        assert config.environment == "PRD"

    def test_ambiente_convertido_para_maiusculo(self, monkeypatch):
        """
        SAP_ENV em minúsculo deve ser normalizado para maiúsculo.

        Evita que 'prd' e 'PRD' sejam tratados como ambientes diferentes.
        """
        monkeypatch.setenv("SAP_USER", "usuario_teste")
        monkeypatch.setenv("SAP_ENV", "prd")
        monkeypatch.setenv("SAP_PASSWD_PRD", "senha_prd")

        config = SAPConfig.from_env()
        assert config.environment == "PRD"


class TestValorDefault:
    """Testes dos valores default para variáveis opcionais."""

    def test_client_default(self, monkeypatch):
        """SAP_CLIENT deve ter valor default '400'."""
        config_env_base(monkeypatch)
        monkeypatch.delenv("SAP_CLIENT", raising=False)
        config = SAPConfig.from_env()
        assert config.client == "400"

    def test_language_default(self, monkeypatch):
        """SAP_LANG deve ter valor default 'PT'."""
        config_env_base(monkeypatch)
        monkeypatch.delenv("SAP_LANG", raising=False)
        config = SAPConfig.from_env()
        assert config.language == "PT"

    def test_client_customizado(self, monkeypatch):
        """SAP_CLIENT customizado deve sobrescrever o default."""
        config_env_base(monkeypatch)
        monkeypatch.setenv("SAP_CLIENT", "300")
        config = SAPConfig.from_env()
        assert config.client == "300"

    def test_language_customizado(self, monkeypatch):
        """SAP_LANG customizado deve sobrescrever o default."""
        config_env_base(monkeypatch)
        monkeypatch.setenv("SAP_LANG", "EN")
        config = SAPConfig.from_env()
        assert config.language == "EN"


class TestNomesConexao:
    """
    Testes dos nomes de conexão SAP (usados pelo SAPConnection para
    localizar a conexão correta no SAP Logon).
    """

    def test_nome_conexao_prd_default(self, monkeypatch):
        """
        Quando SAP_CONN_NAME_PRD não está definido, deve usar o nome padrão.
        """
        config_env_base(monkeypatch, env="PRD")
        monkeypatch.delenv("SAP_CONN_NAME_PRD", raising=False)
        config = SAPConfig.from_env()
        assert config.sap_conn_name_prd == "F04 - SAP Scripting Transpetro PRD"

    def test_nome_conexao_qas_default(self, monkeypatch):
        """
        Quando SAP_CONN_NAME_QAS não está definido, deve usar o nome padrão.
        """
        config_env_base(monkeypatch, env="QAS")
        monkeypatch.delenv("SAP_CONN_NAME_QAS", raising=False)
        config = SAPConfig.from_env()
        assert config.sap_conn_name_qas == "TEQ - SAP ECC Transpetro QAS"

    def test_nome_conexao_prd_customizado(self, monkeypatch):
        """SAP_CONN_NAME_PRD customizado deve sobrescrever o default."""
        config_env_base(monkeypatch, env="PRD")
        monkeypatch.setenv("SAP_CONN_NAME_PRD", "MINHA CONEXAO PRD")
        config = SAPConfig.from_env()
        assert config.sap_conn_name_prd == "MINHA CONEXAO PRD"

    def test_nome_conexao_qas_customizado(self, monkeypatch):
        """SAP_CONN_NAME_QAS customizado deve sobrescrever o default."""
        config_env_base(monkeypatch, env="QAS")
        monkeypatch.setenv("SAP_CONN_NAME_QAS", "MINHA CONEXAO QAS")
        config = SAPConfig.from_env()
        assert config.sap_conn_name_qas == "MINHA CONEXAO QAS"


class TestValidacao:
    """
    Testes de validação — SAPConfig.validate() deve lançar ConfigError
    quando variáveis obrigatórias estão ausentes.

    Conceito: testes de exceção com pytest.raises
    ----------------------------------------------
    pytest.raises(ExceptionType) é um context manager que verifica se
    a exceção esperada é lançada. O teste PASSA se a exceção ocorrer,
    e FALHA se não ocorrer ou se ocorrer outro tipo de exceção.

    Podemos também inspecionar a mensagem da exceção via excinfo.value:
        with pytest.raises(ConfigError) as excinfo:
            SAPConfig.from_env()
        assert "SAP_USER" in str(excinfo.value)
    """

    def test_falha_sem_usuario(self, monkeypatch):
        """ConfigError deve ser lançado quando SAP_USER está ausente."""
        monkeypatch.delenv("SAP_USER", raising=False)
        monkeypatch.setenv("SAP_ENV", "PRD")
        monkeypatch.setenv("SAP_PASSWD_PRD", "senha")

        with pytest.raises(ConfigError):
            SAPConfig.from_env()

    def test_falha_sem_senha_prd(self, monkeypatch):
        """ConfigError deve ser lançado quando SAP_PASSWD_PRD está ausente em ambiente PRD."""
        monkeypatch.setenv("SAP_USER", "usuario")
        monkeypatch.setenv("SAP_ENV", "PRD")
        monkeypatch.delenv("SAP_PASSWD_PRD", raising=False)
        monkeypatch.delenv("SAP_PASSWD_QAS", raising=False)

        with pytest.raises(ConfigError):
            SAPConfig.from_env()

    def test_falha_sem_senha_qas(self, monkeypatch):
        """ConfigError deve ser lançado quando SAP_PASSWD_QAS está ausente em ambiente QAS."""
        monkeypatch.setenv("SAP_USER", "usuario")
        monkeypatch.setenv("SAP_ENV", "QAS")
        monkeypatch.delenv("SAP_PASSWD_QAS", raising=False)

        with pytest.raises(ConfigError):
            SAPConfig.from_env()

    def test_mensagem_erro_menciona_variavel_ausente(self, monkeypatch):
        """
        A mensagem do ConfigError deve mencionar qual variável está ausente.

        Facilita o diagnóstico quando a configuração falha em produção.
        """
        monkeypatch.setenv("SAP_USER", "usuario")
        monkeypatch.setenv("SAP_ENV", "PRD")
        monkeypatch.delenv("SAP_PASSWD_PRD", raising=False)

        with pytest.raises(ConfigError) as excinfo:
            SAPConfig.from_env()

        assert "SAP_PASSWD_PRD" in str(excinfo.value)

    def test_mensagem_erro_menciona_usuario_ausente(self, monkeypatch):
        """A mensagem do ConfigError deve mencionar SAP_USER quando ausente."""
        monkeypatch.delenv("SAP_USER", raising=False)
        monkeypatch.setenv("SAP_ENV", "PRD")
        monkeypatch.setenv("SAP_PASSWD_PRD", "senha")

        with pytest.raises(ConfigError) as excinfo:
            SAPConfig.from_env()

        assert "SAP_USER" in str(excinfo.value)

    def test_senha_prd_nao_usada_no_qas(self, monkeypatch):
        """
        SAP_PASSWD_PRD não deve ser aceita quando SAP_ENV=QAS.

        Garante que o código não usa a senha errada por engano ao trocar de ambiente.
        """
        monkeypatch.setenv("SAP_USER", "usuario")
        monkeypatch.setenv("SAP_ENV", "QAS")
        monkeypatch.setenv(
            "SAP_PASSWD_PRD", "senha_prd"
        )  # existe, mas é do ambiente errado
        monkeypatch.delenv("SAP_PASSWD_QAS", raising=False)

        with pytest.raises(ConfigError):
            SAPConfig.from_env()
