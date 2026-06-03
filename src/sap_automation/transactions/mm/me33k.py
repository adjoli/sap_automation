"""
Transação ME33K — Exibir Contrato

Fluxo de execução
-----------------
A ME33K exige navegação entre múltiplas telas para coletar todos os dados:

    1. Digita número do contrato → Enter → abre tela de síntese
    2. Clica em "Detalhes" (btn[6]) → tela principal com campos base
    3. Abre popup de status (btn[42]) → lê status → fecha (Enter wnd[1])
    4. Abre popup de gerentes/fiscais (BTN_GERENTES_FISCAIS) →
       lê tabela de gerentes → lê tabela de fiscais → fecha (Enter wnd[1])
    5. Abre tela de dados adicionais (BTN_DADOS_ADICIONAIS) →
       lê TLC, valor consumido, saldo → volta (F3)

Fechamento de popups
--------------------
O fechamento de wnd[1] é sempre feito em bloco finally — garante que o
popup fecha mesmo quando a leitura das tabelas falha, evitando que
operações subsequentes encontrem a tela em estado inesperado.
"""

import logging

from sap_automation.components import TableControl
from sap_automation.core.converters import parse_sap_date
from sap_automation.exceptions.errors import ConfigError, SAPNotFoundError
from sap_automation.models.mm.contrato import Contrato, Gestor
from sap_automation.transactions.base import Transaction


class _IDs:
    """IDs SAP da transação ME33K."""

    # tela principal
    CONTRATO = "wnd[0]/usr/ctxtRM06E-EVRTN"
    FORNECEDOR = "wnd[0]/usr/ctxtEKKO-LIFNR"
    DESC_FORNECEDOR = "wnd[0]/usr/txtLFA1-NAME1"
    DATA_FIM = "wnd[0]/usr/ctxtEKKO-KDATE"
    TLC = "wnd[0]/usr/ctxtEKKO_CI-ZZTPCOD_TLC"
    VALOR_TOTAL = "wnd[0]/usr/txtEKKO-KTWRT"
    VALOR_CONSUMIDO = "wnd[0]/usr/txtVG_BRTWR"
    SALDO = "wnd[0]/usr/txtVG_SALDO"

    # botões de navegação
    BTN_DETALHES = "wnd[0]/tbar[1]/btn[6]"
    BTN_SINTESE = "wnd[0]/tbar[1]/btn[5]"
    BTN_STATUS = "wnd[0]/tbar[1]/btn[42]"
    BTN_GEST_FISC = "wnd[0]/usr/ssubCUSTSCR1:SAPLXM06:0201/btnGERENTE_FISCAL"
    BTN_DADOS_ADIC = "wnd[0]/usr/ssubCUSTSCR1:SAPLXM06:0201/btnINF_ADIC"

    # popups
    STATUS = "wnd[1]/usr/txtT16FE-FRGET"
    TABELA_GERENTES = "wnd[1]/usr/tblSAPLZGFMM_GERFISTC_GERENTES"
    TABELA_FISCAIS = "wnd[1]/usr/tblSAPLZGFMM_GERFISTC_FISCAIS"


def _fechar_popup() -> None:
    """Tenta fechar wnd[1] — nunca lança exceção."""
    pass  # implementado por closure em _load_gerentes_fiscais


