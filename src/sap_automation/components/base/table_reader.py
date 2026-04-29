from abc import ABC, abstractmethod
from typing import Any


class TableReader(ABC):
    """
    Interface para leitura de tabelas no SAP (TableControl, GridView, etc.)
    """

    @abstractmethod
    def to_list(self) -> list[dict[str, Any]]:
        """
        Retorna os dados da tabela como lista de dicionários.
        """
        pass

    def to_dataframe(self):
        import pandas as pd

        return pd.DataFrame(self.to_list())
