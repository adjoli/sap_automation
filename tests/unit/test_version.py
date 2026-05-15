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

Por que isso importa?
----------------------
Sem esses testes, é possível:
  - Quebrar a importação de __version__ silenciosamente ao refatorar __init__.py.
  - Desincronizar a versão exposta pela classe SAP da versão real do pacote.
  - Publicar uma versão com formato inválido que quebre ferramentas de CI/CD.

Execução:
    pytest tests/unit/test_version.py -v
"""

import re

import pytest

import sap_automation
from sap_automation.sap import SAP

# Formato semântico: MAJOR.MINOR.PATCH com sufixos opcionais (ex: 1.0.0, 0.2.0, 1.0.0b1)
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

        Exemplo de valores válidos: "0.2.0", "1.0.0", "1.2.3b1"
        Exemplo de valores inválidos: "v0.2.0", "latest", "dev"

        Garante que a versão pode ser comparada e parseada por ferramentas
        de empacotamento e CI/CD.
        """
        assert SEMVER_PATTERN.match(sap_automation.__version__), (
            f"Versão {sap_automation.__version__!r} não segue o formato MAJOR.MINOR.PATCH"
        )

    def test_version_acessivel_pela_classe_sap(self):
        """
        SAP.version deve retornar o mesmo valor de sap_automation.__version__.

        A classe SAP expõe a versão como propriedade para que código cliente
        possa verificar a versão sem importar o módulo diretamente.

        SAP.version lê direto de importlib.metadata — não depende de __init__
        nem de SAPConnection, então não precisa de mock para ser testado.
        Instanciamos via __new__ para evitar que __init__ tente conectar ao SAP.
        """
        sap = SAP.__new__(SAP)
        assert sap.version == sap_automation.__version__

    def test_version_fallback_quando_pacote_nao_instalado(self, monkeypatch):
        """
        SAP.version deve retornar "0.0.0-dev" quando o pacote não está instalado.

        Situação típica: rodando direto do repositório sem pip install -e .
        O fallback evita que PackageNotFoundError quebre o código cliente
        que apenas quer checar a versão.

        Usamos monkeypatch para simular a ausência do pacote sem precisar
        desinstalar nada — substituímos version() por uma que lança
        PackageNotFoundError, exatamente como o importlib faria.
        """
        from importlib.metadata import PackageNotFoundError

        def version_nao_instalado(name):
            raise PackageNotFoundError(name)

        monkeypatch.setattr("sap_automation.sap.version", version_nao_instalado)

        sap = SAP.__new__(SAP)
        assert sap.version == "0.0.0-dev"

    def test_version_consistente_entre_importacoes(self):
        """
        Múltiplas importações do módulo devem retornar a mesma versão.

        Python cacheia módulos importados — esse teste documenta e garante
        esse comportamento esperado.
        """
        import sap_automation as sa1
        import sap_automation as sa2

        assert sa1.__version__ == sa2.__version__
