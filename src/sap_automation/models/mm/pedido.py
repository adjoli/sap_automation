from datetime import date
from typing import List

from pydantic import BaseModel


class ItemPedido(BaseModel):
    item: str
    material: str | None
    descricao: str | None
    quantidade: float | None
    dt_remessa: date | None
    unidade: str | None
    valor: float | None


class Pedido(BaseModel):
    numero: str
    fornecedor: str | None
    data: date | None
    valor_total: float | None
    itens: List[ItemPedido]
