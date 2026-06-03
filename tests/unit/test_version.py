"""
Testes de versão — sap_automation

Conceito: o que estamos testando aqui?
---------------------------------------
A versão da aplicação tem uma única fonte de verdade: o campo `version`
em pyproject.toml. O `importlib.metadata.version()` lê esse valor em
tempo de execução a partir dos metadados do pacote instalado.

Esses testes garantem três coisas:
  1. O pacote está instalado corretamente no ambiente (importável).
  2. A versão segue o formato semântico esperado (MAJOR.MINOR.PATCH).
  3. A versão está acessível pelo caminho público correto (`sap_automation.__version__`
     e `SAP.version`), não apenas internamente.

Conceito: pytest-mock vs unittest.mock
----------------------------------------
Usamos pytest-mock (fixture `mocker`) em vez de unittest.mock diretamente.

Vantagens práticas:
  - Patches são revertidos automaticamente ao fim de cada teste, sem
    necessidade de `with patch(...)` ou `@patch` decorators.
  - `mocker.patch()` é mais conciso e integra melhor com o relatório do pytest.
  - `mocker.spy()` permite espionar métodos reais sem substituí-los.

pytest-mock é um wrapper sobre unittest.mock — MagicMock, call, side_effect
funcionam exatamente igual. O conhecimento é 100% transferível.

Execução:
    pytest tests/unit/test_version.py -v
"""

import re

import sap_automation
from sap_automation.sap import SAP

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+")


class TestVersion:
    """Testes da versão do pacote sap_automation."""

    def test_version_esta_definida(self):
        """
        __version__ deve existir e não ser None.

        Verifica que o atributo foi definido em __init__.py e que o pacote
        está instalado corretamente (importlib.metadata conseguiu ler os metadados).
        """
        assert sap_automation.__version__ is not None

    def test_version_e_string(self):
        """
        __version__ deve ser uma string.

        importlib.metadata.version() sempre retorna str. Se for outro tipo,
        algo foi redefinido incorretamente.
        """
        assert isinstance(sap_automation.__version__, str)

    def test_version_nao_e_string_vazia(self):
        """
        __version__ não deve ser string vazia.

        Uma string vazia indicaria que o pacote foi instalado sem metadados
        ou que o valor foi sobrescrito erroneamente.
        """
        assert sap_automation.__version__.strip() != ""

    def test_version_segue_formato_semver(self):
        """
        __version__ deve seguir o formato semântico MAJOR.MINOR.PATCH.

        Exemplos válidos  : "0.2.0", "1.0.0", "1.2.3b1"
        Exemplos inválidos: "v0.2.0", "latest", "dev"

        Garante que a versão pode ser comparada e parseada por ferramentas
        de empacotamento e CI/CD.
        """
        assert SEMVER_PATTERN.match(sap_automation.__version__), (
            f"Versão {sap_automation.__version__!r} não segue o formato MAJOR.MINOR.PATCH"
        )

    def test_version_acessivel_pela_classe_sap(self):
        """
        SAP.version deve retornar o mesmo valor de sap_automation.__version__.

        SAP.version lê direto de importlib.metadata — não depende de __init__
        nem de SAPConnection, então não precisa de mock para ser testado.
        Instanciamos via __new__ para evitar que __init__ tente conectar ao SAP.
        """
        sap = SAP.__new__(SAP)
        assert sap.version == f"sap-automation v{sap_automation.__version__}"

    def test_version_fallback_quando_pacote_nao_instalado(self, mocker):
        """
        SAP.version deve retornar '0.0.0-dev' quando o pacote não está instalado.

        Situação típica: rodando direto do repositório sem pip install -e .

        mocker.patch() substitui version() por uma função que lança
        PackageNotFoundError, simulando a ausência do pacote instalado.
        O patch é revertido automaticamente ao fim do teste.
        """
        from importlib.metadata import PackageNotFoundError

        mocker.patch(
            "sap_automation.sap.version",
            side_effect=PackageNotFoundError("sap-automation"),
        )

        sap = SAP.__new__(SAP)
        assert sap.version == "sap-automation v0.0.0-dev"

    def test_version_consistente_entre_importacoes(self):
        """
        Múltiplas importações do módulo devem retornar a mesma versão.

        Python cacheia módulos importados — esse teste documenta e garante
        esse comportamento esperado.
        """
        import sap_automation as sa1
        import sap_automation as sa2

        assert sa1.__version__ == sa2.__version__
