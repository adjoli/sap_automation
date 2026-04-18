import os
from dataclasses import dataclass

from sap_automation.exceptions import ConfigError


@dataclass
class SAPConfig:
    user: str
    password: str
    environment: str
    client: str
    language: str
    saplogon_path: str
    sap_window: str

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
            client=os.getenv("SAP_CLIENT", "400"),
            language=os.getenv("SAP_LANG", "PT"),
            saplogon_path=os.getenv(
                "SAPLOGON_PATH",
                r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
            ),
            sap_window=os.getenv("SAP_WINDOW", "SAP Logon 800"),
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
