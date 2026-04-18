import logging


def setup_logging(level=logging.INFO):
    """
    Configura logging global da aplicação.
    Deve ser chamado no entrypoint.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str, **context):
    """
    Retorna um logger com contexto adicional.
    Exemplo:
        logger = get_logger("sap.mm.ml81n", frs="123")
    """

    base_logger = logging.getLogger(name)

    if not context:
        return base_logger

    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            context_str = " ".join(f"{k}={v}" for k, v in self.extra.items())
            return f"[{context_str}] {msg}", kwargs

    return ContextAdapter(base_logger, context)
