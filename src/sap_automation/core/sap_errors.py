from sap_automation.exceptions import SAPRuntimeError


def raise_sap_error(session, default_msg="Erro desconhecido no SAP"):
    """
    Lê status bar e levanta exceção com mensagem do SAP.
    """
    message = session.get_status_bar()

    if message:
        raise SAPRuntimeError(message)

    raise SAPRuntimeError(default_msg)
