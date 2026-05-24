from datetime import date

from pydantic import BaseModel, field_validator

from .fiscal import Fiscal


# ===========================================
class FRS(BaseModel):
    numero: str
    pedido: str | None = None
    item_pedido: int | None = None
    texto_breve: str | None = None
    categoria: str | None = None
    local_prest_servico: str | None = None
    municipio: str | None = None
    UF: str | None = None
    liberada: bool = False
    resp_interno: str | None = None
    resp_externo: str | None = None
    valor: float = 0.0
    fiscais: list[Fiscal] = []

    # ---------------------------------
    # VALIDAÇÕES
    # ---------------------------------

    @field_validator("valor", mode="before")
    @classmethod
    def parse_valor(cls, value):
        if isinstance(value, str):
            return float(value.replace(".", "").replace(",", "."))
        return value

    # ---------------------------------
    # DOMÍNIO
    # ---------------------------------

    def is_liberada(self) -> bool:
        return self.liberada

    def has_fiscais(self) -> bool:
        return len(self.fiscais) > 0

    # ---------------------------------
    # SERIALIZAÇÃO
    # ---------------------------------

    def as_dict(self) -> dict:
        return self.model_dump()

    def as_json(self) -> str:
        return self.model_dump_json()


# ===========================================
class ML84Item(BaseModel):
    frs: str
    aceito: bool
    pedido: str | None
    item: str | None
    centro: str | None
    fornecedor_num: str | None
    fornecedor_nome: str | None
    data_doc: date | None
    valor_pedido: float
    data_remessa: date | None
    texto_breve: str
    valor: float
    criado_em: date | None
