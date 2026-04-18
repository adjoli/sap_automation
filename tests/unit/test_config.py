import os

import pytest

from sap_automation.client.config import SAPConfig
from sap_automation.exceptions import ConfigError


def test_config_loads_prd(monkeypatch):
    monkeypatch.setenv("SAP_USER", "user")
    monkeypatch.setenv("SAP_PASSWD_PRD", "123")
    monkeypatch.setenv("SAP_ENV", "PRD")

    config = SAPConfig.from_env()

    assert config.user == "user"
    assert config.password == "123"
    assert config.environment == "PRD"


def test_config_switches_to_qas(monkeypatch):
    monkeypatch.setenv("SAP_USER", "user")
    monkeypatch.setenv("SAP_PASSWD_QAS", "abc")
    monkeypatch.setenv("SAP_ENV", "QAS")

    config = SAPConfig.from_env()

    assert config.password == "abc"


# @pytest.mark.skip
def test_config_fails_without_password(monkeypatch):
    monkeypatch.setenv("SAP_USER", "user")
    monkeypatch.setenv("SAP_ENV", "PRD")

    with pytest.raises(ConfigError):
        SAPConfig.from_env()
