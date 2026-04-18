from importlib.metadata import version

from .client.config import SAPConfig
from .client.connection import SAPConnection

__version__ = version("sap-automation")
