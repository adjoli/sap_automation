"""
Transação ML83 — Impressão de Folha de Registro de Serviços

Fluxo de execução (por FRS)
----------------------------
1. Aplica filtros na tela de seleção (padrão Builder, igual à ML84)
2. Executa a pesquisa (F8) — tela de resultados exibe a lista de FRS
3. Seleciona o checkbox da FRS (ID fixo: wnd[0]/usr/chk[1,6])
4. Clica em "Exibir saída" (btn[17])
5. Na tela de visualização, clica em "Imprimir" (btn[14])
6. O Windows abre o popup "Salvar Saída de Impressão como"
7. pywin32 localiza o popup pelo título, preenche o caminho e confirma
8. Volta à tela de resultados (F3)

Nomenclatura de arquivos
------------------------
O nome do arquivo é controlado por um callable `nome_arquivo`:
    Callable[[str], str]  — recebe o número da FRS, retorna o nome sem extensão

Isso mantém a biblioteca desacoplada de qualquer lógica de negócio específica
(municípios, datas, prefixos). O chamador injeta a função que quiser:

    # padrão (sem informação adicional)
    sap.mm.ml83(frs=["1001909519"], destino="C:/pdfs/")
    # → FRS_1001909519.pdf

    # com município vindo de fonte externa
    def nome(numero): return f"FRS_{numero}_{minha_base[numero]['municipio']}"
    sap.mm.ml83(frs=["1001909519"], destino="C:/pdfs/", nome_arquivo=nome)
    # → FRS_1001909519_IPOJUCA.pdf

    # com município vindo da ML81N
    def nome(numero): return f"FRS_{numero}_{sap.mm.ml81n(numero).municipio}"
    sap.mm.ml83(frs=["1001909519"], destino="C:/pdfs/", nome_arquivo=nome)

TODO: implementar modo de impressão em lote (múltiplas FRS por execução).
      Atualmente a transação é chamada uma vez por FRS para garantir o ID
      fixo do checkbox (wnd[0]/usr/chk[1,6]). Em lote, os checkboxes variam
      de posição conforme a linha, exigindo lógica de mapeamento dinâmico
      da GuiUserArea (GuiLabel + GuiCheckbox filhos).
"""

import logging
import time
from enum import StrEnum
from pathlib import Path
from typing import Callable

import win32con
import win32gui

from sap_automation.components import MultiSelection
from sap_automation.transactions.base import Transaction

# ─── Constantes ───────────────────────────────────────────────────────────────

_TITULO_POPUP_WINDOWS = "Salvar Saída de Impressão como"
_PATH_CHECKBOX = "wnd[0]/usr/chk[1,6]"
_PATH_BTN_EXIBIR = "wnd[0]/tbar[1]/btn[17]"
_PATH_BTN_IMPRIMIR = "wnd[0]/tbar[0]/btn[86]"
_TIMEOUT_POPUP = 10  # segundos aguardando o popup Windows aparecer
_DELAY_APOS_SALVAR = 1.0  # segundos aguardando o SAP processar o salvamento


def _nome_padrao(numero_frs: str) -> str:
    """Nome padrão: FRS_{numero}. Usado quando nome_arquivo não é informado."""
    return f"FRS_{numero_frs}"


# ─── Enums ────────────────────────────────────────────────────────────────────


class ML83Filter(StrEnum):
    """
    Filtros disponíveis na tela de seleção da ML83.
    Segue o mesmo padrão de ML84Filter — usado internamente pelo MultiSelection.
    """

    FRS = "LBLNI"
    COD_ACEITACAO = "KZABN"
    PEDIDO = "EBELN"
    TIPO_DOCUMENTO = "BSART"
    FORNECEDOR = "LIFNR"
    DATA_DOCUMENTO = "BEDAT"


# ----------------------------------------------
# HELPER PARA RESOLVER BOTÃO DE SELEÇÃO MÚLTIPLA
# ----------------------------------------------
def build_button_id(field: ML83Filter) -> str:
    return f"wnd[0]/usr/btn%_S_{field}_%_APP_%-VALU_PUSH"


