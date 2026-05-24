"""
Transação ML83 — Impressão de Folha de Registro de Serviços

Fluxo de execução
------------------
1. Aplica filtros na tela de seleção (padrão Builder, igual à ML84)
2. Executa a pesquisa (F8) — tela de resultados exibe a lista de FRS
3. Mapeia as FRS disponíveis via _mapear_frs() (lê chk[1,N] e lbl[3,N])
4. Pré-carrega dados de cada FRS via ML81N (município, UF)
5. Para cada FRS: seleciona checkbox, clica Exibir saída, clica Imprimir,
   salva PDF via popup Windows, volta à tela de resultados (F3)

Nomenclatura de arquivos
------------------------
Por padrão usa município e UF obtidos da ML81N:
    FRS_{numero}_{municipio}_{UF}.pdf

Pode ser customizado via callable nome_arquivo(numero_frs, frs_data):
    def nome(numero, frs): return f"FRS_{numero}_{frs.texto_breve}"
    ML83(session, destino="C:/pdfs/", nome_arquivo=nome)

TODO: implementar modo de impressão em lote sem ML81N.
      Atualmente cada FRS é processada individualmente para garantir o ID
      fixo do checkbox (wnd[0]/usr/chk[1,6]). Em lote com checkboxes
      dinâmicos, seria necessário mapear a GuiUserArea (GuiLabel + GuiCheckbox).
"""

import logging
import re
import time
from enum import StrEnum
from pathlib import Path
from typing import Callable

import win32con
import win32gui

from sap_automation.components import MultiSelection
from sap_automation.exceptions.errors import (
    ConfigError,
    SAPNotFoundError,
    SAPTimeoutError,
)
from sap_automation.transactions.base import Transaction

# ─── Constantes ───────────────────────────────────────────────────────────────

_TITULO_POPUP_WINDOWS = "Salvar Saída de Impressão como"
_PATH_BTN_EXIBIR = "wnd[0]/tbar[1]/btn[17]"
_PATH_BTN_IMPRIMIR = "wnd[0]/tbar[0]/btn[86]"
_TIMEOUT_POPUP = 15  # segundos aguardando o popup Windows aparecer
_DELAY_APOS_SALVAR = 2.0  # segundos aguardando SAP processar o salvamento


def _nome_padrao(numero_frs: str, frs=None) -> str:
    """
    Nome padrão usando município e UF obtidos da ML81N:
        FRS_{numero}_{municipio}_{UF}

    Se município/UF não estiverem disponíveis, usa só o número.
    """
    if frs and frs.municipio and frs.UF:
        municipio = frs.municipio.replace(" ", "_")
        return f"FRS_{numero_frs}_{municipio}_{frs.UF}"
    return f"FRS_{numero_frs}"


# ─── Enums ────────────────────────────────────────────────────────────────────


class ML83Filter(StrEnum):
    """Filtros disponíveis na tela de seleção da ML83."""

    FRS = "LBLNI"
    COD_ACEITACAO = "KZABN"
    PEDIDO = "EBELN"
    TIPO_DOCUMENTO = "BSART"
    FORNECEDOR = "LIFNR"
    DATA_DOCUMENTO = "BEDAT"


def build_button_id(field: ML83Filter) -> str:
    return f"wnd[0]/usr/btn%_S_{field}_%_APP_%-VALU_PUSH"


# ─── Transação ────────────────────────────────────────────────────────────────


