from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from sap_automation.cache import CacheManager, CacheTTL
from sap_automation.client.config import SAPConfig
from sap_automation.client.connection import SAPConnection
from sap_automation.core.types import ReadMode
from sap_automation.models.mm.contrato import Contrato
from sap_automation.models.mm.frs import FRS, ML84Item
from sap_automation.models.mm.pedido import Pedido
from sap_automation.transactions.mm import ME23N, ME33K, ML81N, ML83, ML84


class SAP:
    """
    Ponto de entrada da biblioteca sap_automation.

    Gerencia a conexão com o SAP e expõe os módulos de transações
    organizados por área funcional (MM, futuramente PM, FI, etc.).

    Uso
    ---
        config = SAPConfig.from_env()
        sap = SAP(config).connect()

        pedido   = sap.mm.me23n("4500012345")
        frs      = sap.mm.ml81n("1001904414")
        frs_list = sap.mm.ml84(pedidos=["4500012345"])
        frs_pdf  = sap.mm.ml83(frs=["1001909519"], destino="C:/pdfs/")

    Cache
    -----
    Por padrão, os resultados são cacheados em SQLite com TTL por operação.
    Para ignorar o cache e forçar consulta ao SAP:

        frs_list = sap.mm.ml84(pedidos=["4500012345"], force=True)

    O banco de cache fica em ~/.sap_automation/cache.db por padrão.
    Para customizar, defina SAP_CACHE_DB no .env ou passe cache_db_path
    ao SAPConfig.
    """

    def __init__(self, config: SAPConfig):
        self.config = config
        self._connection = SAPConnection(config)
        self.session = None
        self.cache = CacheManager(config.cache_db_path)
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
            return f"sap-automation v{version('sap-automation')}"
        except PackageNotFoundError:
            return "sap-automation v0.0.0-dev"

    # ------------------------------------------------------------------
    # MÓDULOS
    # ------------------------------------------------------------------

    class MM:
        """
        Módulo de transações MM (Gestão de Materiais).

        Agrupa as transações do módulo MM e isola a criação dos objetos
        Transaction do código cliente — que só precisa chamar métodos.

        Todos os métodos de consulta aceitam force=True para ignorar o
        cache e buscar diretamente do SAP.
        """

        def __init__(self, sap: "SAP"):
            self.sap = sap

        # - - - - - - - - - - - - - - - - -
        def me23n(
            self,
            pedido: str,
            mode: ReadMode = ReadMode.DEEP,
            force: bool = False,
        ) -> Pedido:
            """
            Consulta um pedido de compras (ME23N).

            Parâmetros
            ----------
            pedido : str      — número do pedido (ex: "4500012345")
            mode   : ReadMode — DEEP (padrão): cabeçalho + itens + histórico
                                SHALLOW: apenas cabeçalho
            force  : bool     — True ignora o cache e consulta o SAP diretamente

            Retorna
            -------
            Pedido
            """
            key = CacheManager.make_key("me23n", pedido=pedido, mode=str(mode))

            if not force:
                cached = self.sap.cache.get(key)
                if cached is not None:
                    return Pedido(**cached)

            result: Pedido = ME23N(self.sap.session, pedido, mode=mode).run()
            self.sap.cache.set(key, result.model_dump(), ttl=CacheTTL.ME23N)
            return result

        # - - - - - - - - - - - - - - - - -
        def me33k(
            self,
            contrato: str,
            force: bool = False,
        ) -> Contrato:
            """
            Consulta um contrato (ME33K).

            Parâmetros
            ----------
            contrato : str  — número do contrato (ex: "4600017196")
            force    : bool — True ignora o cache e consulta o SAP diretamente

            Retorna
            -------
            Contrato
            """
            key = CacheManager.make_key("me33k", contrato=contrato)

            if not force:
                cached = self.sap.cache.get(key)
                if cached is not None:
                    return Contrato(**cached)

            result: Contrato = ME33K(self.sap.session, contrato).run()
            self.sap.cache.set(key, result.model_dump(), ttl=CacheTTL.ME33K)
            return result

        # - - - - - - - - - - - - - - - - -
        def ml81n(
            self,
            frs: str,
            mode: ReadMode = ReadMode.DEEP,
            force: bool = False,
        ) -> FRS:
            """
            Consulta uma Folha de Registro de Serviços (ML81N).

            Parâmetros
            ----------
            frs  : str      — número da FRS (ex: "1001904414")
            mode : ReadMode — DEEP (padrão): extração completa
                              SHALLOW: cabeçalho + DdsBásicos (municipio, UF)
            force : bool    — True ignora o cache e consulta o SAP diretamente

            Retorna
            -------
            FRS
            """
            key = CacheManager.make_key("ml81n", frs=frs, mode=str(mode))

            if not force:
                cached = self.sap.cache.get(key)
                if cached is not None:
                    return FRS(**cached)

            result: FRS = ML81N(self.sap.session, frs, mode=mode).run()
            self.sap.cache.set(key, result.model_dump(), ttl=CacheTTL.ML81N)
            return result

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
        ) -> list[Path]:
            """
            Imprime FRS como PDF (ML83).

            Nota: ml83 não usa cache — cada execução gera arquivos
            físicos no disco e depende do estado atual do SAP.

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
            force: bool = False,
        ) -> list[ML84Item]:
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
            status       : str  — "tudo" | "aceito" | "nao_aceito" (padrão: "tudo")
            force        : bool — True ignora o cache e consulta o SAP diretamente

            Retorna
            -------
            list[ML84Item]
            """
            key = CacheManager.make_key(
                "ml84",
                frs=frs,
                pedidos=pedidos,
                fornecedores=fornecedores,
                req_compras=req_compras,
                centros=centros,
                status=status,
            )

            if not force:
                cached = self.sap.cache.get(key)
                if cached is not None:
                    return [ML84Item(**item) for item in cached]

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

            result: list[ML84Item] = ml84.run()
            self.sap.cache.set(
                key,
                [item.model_dump() for item in result],
                ttl=CacheTTL.ML84,
            )
            return result
