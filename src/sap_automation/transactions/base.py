from abc import ABC, abstractmethod


class Transaction(ABC):
    def __init__(self, session):
        self.session = session

    @abstractmethod
    def execute(self):
        pass