class ME33K(Transaction):
    """
    Transação ME33K — Exibir Contrato.

    Retorna objeto Contrato com todos os dados disponíveis.

    Uso
    ---
        contrato = ME33K(session, '4600012345').run()
        print(contrato.nome_fornecedor)
        print(contrato.dias_restantes)
    """

    def __init__(self, session, contrato: str):
        super().__init__(session)

        if not contrato or not str(contrato).strip():
            raise ConfigError("Número do contrato é obrigatório")

        self.contrato = str(contrato).strip()
        self.logger = logging.getLogger("sap.mm.me33k")

    # ------------------------------------------------------------------
    # CICLO DE VIDA
    # ------------------------------------------------------------------

    def start(self):
        self.logger.info(f"Iniciando ME33K [contrato={self.contrato}]")
        self.session.start_transaction("ME33K")

    def execute(self) -> Contrato:
        self._abrir_contrato()

        self.session.find(_IDs.BTN_DETALHES).press()

        data = {}
        data["num_contrato"] = self.contrato
        data["num_fornecedor"] = self.session.get_text(_IDs.FORNECEDOR)
        data["nome_fornecedor"] = self.session.get_text(_IDs.DESC_FORNECEDOR)
        data["data_fim_contrato"] = parse_sap_date(self.session.get_text(_IDs.DATA_FIM))
        data["valor_total"] = self.session.get_text(_IDs.VALOR_TOTAL)

        data["status"] = self._load_status()
        data["gerentes"], data["fiscais"] = self._load_gerentes_fiscais()

        adic = self._load_dados_adicionais()
        data.update(adic)

        self.logger.info("ME33K finalizada com sucesso")
        return Contrato(**data)

    # ------------------------------------------------------------------
    # ABERTURA DO CONTRATO
    # ------------------------------------------------------------------

    def _abrir_contrato(self):
        self.session.set_text(_IDs.CONTRATO, self.contrato)
        self.session.send_vkey(0)

        status = self.session.get_status_bar()
        if "não existe" in status.lower():
            raise SAPNotFoundError(
                f"Contrato {self.contrato} não encontrado",
                sap_message=status,
            )

    # ------------------------------------------------------------------
    # HELPER: fecha popup wnd[1]
    # ------------------------------------------------------------------

    def _fechar_popup_status(self):
        """
        Fecha o popup de status do contrato (wnd[1]).
        Usa Enter (vkey 0) — botão padrão de confirmação.
        Nunca lança exceção — usado em bloco finally.
        """
        try:
            self.session.send_vkey(0, window="wnd[1]")
        except Exception:
            pass

    def _fechar_popup_gerentes_fiscais(self):
        """
        Fecha o popup de gerentes e fiscais (wnd[1]).
        Usa btn[8] — botão de confirmação deste popup específico.
        Nunca lança exceção — usado em bloco finally.
        """
        try:
            self.session.find("wnd[1]/tbar[0]/btn[8]").press()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # TELAS SECUNDÁRIAS
    # ------------------------------------------------------------------

    def _load_status(self) -> str | None:
        """
        Abre popup de status, lê e fecha.
        Fluxo: btn[42] → lê STATUS → fecha wnd[1]
        """
        try:
            self.session.find(_IDs.BTN_STATUS).press()
            status = self.session.get_text(_IDs.STATUS)
            return status
        except Exception as e:
            self.logger.warning(f"Erro ao ler status do contrato: {e}")
            return None
        finally:
            self._fechar_popup_status()

    def _load_gerentes_fiscais(self) -> tuple[list[Gestor], list[Gestor]]:
        """
        Abre popup de gerentes/fiscais, lê as duas tabelas e fecha.

        O fechamento em finally garante que wnd[1] sempre fecha,
        mesmo que a leitura das tabelas falhe — evitando que
        _load_dados_adicionais encontre a tela em estado incorreto.
        """
        gerentes = []
        fiscais = []

        try:
            self.session.find(_IDs.BTN_GEST_FISC).press()

            gerentes_rows = TableControl(
                self.session, _IDs.TABELA_GERENTES, window="wnd[1]"
            ).to_list()
            gerentes = [
                Gestor(chave=row.get("Chave", ""), nome=row.get("Nome", ""))
                for row in gerentes_rows
                if row.get("Chave")
            ]

            fiscais_rows = TableControl(
                self.session, _IDs.TABELA_FISCAIS, window="wnd[1]"
            ).to_list()
            fiscais = [
                Gestor(chave=row.get("Chave", ""), nome=row.get("Nome", ""))
                for row in fiscais_rows
                if row.get("Chave")
            ]

        except Exception as e:
            self.logger.warning(f"Erro ao ler gerentes/fiscais: {e}")
        finally:
            # sempre fecha o popup — independente de sucesso ou falha
            self._fechar_popup_gerentes_fiscais()

        return gerentes, fiscais

    def _load_dados_adicionais(self) -> dict:
        """
        Abre tela de dados adicionais, lê campos e volta.
        Fluxo: BTN_DADOS_ADIC → lê campos → F3
        """
        data = {
            "tlc": None,
            "valor_consumido": None,
            "saldo": None,
        }

        try:
            self.session.find(_IDs.BTN_DADOS_ADIC).press()

            data["tlc"] = self.session.get_text(_IDs.TLC)

            data["valor_consumido"] = self.session.get_text(_IDs.VALOR_CONSUMIDO)
            data["saldo"] = self.session.get_text(_IDs.SALDO)

        except Exception as e:
            self.logger.warning(f"Erro ao ler dados adicionais: {e}")
        finally:
            self.session.send_vkey(3)  # F3 — volta, sempre

        return data
