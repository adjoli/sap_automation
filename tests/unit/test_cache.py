"""
Testes unitários para CacheManager.

Cobertos:
- get() em cache vazio          → None
- set() + get()                 → hit
- set() sobrescreve             → valor novo retornado
- get() com tipos diversos      → preserva listas, strings e números
- TTL expirado                  → None + entrada removida
- TTL por operação              → sobrepõe o default
- invalidate_all()              → cache esvaziado, retorna contagem
- make_key: determinismo        → mesmos args = mesma key
- make_key: ordem dos kwargs    → ordem não importa
- make_key: params diferentes   → keys diferentes
- make_key: métodos diferentes  → keys diferentes
- make_key: prefixo             → começa com nome do método
- CacheTTL: valores são int     → IntEnum compatível com int
- CacheTTL: ordem crescente     → ML84 < ME23N < ML81N < ME33K
- CacheTTL: compatível com set  → sem cast manual
- CacheTTL: default_ttl         → CacheManager usa ML84 por padrão
- Criação de diretório          → cria hierarquia de pastas automaticamente
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
    """Após expirar, get() remove a entrada — invalidate_all() deve retornar 0."""
    cache = CacheManager(db_path=tmp_path / "ttl2.db", default_ttl=1)
    cache.set("k", {"dados": True})
    time.sleep(1.1)
    cache.get("k")  # dispara a remoção
    assert cache.invalidate_all() == 0


def test_ttl_por_operacao_sobrepoe_default(tmp_path: Path):
    """TTL passado em set() deve sobrepor o default."""
    cache = CacheManager(db_path=tmp_path / "ttl3.db", default_ttl=3600)
    cache.set("k", "valor", ttl=1)
    time.sleep(1.1)
    assert cache.get("k") is None


# ------------------------------------------------------------------
# invalidate_all
# ------------------------------------------------------------------


def test_invalidate_all_limpa_tudo(cache: CacheManager):
    cache.set("k1", 1)
    cache.set("k2", 2)
    cache.set("k3", 3)

    removed = cache.invalidate_all()

    assert removed == 3
    assert cache.get("k1") is None
    assert cache.get("k2") is None
    assert cache.get("k3") is None


def test_invalidate_all_cache_vazio_retorna_zero(cache: CacheManager):
    assert cache.invalidate_all() == 0


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
# CacheTTL
# ------------------------------------------------------------------


def test_cache_ttl_valores_sao_inteiros():
    """CacheTTL deve se comportar como int em qualquer contexto."""
    for membro in CacheTTL:
        assert isinstance(membro, int)


def test_cache_ttl_valores_crescentes():
    """TTLs devem respeitar a ordem lógica: ML84 < ME23N < ML81N < ME33K."""
    assert CacheTTL.ML84 < CacheTTL.ME23N < CacheTTL.ML81N < CacheTTL.ME33K


def test_cache_ttl_compativel_com_set(cache: CacheManager):
    """CacheTTL deve ser aceito diretamente por cache.set() sem cast."""
    cache.set("k", "valor", ttl=CacheTTL.ML84)
    assert cache.get("k") == "valor"


def test_cache_ttl_default_e_ml84(tmp_path: Path):
    """O default_ttl do CacheManager deve ser CacheTTL.ML84."""
    c = CacheManager(db_path=tmp_path / "c.db")
    assert c._default_ttl == CacheTTL.ML84


# ------------------------------------------------------------------
# Criação automática de diretório
# ------------------------------------------------------------------


def test_cria_diretorio_pai_automaticamente(tmp_path: Path):
    db_path = tmp_path / "sub" / "dir" / "cache.db"
    CacheManager(db_path=db_path)
    assert db_path.exists()
