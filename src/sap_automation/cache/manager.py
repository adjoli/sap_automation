"""
Camada de cache com TTL para dados extraídos do SAP.

Persiste resultados em SQLite para evitar consultas repetidas
ao SAP GUI enquanto os dados ainda são válidos.

Uso típico (interno — via SAP.MM):
    cache = CacheManager(db_path)
    key   = CacheManager.make_key("ml84", pedidos=["4500012345"])

    cached = cache.get(key)
    if cached is not None:
        return cached           # retorna do banco

    result = ML84(...).run()
    cache.set(key, result, ttl=CacheTTL.ML84)
    return result
"""

import hashlib
import json
import logging
import sqlite3
from enum import IntEnum
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("sap_automation.cache")


# ------------------------------------------------------------------
# TTLs padrão por operação (em segundos)
# ------------------------------------------------------------------
class CacheTTL(IntEnum):
    ML84  = 1 * 3600        #  1 hora  — listagem de FRS
    ML81N = 24 * 3600       # 24 horas — detalhes de uma FRS
    ME33K = 7 * 24 * 3600   #  7 dias  — contrato (raramente muda)
    ME23N = 4 * 3600        #  4 horas — pedido de compras

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    created_at REAL NOT NULL,
    ttl        INTEGER NOT NULL
);
"""


class CacheManager:
    """
    Cache com TTL baseado em SQLite.

    Parâmetros
    ----------
    db_path : Path | str
        Caminho para o arquivo .db. Criado automaticamente se não existir.
    default_ttl : int
        TTL padrão em segundos. Usado quando `set()` não recebe `ttl`.
    """

    def __init__(self, db_path: Path | str, default_ttl: int = CacheTTL.ML84):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl
        self._init_db()

    # ------------------------------------------------------------------
    # INTERFACE PÚBLICA
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """
        Retorna o valor cacheado para a chave, ou None se:
        - a chave não existe
        - o TTL expirou

        Entradas expiradas são removidas automaticamente.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data, created_at, ttl FROM cache WHERE key = ?",
                (key,),
            ).fetchone()

        if row is None:
            logger.debug("Cache MISS: %s", key)
            return None

        data_json, created_at, ttl = row
        age = datetime.now(timezone.utc).timestamp() - created_at

        if age > ttl:
            logger.debug("Cache EXPIRADO (%.0fs > %ds): %s", age, ttl, key)
            self._delete(key)
            return None

        logger.debug("Cache HIT (%.0fs restantes): %s", ttl - age, key)
        return json.loads(data_json)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Armazena `value` (serializável em JSON) com o TTL informado.
        Sobrescreve a entrada se a chave já existir.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        now = datetime.now(timezone.utc).timestamp()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache (key, data, created_at, ttl)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    data       = excluded.data,
                    created_at = excluded.created_at,
                    ttl        = excluded.ttl
                """,
                (key, json.dumps(value, ensure_ascii=False, default=str), now, effective_ttl),
            )

        logger.debug("Cache SET (ttl=%ds): %s", effective_ttl, key)

    def invalidate(self, key: str) -> None:
        """Remove uma entrada específica do cache."""
        self._delete(key)
        logger.debug("Cache INVALIDADO: %s", key)

    def invalidate_all(self) -> int:
        """
        Remove todas as entradas do cache.
        Retorna o número de entradas removidas.
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM cache")
            count = cursor.rowcount

        logger.info("Cache limpo: %d entradas removidas", count)
        return count

    def purge_expired(self) -> int:
        """
        Remove entradas com TTL expirado.
        Retorna o número de entradas removidas.
        """
        now = datetime.now(timezone.utc).timestamp()

        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE (? - created_at) > ttl",
                (now,),
            )
            count = cursor.rowcount

        if count:
            logger.debug("Cache: %d entradas expiradas removidas", count)

        return count

    # ------------------------------------------------------------------
    # CHAVE
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(method: str, **kwargs) -> str:
        """
        Gera uma chave determinística a partir do nome do método
        e dos seus parâmetros.

        A ordem dos kwargs não importa — os parâmetros são ordenados
        antes do hash para garantir que chamadas equivalentes produzam
        a mesma chave.

        Exemplos
        --------
            CacheManager.make_key("ml84", pedidos=["4500012345"], status="tudo")
            CacheManager.make_key("ml81n", frs="1001909519", mode="deep")
        """
        # Ordena para garantir determinismo independente da ordem dos kwargs
        canonical = json.dumps(
            {"method": method, "params": kwargs},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return f"{method}:{digest}"

    # ------------------------------------------------------------------
    # INTERNOS
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
