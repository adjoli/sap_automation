from pydantic import BaseModel, field_validator


class Fiscal(BaseModel):
    chave: str
    nome: str


class FRS(BaseModel):
    numero: str
    pedido: str | None = None
    texto_breve: str | None = None
    categoria: str | None = None
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
