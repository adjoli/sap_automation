from importlib.metadata import PackageNotFoundError, version

from sap_automation.client.config import SAPConfig
from sap_automation.client.connection import SAPConnection
from sap_automation.transactions.mm import ME23N, ML81N, ML83, ML84


class SAP:
    """
    Ponto de entrada da biblioteca sap_automation.

    Gerencia a conexão com o SAP e expõe os módulos de transações
    organizados por área funcional (MM, futuramente PM, FI, etc.).

    Uso
    ---
        config = SAPConfig.from_env()
        sap = SAP(config).connect()

        pedido = sap.mm.me23n("4500012345")
        frs    = sap.mm.ml81n("1001904414")
        frs_pdf = sap.mm.ml83(frs=["1001909519"], destino="C:/pdfs/")
    """

    def __init__(self, config: SAPConfig):
        self.config = config
        self._connection = SAPConnection(config)
        self.session = None
        self.mm = self.MM(self)

    def connect(self) -> "SAP":
        """
        Conecta ao SAP GUI aberto na máquina.
        Retorna self para permitir encadeamento: SAP(config).connect()
        """
        self.session = self._connection.connect()
        return self

    @property
    def version(self) -> str:
        """
        Versão instalada do pacote sap-automation.

        Lida diretamente dos metadados do pacote via importlib.metadata,
        garantindo que sempre reflete a versão real instalada —
        independente do estado de sap_automation.__init__.

        Retorna '0.0.0-dev' se o pacote não estiver instalado formalmente
        (ex: rodando direto do repositório sem pip install -e .).
        """
        try:
            return version("sap-automation")
        except PackageNotFoundError:
            return "0.0.0-dev"

    # ------------------------------------------------------------------
    # MÓDULOS
    # ------------------------------------------------------------------

    class MM:
        """
        Módulo de transações MM (Gestão de Materiais).

        Agrupa as transações do módulo MM e isola a criação dos objetos
        Transaction do código cliente — que só precisa chamar métodos.
        """

        def __init__(self, sap: "SAP"):
            self.sap = sap

        # - - - - - - - - - - - - - - - - -
        def me23n(self, pedido: str):
            """
            Consulta um pedido de compras (ME23N).

            Parâmetros
            ----------
            pedido : str — número do pedido (ex: "4500012345")

            Retorna
            -------
            Pedido
            """
            return ME23N(self.sap.session, pedido).run()

        # - - - - - - - - - - - - - - - - -
        def ml81n(self, frs: str):
            """
            Consulta uma Folha de Registro de Serviços (ML81N).

            Parâmetros
            ----------
            frs : str — número da FRS (ex: "1001904414")

            Retorna
            -------
            FRS
            """
            return ML81N(self.sap.session, frs).run()

        # - - - - - - - - - - - - - - - - -
        def ml83(
            self,
            destino: str,
            frs: list[str] | None = None,
            cod_aceitacao: list[str] | None = None,
            pedidos: list[str] | None = None,
            tipo_documento: list[str] | None = None,
            fornecedores: list[str] | None = None,
            data_documento: list[str] | None = None,
            nome_arquivo=None,
        ) -> list:
            """
            Imprime FRS como PDF (ML83).

            Parâmetros
            ----------
            destino        : str — pasta onde os PDFs serão salvos
            frs            : list[str] | None — números de FRS
            cod_aceitacao  : list[str] | None — códigos de aceitação
            pedidos        : list[str] | None — números de pedido
            tipo_documento : list[str] | None — tipos de documento
            fornecedores   : list[str] | None — códigos de fornecedor
            data_documento : list[str] | None — datas de documento
            nome_arquivo   : Callable[[str], str] | None
                            Função que recebe o número da FRS e retorna o nome
                            do arquivo sem extensão. Default: "FRS_{numero_frs}"

            Retorna
            -------
            list[Path] — caminhos dos PDFs gerados com sucesso
            """

            kwargs = {"destino": destino}
            if nome_arquivo:
                kwargs["nome_arquivo"] = nome_arquivo

            ml83 = ML83(self.sap.session, **kwargs)

            if frs:
                ml83.filter_frs(frs)
            if cod_aceitacao:
                ml83.filter_cod_aceitacao(cod_aceitacao)
            if pedidos:
                ml83.filter_pedidos(pedidos)
            if tipo_documento:
                ml83.filter_tipo_documento(tipo_documento)
            if fornecedores:
                ml83.filter_fornecedor(fornecedores)
            if data_documento:
                ml83.filter_data_documento(data_documento)

            return ml83.run()

        # - - - - - - - - - - - - - - - - -
        def ml84(
            self,
            frs: list[str] | None = None,
            pedidos: list[str] | None = None,
            fornecedores: list[str] | None = None,
            req_compras: list[str] | None = None,
            centros: list[str] | None = None,
            status: str = "tudo",
        ) -> list:
            """
            Lista Folhas de Registro de Serviços com filtros (ML84).

            Todos os parâmetros são opcionais — sem filtros, retorna todas
            as FRS acessíveis. O parâmetro status filtra pelo aceite.

            Parâmetros
            ----------
            frs          : list[str] | None — números de FRS
            pedidos      : list[str] | None — números de pedido
            fornecedores : list[str] | None — códigos de fornecedor
            req_compras  : list[str] | None — números de requisição de compra
            centros      : list[str] | None — códigos de centro
            status       : str — "tudo" | "aceito" | "nao_aceito" (padrão: "tudo")

            Retorna
            -------
            list[ML84Item]
            """
            ml84 = ML84(self.sap.session)

            if frs:
                ml84.filter_frs(frs)
            if pedidos:
                ml84.filter_pedidos(pedidos)
            if req_compras:
                ml84.filter_req_compras(req_compras)
            if fornecedores:
                ml84.filter_fornecedor(fornecedores)
            if centros:
                ml84.filter_centros(centros)

            ml84.status(status)

            return ml84.run()
