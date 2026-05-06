from sap_automation.components import SAPExplorer


class Screen:
    def __init__(self, session):
        self.session = session

    @property
    def explorer(self):
        return SAPExplorer(self.session.find("wnd[0]/usr"))
