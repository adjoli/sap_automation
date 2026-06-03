import os
from dataclasses import dataclass, field
from pathlib import Path

from sap_automation.exceptions import ConfigError

# Localização padrão do banco de cache — na home do usuário,
# fora da estrutura de qualquer aplicação que consuma a biblioteca.
_DEFAULT_CACHE_DB = Path.home() / ".sap_automation" / "cache.db"


@dataclass
class SAPConfig:
    user: str
    password: str
    environment: str
    sap_conn_name_prd: str
    sap_conn_name_qas: str
    client: str
    language: str
    saplogon_path: str
    sap_window: str
    cache_db_path: Path = field(default_factory=lambda: _DEFAULT_CACHE_DB)

    @classmethod
    def from_env(cls):
        env = os.getenv("SAP_ENV", "PRD").upper()

        password_map = {
            "PRD": os.getenv("SAP_PASSWD_PRD"),
            "QAS": os.getenv("SAP_PASSWD_QAS"),
        }

        config = cls(
            user=os.getenv("SAP_USER"),
            password=password_map.get(env),
            environment=env,
            sap_conn_name_prd=os.getenv(
                "SAP_CONN_NAME_PRD", "F04 - SAP Scripting Transpetro PRD"
            ),
            sap_conn_name_qas=os.getenv(
                "SAP_CONN_NAME_QAS", "TEQ - SAP ECC Transpetro QAS"
            ),
            client=os.getenv("SAP_CLIENT", "400"),
            language=os.getenv("SAP_LANG", "PT"),
            saplogon_path=os.getenv(
                "SAPLOGON_PATH",
                r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
            ),
            sap_window=os.getenv("SAP_WINDOW", "SAP Logon 800"),
            cache_db_path=Path(
                os.getenv("SAP_CACHE_DB", str(_DEFAULT_CACHE_DB))
            ),
        )

        config.validate()
        return config

    def validate(self):
        missing = []

        if not self.user:
            missing.append("SAP_USER")

        if not self.password:
            missing.append(f"SAP_PASSWD_{self.environment}")

        if not self.saplogon_path:
            missing.append("SAPLOGON_PATH")

        if missing:
            raise ConfigError(
                f"Configuração inválida. Variáveis ausentes: {', '.join(missing)}"
            )
