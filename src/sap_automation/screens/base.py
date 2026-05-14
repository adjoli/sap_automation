from sap_automation.components.explorer import SAPExplorer


class Screen:
    """
    Classe base para telas SAP complexas com layout dinâmico.

    Fornece acesso ao SAPExplorer com raiz em wnd[0]/usr — o ponto de entrada
    padrão para navegação na área de conteúdo de qualquer janela SAP.

    Uso
    ---
    Subclasse Screen para encapsular a lógica de navegação de uma transação
    específica, separando-a da lógica de negócio da Transaction.

    Quando usar Screen
    ------------------
    Use Screen quando a transação tem:
    - IDs de componentes que variam conforme o estado da tela
    - Múltiplas seções expansíveis
    - TabStrips aninhados
    - Lógica de navegação complexa que não cabe em Transaction.execute()

    Para transações simples com IDs estáveis (ML81N, ML84), não é necessário
    criar uma Screen — acesse os componentes diretamente via session na Transaction.

    Explorer
    --------
    O explorer é recriado a cada acesso — nunca é cacheado. Isso garante que
    após qualquer rerenderização do SAP (select de aba, expand de seção),
    o explorer sempre parte de um nó fresco.

    Se precisar de um explorer com escopo menor (mais rápido), crie-o
    explicitamente a partir de um ID fixo:

        SAPExplorer(self.session.find(ID_FIXO))
    """

    def __init__(self, session):
        """
        Parâmetros
        ----------
        session : SAPSession
            Sessão SAP ativa.
        """
        self.session = session

    @property
    def explorer(self) -> SAPExplorer:
        """
        SAPExplorer com raiz em wnd[0]/usr.

        Recriado a cada acesso para garantir que sempre parte de um nó
        fresco — nunca usa objetos stale de rerenderizações anteriores.
        """
        return SAPExplorer(self.session.find("wnd[0]/usr"))