# =======================
# CLASSE PRINCIPAL
# =======================
class ML83(Transaction):
    """
    Transação ML83 — Impressão de FRS como PDF.

    Usa o padrão Builder (igual à ML84) para configurar filtros antes
    de chamar run(). Cada chamada processa uma FRS por vez.

    Uso
    ---
        resultado = (
            ML83(session, destino="C:/pdfs/")
            .filter_frs(["1001909519"])
            .run()
        )
        # resultado: list[Path] com os arquivos gerados

    Nomenclatura customizada
    -------------------------
        def meu_nome(numero_frs):
            return f"FRS_{numero_frs}_IPOJUCA"

        ML83(session, destino="C:/pdfs/", nome_arquivo=meu_nome)
            .filter_frs(["1001909519"])
            .run()
    """

    def __init__(
        self,
        session,
        destino: str | Path,
        nome_arquivo: Callable[[str], str] = _nome_padrao,
    ):
        """
        Parâmetros
        ----------
        session      : SAPSession — sessão SAP ativa
        destino      : str | Path — pasta onde os PDFs serão salvos
        nome_arquivo : Callable[[str], str] — recebe o número da FRS,
                       retorna o nome do arquivo sem extensão.
                       Default: "FRS_{numero_frs}"
        """
        super().__init__(session)
        self.destino = Path(destino)
        self.nome_arquivo = nome_arquivo
        self._filters: dict[ML83Filter, list[str]] = {}
        self.logger = logging.getLogger("sap.mm.ml83")

        if not self.destino.exists():
            raise ValueError(f"Pasta de destino não encontrada: {self.destino}")

    # ------------------------------------------------------------------
    # BUILDER — configuração de filtros
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

        Retorna
        -------
        list[Path]
            Caminhos dos arquivos PDF gerados com sucesso.
            FRS que falharam são logadas como warning mas não interrompem
            o processamento das demais.
        """
        self._apply_filters()
        self._run()

        # após F8, a tela de resultados exibe as FRS encontradas
        # cada FRS é processada individualmente para garantir ID fixo do checkbox
        return self._processar_resultados()

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

    # ----------
    def _run(self):
        """Executa a pesquisa (F8)."""
        self.session.send_vkey(8)

    # ----------
    def _processar_resultados(self) -> list[Path]:
        """
        Itera sobre as FRS na tela de resultados e gera o PDF de cada uma.

        Estrutura da GuiUserArea
        ------------------------
        A tela de resultados mistura linhas de cabeçalho de pedido (laranja)
        e linhas de FRS. O padrão observado é:

            chk[1,N]  → checkbox de seleção para impressão (coluna 1)
            lbl[3,N]  → número da FRS correspondente (coluna 3)
            chk[20,N] → checkbox de aceite — ignorado

        Linhas sem chk[1,N] são cabeçalhos de pedido — ignoradas.

        Estratégia
        ----------
        1. Enumera todos os componentes da GuiUserArea via Children
        2. Filtra checkboxes da coluna 1 (chk[1,N]) — um por FRS
        3. Para cada um, lê lbl[3,N] para obter o número da FRS
        4. Seleciona o checkbox, clica em Exibir saída, salva PDF, F3
        """
        arquivos_gerados: list[Path] = []

        # mapeia as linhas que contêm FRS imprimíveis
        frs_por_linha = self._mapear_frs()

        if not frs_por_linha:
            self.logger.warning("Nenhuma FRS encontrada na tela de resultados")
            return []

        self.logger.info(
            f"{len(frs_por_linha)} FRS encontrada(s): {list(frs_por_linha.values())}"
        )

        for linha, numero_frs in frs_por_linha.items():
            self.logger.info(f"Processando FRS {numero_frs} (linha {linha})")

            chk_path = f"wnd[0]/usr/chk[1,{linha}]"

            try:
                # seleciona o checkbox desta FRS
                self.session.find(chk_path).selected = True

                # clica em "Exibir saída"
                self.session.find(_PATH_BTN_EXIBIR).press()

                # na tela de visualização, clica em "Imprimir"
                self.session.find(_PATH_BTN_IMPRIMIR).press()

                # salva o PDF via popup Windows
                nome = self.nome_arquivo(numero_frs)
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

    def _mapear_frs(self) -> dict[int, str]:
        """
        Enumera a GuiUserArea e retorna um dicionário {linha: numero_frs}
        para todas as FRS imprimíveis encontradas na tela de resultados.

        Lógica
        ------
        Itera pelos filhos da GuiUserArea buscando elementos cujo ID
        corresponde ao padrão chk[1,N] (checkbox de seleção, coluna 1).
        Para cada um, lê lbl[3,N] na mesma linha N para obter o número
        da FRS. Checkboxes na coluna 20 (aceite) são ignorados.

        Retorna dict ordenado por linha para garantir processamento sequencial.
        """
        import re

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

                # busca por chk[1,N] — checkbox de seleção (coluna 1)
                m = re.search(r"chk\[1,(\d+)\]", child_id)
                if not m:
                    continue

                linha = int(m.group(1))

                # lê o número da FRS em lbl[3,N] — mesma linha, coluna 3
                lbl_path = f"wnd[0]/usr/lbl[3,{linha}]"
                numero_frs = self.session.get_text(lbl_path).strip()

                if numero_frs:
                    resultado[linha] = numero_frs
                    self.logger.debug(f"FRS mapeada: linha={linha} numero={numero_frs}")

            except Exception as e:
                self.logger.debug(f"Elemento {i} ignorado: {e}")
                continue

        return dict(sorted(resultado.items()))

    def _ler_numero_frs(self, linha: int) -> str:
        """
        Lê o número da FRS na linha informada.

        Na tela de resultados da ML83, o número da FRS está em uma
        GuiLabel na coluna 6 da linha correspondente.
        """
        path = f"wnd[0]/usr/lbl[6,{linha}]"
        return self.session.get_text(path).strip()

    def _salvar_popup_windows(self, caminho_completo: str):
        """
        Interage com o popup nativo do Windows "Salvar Saída de Impressão como".

        Estratégia: em vez de navegar pela hierarquia de handles (frágil para
        diálogos modernos do Windows), traz o popup para frente e usa
        SendKeys para digitar o caminho e confirmar com Enter.

        Fluxo:
            1. Aguarda o popup aparecer
            2. Traz para frente (SetForegroundWindow)
            3. Abre o campo de nome com Ctrl+L (atalho universal do Explorer)
            4. Digita o caminho completo
            5. Confirma com Enter (salva o arquivo)

        Parâmetros
        ----------
        caminho_completo : str — caminho absoluto do arquivo a ser salvo,
                           incluindo nome e extensão (.pdf).

        Lança
        -----
        TimeoutError se o popup não aparecer dentro de _TIMEOUT_POPUP segundos.
        """
        import win32api
        import win32process

        self.logger.debug(f"Aguardando popup Windows: {_TITULO_POPUP_WINDOWS!r}")

        hwnd = self._aguardar_janela(_TITULO_POPUP_WINDOWS, _TIMEOUT_POPUP)

        # traz o popup para frente — necessário para SendKeys funcionar
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)

        # usa SendMessage com WM_SETTEXT diretamente no Edit dentro do ComboBox
        # o ComboBox de nome do arquivo é o último Edit da hierarquia do popup
        hwnd_edit = self._find_edit_recursivo(hwnd)
        if hwnd_edit:
            # abordagem 1: WM_SETTEXT direto no Edit (sem focar o campo)
            win32gui.SendMessage(hwnd_edit, win32con.WM_SETTEXT, 0, caminho_completo)
            self.logger.debug(f"Caminho preenchido via WM_SETTEXT: {caminho_completo}")
        else:
            # abordagem 2: fallback via teclado — seleciona tudo e digita
            self.logger.debug("Edit não encontrado — usando fallback via teclado")
            import win32clipboard

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(caminho_completo)
            win32clipboard.CloseClipboard()

            # Ctrl+A para selecionar texto existente, Ctrl+V para colar
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(ord("A"), 0, 0, 0)
            win32api.keybd_event(ord("A"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(ord("V"), 0, 0, 0)
            win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.2)

        # confirma com Enter — equivale a clicar em Salvar
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        self.logger.debug("Enter enviado — salvamento confirmado")

        # aguarda o SAP processar o salvamento antes de continuar
        time.sleep(_DELAY_APOS_SALVAR)

    def _find_edit_recursivo(self, hwnd_pai: int) -> int | None:
        """
        Busca recursivamente o primeiro campo Edit dentro de uma janela.

        Necessário porque o campo de nome do arquivo no diálogo moderno
        do Windows fica aninhado em múltiplos níveis (ComboBox dentro de
        FloatNotifySink), não como filho direto do popup.
        """
        resultado = []

        def callback(hwnd, _):
            if win32gui.GetClassName(hwnd) == "Edit":
                resultado.append(hwnd)

        win32gui.EnumChildWindows(hwnd_pai, callback, None)
        return resultado[0] if resultado else None

    def _aguardar_janela(self, titulo: str, timeout: float) -> int:
        """
        Aguarda uma janela Windows com o título informado aparecer.

        Retorna o handle (hwnd) da janela encontrada.
        Lança TimeoutError se não encontrar dentro do timeout.
        """
        inicio = time.time()
        while time.time() - inicio < timeout:
            hwnd = win32gui.FindWindow(None, titulo)
            if hwnd:
                self.logger.debug(f"Popup encontrado: hwnd={hwnd}")
                return hwnd
            time.sleep(0.3)

        raise TimeoutError(
            f"Popup {titulo!r} não apareceu após {timeout}s. "
            "Verifique se o SAP abriu a janela de salvamento corretamente."
        )

    def _find_button(self, hwnd_pai: int, texto: str) -> int | None:
        """
        Localiza um botão filho pelo texto dentro de uma janela pai.

        Retorna o handle do botão, ou None se não encontrado.
        """
        resultado = []

        def callback(hwnd, _):
            classe = win32gui.GetClassName(hwnd)
            label = win32gui.GetWindowText(hwnd)
            if classe == "Button" and texto.lower() in label.lower():
                resultado.append(hwnd)

        win32gui.EnumChildWindows(hwnd_pai, callback, None)
        return resultado[0] if resultado else None
