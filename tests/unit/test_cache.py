"""
Testes unitários para CacheManager.

Cobertos:
- get() em cache vazio       → None
- set() + get()              → hit
- TTL expirado               → None + entrada removida
- force via invalidate()     → None após invalidação
- make_key determinismo      → mesmos args = mesma key
- make_key ordem dos kwargs  → ordem não importa
- set() sobrescreve          → valor novo retornado
- invalidate_all()           → cache esvaziado
- purge_expired()            → só entradas expiradas removidas
"""

import time
from pathlib import Path

import pytest

from sap_automation.cache.manager import CacheManager, CacheTTL


# ------------------------------------------------------------------
# FIXTURE
# ------------------------------------------------------------------

@pytest.fixture
def cache(tmp_path: Path) -> CacheManager:
    """CacheManager apontando para banco temporário."""
    return CacheManager(db_path=tmp_path / "test_cache.db", default_ttl=60)


# ------------------------------------------------------------------
# get / set
# ------------------------------------------------------------------

def test_get_vazio_retorna_none(cache: CacheManager):
    assert cache.get("chave_inexistente") is None


def test_set_e_get_retorna_valor(cache: CacheManager):
    cache.set("k1", {"foo": "bar"})
    assert cache.get("k1") == {"foo": "bar"}


def test_set_sobrescreve_valor(cache: CacheManager):
    cache.set("k1", {"v": 1})
    cache.set("k1", {"v": 2})
    assert cache.get("k1") == {"v": 2}


def test_get_tipos_diversos(cache: CacheManager):
    """set/get preserva listas, strings e números."""
    cache.set("lista", [1, 2, 3])
    cache.set("texto", "hello")
    cache.set("numero", 42)

    assert cache.get("lista") == [1, 2, 3]
    assert cache.get("texto") == "hello"
    assert cache.get("numero") == 42


# ------------------------------------------------------------------
# TTL
# ------------------------------------------------------------------

def test_ttl_expirado_retorna_none(tmp_path: Path):
    cache = CacheManager(db_path=tmp_path / "ttl.db", default_ttl=1)
    cache.set("k", {"dados": True})

    time.sleep(1.1)

    assert cache.get("k") is None


def test_ttl_expirado_remove_entrada(tmp_path: Path):
    """Após expirar, a entrada não deve mais existir no banco."""
    cache = CacheManager(db_path=tmp_path / "ttl2.db", default_ttl=1)
    cache.set("k", {"dados": True})

    time.sleep(1.1)
    cache.get("k")  # dispara a remoção

    # purge_expired não deve encontrar nada para remover
    assert cache.purge_expired() == 0


def test_ttl_por_operacao_sobrepoe_default(tmp_path: Path):
    """TTL passado em set() deve sobrepor o default."""
    cache = CacheManager(db_path=tmp_path / "ttl3.db", default_ttl=3600)
    cache.set("k", "valor", ttl=1)

    time.sleep(1.1)

    assert cache.get("k") is None


# ------------------------------------------------------------------
# invalidate
# ------------------------------------------------------------------

def test_invalidate_remove_entrada(cache: CacheManager):
    cache.set("k1", "valor")
    cache.invalidate("k1")
    assert cache.get("k1") is None


def test_invalidate_chave_inexistente_nao_falha(cache: CacheManager):
    """invalidate em chave que não existe não deve lançar exceção."""
    cache.invalidate("nao_existe")  # não deve levantar


def test_invalidate_all_limpa_tudo(cache: CacheManager):
    cache.set("k1", 1)
    cache.set("k2", 2)
    cache.set("k3", 3)

    removed = cache.invalidate_all()

    assert removed == 3
    assert cache.get("k1") is None
    assert cache.get("k2") is None
    assert cache.get("k3") is None


# ------------------------------------------------------------------
# purge_expired
# ------------------------------------------------------------------

def test_purge_expired_remove_apenas_expirados(tmp_path: Path):
    cache = CacheManager(db_path=tmp_path / "purge.db", default_ttl=3600)

    cache.set("valido", "ok", ttl=3600)
    cache.set("expirado", "bye", ttl=1)

    time.sleep(1.1)

    removed = cache.purge_expired()

    assert removed == 1
    assert cache.get("valido") == "ok"
    assert cache.get("expirado") is None


# ------------------------------------------------------------------
# make_key
# ------------------------------------------------------------------

def test_make_key_determinismo():
    k1 = CacheManager.make_key("ml84", pedidos=["123"], status="tudo")
    k2 = CacheManager.make_key("ml84", pedidos=["123"], status="tudo")
    assert k1 == k2


def test_make_key_ordem_kwargs_nao_importa():
    k1 = CacheManager.make_key("ml84", status="tudo", pedidos=["123"])
    k2 = CacheManager.make_key("ml84", pedidos=["123"], status="tudo")
    assert k1 == k2


def test_make_key_params_diferentes_geram_keys_diferentes():
    k1 = CacheManager.make_key("ml84", pedidos=["111"])
    k2 = CacheManager.make_key("ml84", pedidos=["222"])
    assert k1 != k2


def test_make_key_metodos_diferentes_geram_keys_diferentes():
    k1 = CacheManager.make_key("ml84", pedidos=["123"])
    k2 = CacheManager.make_key("ml81n", pedidos=["123"])
    assert k1 != k2


def test_make_key_prefixo_contem_nome_do_metodo():
    key = CacheManager.make_key("ml84", pedidos=["123"])
    assert key.startswith("ml84:")


# ------------------------------------------------------------------
# Criação automática de diretório
# ------------------------------------------------------------------

def test_cria_diretorio_pai_automaticamente(tmp_path: Path):
    db_path = tmp_path / "sub" / "dir" / "cache.db"
    cache = CacheManager(db_path=db_path)
    cache.set("k", "v")
    assert db_path.exists()


# ------------------------------------------------------------------
# CacheTTL
# ------------------------------------------------------------------

def test_cache_ttl_valores_sao_inteiros():
    """CacheTTL deve se comportar como int em qualquer contexto."""
    assert isinstance(CacheTTL.ML84, int)
    assert isinstance(CacheTTL.ML81N, int)
    assert isinstance(CacheTTL.ME33K, int)
    assert isinstance(CacheTTL.ME23N, int)


def test_cache_ttl_valores_crescentes():
    """TTLs devem respeitar a ordem lógica: ML84 < ME23N < ML81N < ME33K."""
    assert CacheTTL.ML84 < CacheTTL.ME23N < CacheTTL.ML81N < CacheTTL.ME33K


def test_cache_ttl_compativel_com_set(cache: CacheManager):
    """CacheTTL deve ser aceito diretamente por cache.set() sem cast."""
    cache.set("k", "valor", ttl=CacheTTL.ML84)
    assert cache.get("k") == "valor"


def test_cache_ttl_default_e_ml84():
    """O default_ttl do CacheManager deve ser CacheTTL.ML84."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        c = CacheManager(db_path=Path(d) / "c.db")
        assert c._default_ttl == CacheTTL.ML84
