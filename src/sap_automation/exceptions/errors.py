"""
Hierarquia de exceções da biblioteca sap_automation.

Todas as exceções herdam de SAPError, permitindo ao chamador capturar
erros genéricos ou específicos conforme necessário:

    # captura qualquer erro da biblioteca
    except SAPError:
        ...

    # captura apenas erros de documento não encontrado
    except SAPNotFoundError:
        ...

Hierarquia
----------
SAPError
  ├── ConfigError          — configuração inválida ou incompleta
  ├── SAPConnectionError   — falha ao conectar ou autenticar no SAP
  └── SAPRuntimeError      — erro durante execução de uma transação
        ├── SAPNotFoundError    — documento/elemento não encontrado
        ├── SAPTimeoutError     — timeout aguardando popup ou elemento
        └── SAPNavigationError  — falha ao navegar na tela
"""


# ─── BASE ─────────────────────────────────────────────────────────────────────


class SAPError(Exception):
    """
    Classe base de todas as exceções da biblioteca sap_automation.

    Capture esta exceção para tratar qualquer erro da biblioteca
    sem precisar conhecer os tipos específicos.
    """


# ─── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────


class ConfigError(SAPError):
    """
    Configuração inválida ou incompleta.

    Lançada quando:
    - Variável de ambiente obrigatória está ausente (SAP_USER, SAP_PASSWD_*)
    - Parâmetro obrigatório não foi fornecido (número de pedido vazio)
    - Pasta de destino não existe (ML83)

    Exemplos
    --------
        raise ConfigError("SAP_USER não definido no ambiente")
        raise ConfigError("Número do pedido é obrigatório")
        raise ConfigError(f"Pasta de destino não encontrada: {destino}")
    """


# ─── CONEXÃO ──────────────────────────────────────────────────────────────────


class SAPConnectionError(SAPError):
    """
    Falha ao conectar ou autenticar no SAP GUI.

    Lançada quando:
    - O SAP GUI não está aberto
    - O Scripting não está habilitado
    - A conexão especificada não foi encontrada no SAP Logon
    - Credenciais inválidas

    Exemplos
    --------
        raise SAPConnectionError("SAP GUI não está aberto")
        raise SAPConnectionError(f"Conexão {nome!r} não encontrada no SAP Logon")
    """


# ─── RUNTIME ──────────────────────────────────────────────────────────────────


class SAPRuntimeError(SAPError):
    """
    Erro genérico durante a execução de uma transação SAP.

    Use as subclasses quando possível para maior precisão.
    Use esta diretamente apenas para erros que não se encaixam
    nas categorias mais específicas.
    """


class SAPNotFoundError(SAPRuntimeError):
    """
    Documento ou elemento não encontrado.

    Lançada quando:
    - O SAP exibe mensagem de "não encontrado" na barra de status
    - Uma FRS, pedido ou documento não existe no sistema
    - Um elemento SAP (campo, botão, aba) não está disponível na tela

    Exemplos
    --------
        raise SAPNotFoundError(
            "Nenhuma FRS encontrada para os filtros informados",
            sap_message="Não foram encontrados documentos de compra adequados",
        )
        raise SAPNotFoundError(f"FRS {numero!r} não existe no sistema")
    """

    def __init__(self, message: str, *, sap_message: str | None = None):
        """
        Parâmetros
        ----------
        message     : str — descrição do erro em linguagem da aplicação
        sap_message : str — mensagem exata da barra de status do SAP (opcional)
        """
        self.sap_message = sap_message
        full = f"{message} | SAP: {sap_message}" if sap_message else message
        super().__init__(full)


class SAPTimeoutError(SAPRuntimeError):
    """
    Timeout aguardando um popup ou elemento aparecer.

    Lançada quando:
    - O popup do Windows não aparece dentro do tempo limite (ML83)
    - O SAP demora mais que o esperado para renderizar um elemento

    Exemplos
    --------
        raise SAPTimeoutError(
            f"Popup {titulo!r} não apareceu após {timeout}s"
        )
    """


class SAPNavigationError(SAPRuntimeError):
    """
    Falha ao navegar na tela SAP.

    Lançada quando:
    - Uma aba não existe no TabStrip
    - Uma seção não pode ser expandida
    - A transação não abriu corretamente

    Exemplos
    --------
        raise SAPNavigationError(f"Aba {nome!r} não encontrada em {tabstrip}")
        raise SAPNavigationError("Seção do cabeçalho não pôde ser expandida")
    """