class ML83(Transaction):
    """
    Transação ML83 — Impressão de FRS como PDF.

    Uso
    ---
        resultado = (
            ML83(session, destino="C:/pdfs/")
            .filter_frs(["1001909519"])
            .run()
        )
        # resultado: list[Path] com os arquivos gerados
    """

    def __init__(
        self,
        session,
        destino: str | Path,
        nome_arquivo: Callable[[str, object], str] = _nome_padrao,
    ):
        """
        Parâmetros
        ----------
        session      : SAPSession — sessão SAP ativa
        destino      : str | Path — pasta onde os PDFs serão salvos
        nome_arquivo : Callable[[str, FRS], str]
                       Recebe (numero_frs, frs) e retorna nome sem extensão.
                       Default: "FRS_{numero}_{municipio}_{UF}"
        """
        super().__init__(session)
        self.destino = Path(destino)
        self.nome_arquivo = nome_arquivo
        self._filters: dict[ML83Filter, list[str]] = {}
        self.logger = logging.getLogger("sap.mm.ml83")

        if not self.destino.exists():
            raise ConfigError(f"Pasta de destino não encontrada: {self.destino}")

    # ------------------------------------------------------------------
    # BUILDER
    # ------------------------------------------------------------------

    def filter_frs(self, valores: list[str]) -> "ML83":
        """Filtra por número(s) de FRS."""
        self._filters[ML83Filter.FRS] = valores
        return self

    def filter_cod_aceitacao(self, valores: list[str]) -> "ML83":
        """Filtra por código(s) de aceitação."""
        self._filters[ML83Filter.COD_ACEITACAO] = valores
        return self

    def filter_pedidos(self, valores: list[str]) -> "ML83":
        """Filtra por número(s) de pedido."""
        self._filters[ML83Filter.PEDIDO] = valores
        return self

    def filter_tipo_documento(self, valores: list[str]) -> "ML83":
        """Filtra por tipo de documento."""
        self._filters[ML83Filter.TIPO_DOCUMENTO] = valores
        return self

    def filter_fornecedor(self, valores: list[str]) -> "ML83":
        """Filtra por código(s) de fornecedor."""
        self._filters[ML83Filter.FORNECEDOR] = valores
        return self

    def filter_data_documento(self, valores: list[str]) -> "ML83":
        """Filtra por data(s) de documento."""
        self._filters[ML83Filter.DATA_DOCUMENTO] = valores
        return self

    # ------------------------------------------------------------------
    # CICLO DE VIDA
    # ------------------------------------------------------------------

    def start(self):
        self.logger.info("Iniciando ML83")
        self.session.start_transaction("ML83")

    def execute(self) -> list[Path]:
        """
        Executa a impressão das FRS filtradas.

        Fluxo
        -----
        1. Aplica filtros e executa pesquisa (F8)
        2. Mapeia FRS disponíveis na tela de resultados
        3. Pré-carrega dados via ML81N (município, UF para nomenclatura)
        4. Imprime cada FRS

        Retorna
        -------
        list[Path] — arquivos PDF gerados com sucesso.
        FRS que falharam são logadas como warning sem interromper as demais.
        """
        self._apply_filters()
        self._run()

        frs_por_linha = self._mapear_frs()
        if not frs_por_linha:
            self.logger.warning("Nenhuma FRS encontrada na tela de resultados")
            return []

        self.logger.info(
            f"{len(frs_por_linha)} FRS encontrada(s): {list(frs_por_linha.values())}"
        )

        # pré-carrega dados via ML81N antes de iniciar a impressão
        # ML81N.run() chama go_home() no cleanup — o SAP volta ao Easy Access.
        # É necessário reabrir a ML83 e reexecutar a pesquisa para restaurar
        # a tela de resultados antes de processar as impressões.
        dados_frs = self._carregar_dados_frs(list(frs_por_linha.values()))

        self.logger.info("Restaurando tela de resultados da ML83")
        self.session.start_transaction("ML83")
        self._apply_filters()
        self._run()

        return self._processar_resultados(frs_por_linha, dados_frs)

    # ------------------------------------------------------------------
    # PASSOS INTERNOS
    # ------------------------------------------------------------------

    def _apply_filters(self):
        """Aplica os filtros configurados via Builder."""
        for field, values in self._filters.items():
            btn_id = build_button_id(field)
            self.logger.debug(f"Abrindo seleção múltipla: {field.name}")
            self.session.find(btn_id).press()
            multi = MultiSelection(self.session)
            multi.clear()
            multi.include_values(values)
            multi.apply()

    def _run(self):
        """
        Executa a pesquisa (F8) e verifica se há resultados.

        Lança
        -----
        SAPNotFoundError se o SAP indicar que nenhum documento foi encontrado.
        """
        self.session.send_vkey(8)

        status = self.session.get_status_bar()
        if "não foram encontrados" in status.lower():
            raise SAPNotFoundError(
                "Nenhuma FRS encontrada para os filtros informados",
                sap_message=status,
            )

    def _mapear_frs(self) -> dict[int, str]:
        """
        Enumera a GuiUserArea e retorna {linha: numero_frs} para todas
        as FRS imprimíveis encontradas na tela de resultados.

        Padrão observado na tela:
            chk[1,N]  → checkbox de seleção (coluna 1) — um por FRS
            lbl[3,N]  → número da FRS (coluna 3)
            chk[20,N] → checkbox de aceite — ignorado

        Linhas sem chk[1,N] são cabeçalhos de pedido — ignoradas.
        """
        usr = self.session.find("wnd[0]/usr")
        resultado: dict[int, str] = {}

        try:
            children = usr.Children
        except Exception as e:
            self.logger.warning(f"Erro ao acessar filhos da GuiUserArea: {e}")
            return resultado

        for i in range(children.Count):
            try:
                child = children.ElementAt(i)
                child_id = child.Id

                # busca chk[1,N] — checkbox de seleção (coluna 1)
                m = re.search(r"chk\[1,(\d+)\]", child_id)
                if not m:
                    continue

                linha = int(m.group(1))

                # lê número da FRS em lbl[3,N]
                numero_frs = self.session.get_text(f"wnd[0]/usr/lbl[3,{linha}]").strip()

                if numero_frs:
                    resultado[linha] = numero_frs
                    self.logger.debug(f"FRS mapeada: linha={linha} numero={numero_frs}")

            except Exception as e:
                self.logger.debug(f"Elemento {i} ignorado: {e}")
                continue

        return dict(sorted(resultado.items()))

    def _carregar_dados_frs(self, numeros: list[str]) -> dict:
        """
        Pré-carrega dados de cada FRS via ML81N antes de iniciar a impressão.

        Retorna {numero_frs: FRS}. FRS que falharem ficam como None —
        o nome padrão sem município será usado para elas.
        """
        from sap_automation.transactions.mm.ml81n import ML81N

        dados = {}
        for numero in numeros:
            try:
                self.logger.debug(f"Carregando dados da FRS {numero} via ML81N")
                dados[numero] = ML81N(self.session, numero).run()
            except Exception as e:
                self.logger.warning(f"Erro ao carregar FRS {numero} via ML81N: {e}")
                dados[numero] = None
        return dados

    def _processar_resultados(
        self,
        frs_por_linha: dict[int, str],
        dados_frs: dict,
    ) -> list[Path]:
        """
        Itera sobre as FRS mapeadas e gera o PDF de cada uma.

        Para cada FRS:
            1. Seleciona o checkbox
            2. Clica em Exibir saída
            3. Clica em Imprimir
            4. Salva o PDF via popup Windows
            5. Volta à tela de resultados (F3)
        """
        arquivos_gerados: list[Path] = []

        for linha, numero_frs in frs_por_linha.items():
            self.logger.info(f"Processando FRS {numero_frs} (linha {linha})")

            chk_path = f"wnd[0]/usr/chk[1,{linha}]"

            try:
                self.session.find(chk_path).selected = True
                self.session.find(_PATH_BTN_EXIBIR).press()
                self.session.find(_PATH_BTN_IMPRIMIR).press()

                frs_data = dados_frs.get(numero_frs)
                nome = self.nome_arquivo(numero_frs, frs_data)
                caminho = self.destino / f"{nome}.pdf"

                self._salvar_popup_windows(str(caminho))

                arquivos_gerados.append(caminho)
                self.logger.info(f"FRS {numero_frs} salva em: {caminho}")

            except Exception as e:
                self.logger.warning(f"FRS {numero_frs}: erro ao processar — {e}")
            finally:
                # volta à tela de resultados independente de sucesso ou falha
                self.session.send_vkey(3)  # F3

        return arquivos_gerados

    # ------------------------------------------------------------------
    # POPUP WINDOWS
    # ------------------------------------------------------------------

    def _salvar_popup_windows(self, caminho_completo: str):
        """
        Interage com o popup nativo do Windows "Salvar Saída de Impressão como".

        Estrutura do popup (mapeada via EnumChildWindows):
            FloatNotifySink → ComboBox → Edit  ← campo de nome
            Button text='Sa&lvar'              ← filho direto do popup

        O campo Edit fica aninhado, portanto usa _find_edit_recursivo().
        O botão tem ampersand ('Sa&lvar'), portanto busca por substring 'lvar'.
        """
        self.logger.debug(f"Aguardando popup: {_TITULO_POPUP_WINDOWS!r}")
        hwnd = self._aguardar_janela(_TITULO_POPUP_WINDOWS, _TIMEOUT_POPUP)

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)

        # preenche o campo de nome
        hwnd_edit = self._find_edit_recursivo(hwnd)
        if hwnd_edit:
            win32gui.SendMessage(hwnd_edit, win32con.WM_SETTEXT, 0, caminho_completo)
            self.logger.debug(f"Caminho preenchido: {caminho_completo}")
        else:
            # fallback via clipboard
            import win32api
            import win32clipboard

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(caminho_completo)
            win32clipboard.CloseClipboard()
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord("A"), 0, 0, 0)
            win32api.keybd_event(ord("A"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(ord("V"), 0, 0, 0)
            win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.2)
            self.logger.debug("Caminho preenchido via clipboard")

        # confirma com botão Salvar
        hwnd_salvar = self._find_button(hwnd, "lvar")
        if hwnd_salvar:
            win32gui.SendMessage(hwnd_salvar, win32con.BM_CLICK, 0, 0)
            self.logger.debug("Botão Salvar clicado")
        else:
            # fallback via Enter
            import win32api

            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
            self.logger.debug("Enter enviado como fallback")

        # aguarda popup fechar antes de continuar
        self._aguardar_popup_fechar(hwnd, timeout=_TIMEOUT_POPUP)
        self.logger.debug("Popup fechado — salvamento concluído")

    def _find_edit_recursivo(self, hwnd_pai: int) -> int | None:
        """Busca recursivamente o primeiro campo Edit dentro de uma janela."""
        resultado = []

        def callback(hwnd, _):
            if win32gui.GetClassName(hwnd) == "Edit":
                resultado.append(hwnd)

        win32gui.EnumChildWindows(hwnd_pai, callback, None)
        return resultado[0] if resultado else None

    def _aguardar_popup_fechar(self, hwnd: int, timeout: float):
        """
        Aguarda um popup Windows fechar completamente verificando
        se o handle hwnd deixou de ser uma janela válida.
        """
        inicio = time.time()
        while time.time() - inicio < timeout:
            if not win32gui.IsWindow(hwnd):
                return
            time.sleep(0.2)

        raise SAPTimeoutError(
            f"Popup de salvamento não fechou após {timeout}s. "
            "O arquivo pode não ter sido salvo corretamente."
        )

    def _aguardar_janela(self, titulo: str, timeout: float) -> int:
        """
        Aguarda uma janela Windows com o título informado aparecer.
        Retorna o hwnd da janela. Lança SAPTimeoutError se não encontrar.
        """
        inicio = time.time()
        while time.time() - inicio < timeout:
            hwnd = win32gui.FindWindow(None, titulo)
            if hwnd:
                self.logger.debug(f"Popup encontrado: hwnd={hwnd}")
                return hwnd
            time.sleep(0.3)

        raise SAPTimeoutError(
            f"Popup {titulo!r} não apareceu após {timeout}s. "
            "Verifique se o SAP abriu a janela de salvamento corretamente."
        )

    def _find_button(self, hwnd_pai: int, texto: str) -> int | None:
        """Localiza um botão filho pelo texto dentro de uma janela pai."""
        resultado = []

        def callback(hwnd, _):
            classe = win32gui.GetClassName(hwnd)
            label = win32gui.GetWindowText(hwnd)
            if classe == "Button" and texto.lower() in label.lower():
                resultado.append(hwnd)

        win32gui.EnumChildWindows(hwnd_pai, callback, None)
        return resultado[0] if resultado else None
