from datetime import date
from typing import List

from pydantic import BaseModel


class ItemPedido(BaseModel):
    item: str
    material: str | None = None
    descricao: str | None = None
    quantidade: float | None = None
    dt_remessa: date | None = None
    unidade: str | None = None
    valor: float | None = None


class Pedido(BaseModel):
    numero: str
    tipo: str | None = None
    cod_fornecedor: str | None = None
    desc_fornecedor: str | None = None
    data: date | None = None
    texto_breve: str | None = None
    grp_comprador: str | None = None
    status: str | None = None
    valor_total: float | None = None
    tlc: str | None = None
    itens: List[ItemPedido] = []
