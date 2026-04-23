import logging

import pyperclip


class MultiSelection:
    TABS = {
        "include_values": "tabpSIVA",
        "include_ranges": "tabpINTL",
        "exclude_values": "tabpNOSV",
        "exclude_ranges": "tabpNOINT",
    }

    def __init__(self, session, window="wnd[1]"):
        self.logger = logging.getLogger("sap.multiselection")
        self.session = session
        self.window = window

    # ----------------------------------
    # CORE
    # ----------------------------------

    def clear(self):
        self.session.press(f"{self.window}/tbar[0]/btn[16]")

    def apply(self):
        self.session.press(f"{self.window}/tbar[0]/btn[8]")

    def cancel(self):
        self.session.press(f"{self.window}/tbar[0]/btn[12]")

    def _select_tab(self, tab_key: str):
        tab = f"{self.window}/usr/tabsTAB_STRIP/{self.TABS[tab_key]}"
        self.session.find(tab).select()

    # ----------------------------------
    # CLIPBOARD
    # ----------------------------------

    def _paste(self, values: list[str]):
        pyperclip.copy("\r\n".join(values))
        self.session.press(f"{self.window}/tbar[0]/btn[24]")  # colar

    def _paste_ranges(self, ranges: list[tuple[str, str]]):
        lines = [f"{low}\t{high}" for low, high in ranges]
        pyperclip.copy("\r\n".join(lines))
        self.session.press(f"{self.window}/tbar[0]/btn[24]")

    # ----------------------------------
    # API PRINCIPAL
    # ----------------------------------

    def include_values(self, values: list[str]):
        self._select_tab("include_values")
        self._paste(values)

    def include_ranges(self, ranges: list[tuple[str, str]]):
        raise NotImplementedError
        self._select_tab("include_ranges")
        self._paste_ranges(ranges)

    def exclude_values(self, values: list[str]):
        self._select_tab("exclude_values")
        self._paste(values)

    def exclude_ranges(self, ranges: list[tuple[str, str]]):
        raise NotImplementedError
        self._select_tab("exclude_ranges")
        self._paste_ranges(ranges)
