from datetime import date

from pydantic import BaseModel, computed_field, field_validator

from sap_automation.core.converters import parse_sap_float


class Gestor(BaseModel):
    """Representa um gerente ou fiscal de contrato."""

    chave: str
    nome: str


class Contrato(BaseModel):
    """
    Representa um contrato SAP retornado pela transação ME33K.

    Campos calculados
    -----------------
    dias_restantes : calculado automaticamente a partir de data_fim_contrato.
                     Negativo quando o contrato já está vencido.
    """

    # identificação
    num_contrato: str
    status: str | None = None
    tlc: str | None = None

    # fornecedor
    num_fornecedor: str | None = None
    nome_fornecedor: str | None = None

    # financeiro
    valor_total: float = 0.0
    valor_consumido: float = 0.0
    saldo: float = 0.0

    # vigência
    data_inicio_contrato: date | None = None
    data_fim_contrato: date | None = None

    # relações
    gerentes: list[Gestor] = []
    fiscais: list[Gestor] = []

    # ── validadores ───────────────────────────────────────────────────────────

    @field_validator("valor_total", "valor_consumido", "saldo", mode="before")
    @classmethod
    def parse_valor(cls, value):
        """Converte string SAP (1.234,56) para float."""
        if isinstance(value, str):
            return parse_sap_float(value) or 0.0
        return value or 0.0

    # ── campos calculados ─────────────────────────────────────────────────────

    @computed_field
    @property
    def dias_restantes(self) -> int | None:
        """
        Dias restantes até o fim do contrato.
        Negativo quando o contrato já está vencido.
        Retorna None se data_fim_contrato não estiver disponível.
        """
        if self.data_fim_contrato is None:
            return None
        return (self.data_fim_contrato - date.today()).days

    # ── serialização ──────────────────────────────────────────────────────────

    # def __str__(self) -> str:
    #     return f"[{self.num_contrato}] - {self.nome_fornecedor or '?'}"

    def as_dict(self) -> dict:
        return self.model_dump()

    def as_json(self) -> str:
        return self.model_dump_json()
