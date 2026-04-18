import logging
import time
from functools import wraps


def retry(max_attempts=3, delay=1.0, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"[Tentativa {attempt}/{max_attempts}] erro: {e}")
                    if attempt == max_attempts:
                        raise
                    time.sleep(delay)

        return wrapper

    return decorator
