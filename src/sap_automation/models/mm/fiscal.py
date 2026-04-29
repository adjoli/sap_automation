from pydantic import BaseModel


class Fiscal(BaseModel):
    chave: str
    nome: str
