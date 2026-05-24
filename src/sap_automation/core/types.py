"""
Tipos utilitários compartilhados entre as camadas da biblioteca.
"""

from enum import StrEnum


class ReadMode(StrEnum):
    """
    Controla a profundidade da extração de dados em uma transação.

    SHALLOW — leitura rasa
        Extrai apenas os campos do cabeçalho e da primeira aba relevante.
        Mais rápido — adequado quando apenas alguns campos são necessários.

        ML81N: cabeçalho + DdsBásicos (municipio, UF, categoria)
               Pula: Vals., fiscais, popup de fiscais
        ME23N: apenas cabeçalho (status, liberado, texto_breve, tlc)
               Pula: tabela de itens, histórico de pagamento por item

    DEEP — leitura completa (padrão)
        Extrai todos os dados disponíveis, navegando por todas as abas.
        Comportamento atual — nenhuma mudança para código existente.

    Uso
    ---
        from sap_automation.core.types import ReadMode

        # raso — só município e UF
        frs = sap.mm.ml81n("1001909519", mode=ReadMode.SHALLOW)

        # completo (padrão — equivalente a não passar mode)
        frs = sap.mm.ml81n("1001909519")
        frs = sap.mm.ml81n("1001909519", mode=ReadMode.DEEP)
    """

    SHALLOW = "shallow"
    DEEP = "deep"
