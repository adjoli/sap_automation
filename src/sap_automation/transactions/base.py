from abc import ABC, abstractmethod


class Transaction(ABC):
    def __init__(self, session):
        self.session = session

    # ----------------------------------
    # CICLO DE VIDA
    # ----------------------------------
    def run(self):
        """
        Método padrão de execução segura.
        """
        try:
            self.session.go_home()
            self.start()
            return self.execute()
        finally:
            self.cleanup()

    def start(self):
        """
        Opcional: iniciar transação.
        Subclasses podem sobrescrever.
        """
        pass

    def cleanup(self):
        """
        Retorna ao SAP Easy Access.
        """
        try:
            self.session.go_home()
        except Exception:
            pass

    # ----------------------------------
    # CONTRATO
    # ----------------------------------
    @abstractmethod
    def execute(self):
        pass
