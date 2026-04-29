import tempfile
from pathlib import Path

from sap_automation.core.sap_errors import raise_sap_error


class SAPExporter:
    def __init__(self, session):
        self.session = session

    def export_html(self) -> str:
        """
        Exporta a lista de resultados exibida no SAP para HTML
        e retorna o conteúdo como string.

        Raises:
            RuntimeError: se o SAP não gerar o arquivo (lista vazia ou erro de exportação).
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sap_export.html"

            # SAP: Lista → Exportar → HTML
            self.session.find("wnd[0]/mbar/menu[0]/menu[1]/menu[2]").select()
            self.session.find(
                "wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[3,0]"
            ).select()
            self.session.send_vkey(0, window="wnd[1]")  # confirma formato

            # SAP exige barra no final do caminho
            self.session.set_text("wnd[1]/usr/ctxtDY_PATH", str(path.parent) + "\\")
            self.session.set_text("wnd[1]/usr/ctxtDY_FILENAME", path.name)
            self.session.send_vkey(0, window="wnd[1]")  # salva

            if not path.exists():
                raise_sap_error(
                    self.session,
                    "SAP não gerou o arquivo de exportação. "
                    "Verifique se a lista contém dados e se o caminho é válido.",
                )

            return path.read_text(encoding="utf-8")
