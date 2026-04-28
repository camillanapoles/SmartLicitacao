"""CNAE to SmartLic sector mapping.

Maps Brazilian CNAE (Classificação Nacional de Atividades Econômicas)
codes to SmartLic sector IDs used by the search pipeline.

Lookup architecture (DATA-CNAE-001):
    L1: in-process TTL cache (1h, ``maxsize=2048``) — populated lazily
        from the DB, invalidated by the Redis pubsub listener spawned
        on first use.
    L2: ``public.cnae_setor_mapping`` table (Supabase) — source of
        truth for production lookups.
    L3 (fallback): ``_LEGACY_CNAE_TO_SETOR`` snapshot baked into this
        module — used only when (a) the DB is unreachable and the
        cache is cold, or (b) ``CNAE_DB_LOOKUP_ENABLED=false`` (kill
        switch for emergency rollback).  This snapshot is also the
        single source of truth for the seed migration
        (scripts/generate_cnae_seed.py) and the AC15 snapshot
        regression test.

Public API (kept stable for backward compatibility — DATA-CNAE-001 AC6):
    ``map_cnae_to_setor(cnae)`` — synchronous, returns sector_id.
    ``get_setor_name(setor_id)`` — synchronous, returns human label.
    ``invalidate_cnae_cache(cnae=None)`` — drop one entry or all.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy snapshot — source of truth for the seed migration AND the
# fallback when the DB is unreachable.  DO NOT delete; downstream:
#   * scripts/generate_cnae_seed.py (AC4)
#   * backend/tests/test_cnae_mapping_db.py (AC15)
# ---------------------------------------------------------------------------
_LEGACY_CNAE_TO_SETOR: dict[str, str] = {
    # Engenharia / Construção Civil
    "4120": "engenharia",    # Construção de edifícios
    "4211": "engenharia",    # Construção de rodovias e ferrovias
    "4212": "engenharia",    # Construção de obras de arte especiais
    "4213": "engenharia",    # Obras de urbanização - ruas, praças e calçadas
    "4221": "engenharia",    # Construção de redes de abastecimento de água
    "4222": "engenharia",    # Construção de redes de abastecimento de água e saneamento
    "4223": "engenharia",    # Construção de redes de transportes por dutos
    "4291": "engenharia",    # Obras portuárias, marítimas e fluviais
    "4292": "engenharia",    # Montagem de instalações industriais
    "4299": "engenharia",    # Outras obras de engenharia civil não especificadas
    "4311": "engenharia",    # Demolição e preparação de canteiros de obras
    "4312": "engenharia",    # Perfurações e sondagens
    "4313": "engenharia",    # Obras de terraplenagem
    "4319": "engenharia",    # Serviços de preparação do terreno NEC
    "4321": "engenharia",    # Instalações elétricas
    "4322": "engenharia",    # Instalações hidráulicas, ventilação e refrigeração
    "4329": "engenharia",    # Outras instalações em construções NEC
    "4391": "engenharia",    # Obras de fundações
    "4399": "engenharia",    # Serviços especializados para construção NEC
    "7111": "engenharia",    # Serviços de arquitetura
    "7112": "engenharia",    # Serviços de engenharia
    "7119": "engenharia",    # Atividades técnicas relacionadas à engenharia e arquitetura
    # Vestuário / Uniformes
    "4781": "vestuario",     # Comércio varejista de artigos de vestuário e acessórios
    "1412": "vestuario",     # Confecção de peças de vestuário, exceto roupas íntimas
    "1413": "vestuario",     # Confecção de roupas íntimas
    "1421": "vestuario",     # Fabricação de meias
    "1422": "vestuario",     # Fabricação de artigos do vestuário, produzidos em malharias
    # Facilities / Limpeza
    "8121": "servicos_prediais",  # Limpeza em prédios e em domicílios
    "8122": "servicos_prediais",  # Imunização e controle de pragas urbanas
    "8129": "servicos_prediais",  # Limpeza e conservação de logradouros e vias públicas
    "8130": "servicos_prediais",  # Atividades paisagísticas
    # Vigilância / Segurança
    "8011": "vigilancia",    # Atividades de vigilância e segurança privada
    "8012": "vigilancia",    # Atividades de transporte de valores
    # Saúde / Hospitalar — legacy alias preserved (AC15 byte-equivalence)
    "3250": "saude",         # Fabricação de instrumentos e materiais para uso médico
    "4644": "saude",         # Comércio atacadista de instrumentos e materiais para uso médico
    "4645": "saude",         # Comércio atacadista de instrumentos e materiais odontológicos
    "8610": "saude",         # Atividades de atendimento hospitalar
    "8621": "saude",         # Serviços ambulatoriais providos por médicos e odontólogos
    "8630": "saude",         # Atividades de atenção ambulatorial executadas por outros profissionais da saúde
    # Alimentação / Merenda
    "1011": "alimentos",     # Abate de reses, exceto suínos
    "1091": "alimentos",     # Fabricação de produtos de panificação e confeitaria
    "4639": "alimentos",     # Comércio atacadista de produtos alimentícios em geral
    "4711": "alimentos",     # Comércio varejista de produtos alimentícios em geral
    # TI / Informática
    "6201": "informatica",   # Desenvolvimento de programas de computador sob encomenda
    "6202": "informatica",   # Desenvolvimento e licenciamento de programas de computador
    "6209": "informatica",   # Suporte técnico, manutenção e outros serviços em TI
    "6311": "informatica",   # Tratamento de dados, provedores de serviços de aplicação
    "6319": "informatica",   # Portais, provedores de conteúdo e outros serviços de informação
    # Equipamentos / Eletroeletrônicos — legacy alias preserved
    "2710": "equipamentos",  # Fabricação de geradores, transformadores, motores elétricos
    "2759": "equipamentos",  # Fabricação de outros aparelhos eletrodomésticos NEC
    "2861": "equipamentos",  # Fabricação de ferramentas
    # Transporte / Logística — legacy alias preserved
    "4921": "transporte",    # Transporte rodoviário coletivo de passageiros, com itinerário fixo, municipal
    "4922": "transporte",    # Transporte rodoviário coletivo de passageiros, intermunicipal
    "4924": "transporte",    # Transporte escolar
    "4929": "transporte",    # Outros transportes rodoviários de passageiros NEC
    "4930": "transporte",    # Transporte rodoviário de carga
    # Administração Pública (compradores) — mapear para engenharia como setor mais frequente
    "8411": "engenharia",    # Administração pública em geral
    "8412": "engenharia",    # Regulação das atividades de saúde, educação, serviços culturais
    "8413": "engenharia",    # Regulação das atividades econômicas
}

# Reverse mapping: sector descriptions for user feedback.  Kept in
# code (not in DB) because copy is part of the front-end UX surface.
SETOR_NAMES: dict[str, str] = {
    "engenharia": "Engenharia, Projetos e Obras",
    "vestuario": "Vestuário e Uniformes",
    "servicos_prediais": "Serviços Prediais e Facilities",
    "vigilancia": "Vigilância e Segurança",
    "equipamentos": "Equipamentos",
    "alimentos": "Alimentos e Merenda",
    "informatica": "TI e Sistemas",
    "saude": "Saúde e Hospitalar",
    "transporte": "Transporte e Logística",
}

DEFAULT_FALLBACK_SETOR = "geral"

# Redis pubsub channel published by /v1/admin/cnae-mapping mutations
# (DATA-CNAE-001 AC9).  Subscribers drop their TTL caches.
CNAE_INVALIDATION_CHANNEL = "cnae_mapping:invalidate"


# ---------------------------------------------------------------------------
# TTL cache (no external dependency — implementing a tiny LRU+TTL avoids
# adding `cachetools` to requirements.txt for a single use site).
# ---------------------------------------------------------------------------
class _TTLCache:
    """Thread-safe LRU+TTL cache.

    A miss returns ``_MISS`` (a private sentinel object) so callers
    can distinguish "we cached the absence of a row" (a valid CNAE
    answered with ``DEFAULT_FALLBACK_SETOR``) from "not in cache yet".
    """

    _MISS = object()

    def __init__(self, *, maxsize: int = 2048, ttl_seconds: float = 3600.0) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return self._MISS
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return self._MISS
            return value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            if len(self._store) >= self._maxsize and key not in self._store:
                # Evict ~10% oldest by expiration.  Keeps the cache
                # bounded under churn without per-access bookkeeping.
                victims = sorted(self._store.items(), key=lambda kv: kv[1][0])
                for victim_key, _ in victims[: max(1, self._maxsize // 10)]:
                    self._store.pop(victim_key, None)
            self._store[key] = (time.monotonic() + self._ttl, value)

    def pop(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


_cache = _TTLCache(maxsize=2048, ttl_seconds=3600.0)
_listener_started = False
_listener_lock = threading.Lock()


def _db_lookup_enabled() -> bool:
    """Kill switch for emergency rollback to the legacy in-memory dict.

    Default ON.  Set ``CNAE_DB_LOOKUP_ENABLED=false`` (or ``0``) in
    Railway env vars to bypass the DB entirely and use the legacy
    snapshot — useful if the DB is degraded and we want to drop
    onboarding latency back to memcache speed.
    """
    raw = os.getenv("CNAE_DB_LOOKUP_ENABLED", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def _extract_prefix(cnae: str) -> str:
    """Extract the 4-digit IBGE prefix from arbitrary CNAE shapes.

    Identical behaviour to the pre-DATA-CNAE-001 implementation:
        "4781"             -> "4781"
        "4781-4/00"        -> "4781"
        "47814"            -> "4781"
        "  4781  "         -> "4781"
        "4781-4/00 — text" -> "4781"
        "abc"              -> ""  (falls back to DEFAULT_FALLBACK_SETOR)
    """
    cleaned = cnae.strip().replace(" ", "")
    prefix = ""
    for ch in cleaned:
        if ch.isdigit():
            prefix += ch
            if len(prefix) == 4:
                break
    if len(prefix) < 4:
        return ""
    return prefix


def _query_db(prefix: str) -> Optional[str]:
    """Hit ``cnae_setor_mapping`` for a single prefix.

    Returns ``None`` on DB error or row missing.  Callers fall back to
    ``_LEGACY_CNAE_TO_SETOR.get(prefix)`` then ``DEFAULT_FALLBACK_SETOR``.

    The query is deliberately synchronous: the public API
    ``map_cnae_to_setor`` is sync, called from sync code paths in
    onboarding/empresa_publica.  The DB call is gated by the TTL
    cache so steady-state load is zero queries per request.
    """
    try:
        # Local import to avoid hard-coupling utils -> supabase_client
        # at module import time (keeps tests fast).
        from supabase_client import get_supabase
    except Exception as exc:  # pragma: no cover — import-time failure
        logger.debug("cnae_mapping: supabase_client import failed: %s", exc)
        return None

    try:
        sb = get_supabase()
        result = (
            sb.table("cnae_setor_mapping")
            .select("setor_id")
            .eq("cnae_code", prefix)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning(
            "cnae_mapping: DB lookup failed for cnae=%s, falling back: %s",
            prefix,
            exc,
        )
        return None

    rows = getattr(result, "data", None) or []
    if not rows:
        return None
    setor = rows[0].get("setor_id")
    if not isinstance(setor, str) or not setor:
        return None
    return setor


def _ensure_listener() -> None:
    """Lazily start a daemon thread subscribed to the invalidation channel.

    The thread spends its life listening on Redis pubsub and clears
    the in-process cache when an admin mutation publishes.  Failures
    (Redis unreachable) are swallowed — TTL eviction in the 1h cache
    window is the worst-case staleness either way.

    This is best-effort and intentionally fire-and-forget so unit
    tests that import the module never spin up a network listener
    unless ``CNAE_LISTENER_DISABLED`` is set (recommended for tests).
    """
    global _listener_started
    if _listener_started or os.getenv("CNAE_LISTENER_DISABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        return
    with _listener_lock:
        if _listener_started:
            return
        try:
            import redis as _redis  # noqa: F401 — availability probe
        except Exception:  # pragma: no cover — optional dependency
            _listener_started = True  # don't retry every call
            return

        def _run() -> None:
            try:
                from redis_pool import get_redis_pool  # type: ignore
                import asyncio

                async def _subscribe() -> None:
                    try:
                        pool = await get_redis_pool()
                        if pool is None:
                            return
                        pubsub = pool.pubsub()
                        await pubsub.subscribe(CNAE_INVALIDATION_CHANNEL)
                        async for message in pubsub.listen():
                            if message.get("type") != "message":
                                continue
                            payload = message.get("data") or b""
                            if isinstance(payload, bytes):
                                payload = payload.decode("utf-8", errors="replace")
                            if payload == "__all__":
                                _cache.clear()
                            else:
                                _cache.pop(payload)
                    except Exception as exc:  # pragma: no cover
                        logger.debug(
                            "cnae_mapping listener exited: %s", exc
                        )

                asyncio.run(_subscribe())
            except Exception as exc:  # pragma: no cover
                logger.debug("cnae_mapping listener boot failed: %s", exc)

        thread = threading.Thread(
            target=_run,
            name="cnae-mapping-invalidation-listener",
            daemon=True,
        )
        thread.start()
        _listener_started = True


def map_cnae_to_setor(cnae: str) -> str:
    """Map a CNAE code/string to a SmartLic sector id.

    Behaviour preserved verbatim from the pre-DATA-CNAE-001
    implementation (AC15 snapshot regression).  When the DB is
    unreachable and the cache is cold, falls through to
    ``_LEGACY_CNAE_TO_SETOR`` so the onboarding flow never breaks on
    transient DB unavailability.
    """
    if cnae is None:
        return DEFAULT_FALLBACK_SETOR

    prefix = _extract_prefix(str(cnae))
    if not prefix:
        return DEFAULT_FALLBACK_SETOR

    cached = _cache.get(prefix)
    if cached is not _TTLCache._MISS:
        # mypy can't know the sentinel narrowed type; return is always
        # str at this point because we only ever ``set()`` strings.
        assert isinstance(cached, str)
        return cached

    if _db_lookup_enabled():
        _ensure_listener()
        from_db = _query_db(prefix)
        if from_db is not None:
            _cache.set(prefix, from_db)
            return from_db
        # Row missing in DB or DB unreachable: cache the legacy answer
        # if we have one, else cache DEFAULT_FALLBACK_SETOR.  This
        # guarantees the second call for an unmapped CNAE doesn't
        # re-hit the DB.

    legacy = _LEGACY_CNAE_TO_SETOR.get(prefix, DEFAULT_FALLBACK_SETOR)
    _cache.set(prefix, legacy)
    return legacy


def get_setor_name(setor_id: str) -> str:
    """Get human-readable sector name."""
    return SETOR_NAMES.get(setor_id, setor_id.replace("_", " ").title())


def invalidate_cnae_cache(cnae: Optional[str] = None) -> None:
    """Drop one entry (by code) or the whole TTL cache.

    Called by the admin CRUD layer (routes/admin_cnae.py) after
    mutating a row, in addition to the Redis pubsub broadcast.  Local
    invalidation matters for the worker that just wrote: pubsub
    delivery is asynchronous, so without this call the writer worker
    would serve a stale entry until the next listener tick.
    """
    if cnae is None:
        _cache.clear()
        return
    prefix = _extract_prefix(str(cnae))
    if prefix:
        _cache.pop(prefix)


# ---------------------------------------------------------------------------
# Backward-compat: ``CNAE_TO_SETOR`` was a public symbol of the old
# module.  A read-only proxy keeps existing callers working while
# steering them toward map_cnae_to_setor() (which now goes through DB).
# ---------------------------------------------------------------------------
class _LegacyMappingProxy:
    """Read-only view of ``_LEGACY_CNAE_TO_SETOR`` for legacy importers."""

    def __getitem__(self, key: str) -> str:
        return _LEGACY_CNAE_TO_SETOR[key]

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return _LEGACY_CNAE_TO_SETOR.get(key, default)

    def __contains__(self, key: object) -> bool:
        return key in _LEGACY_CNAE_TO_SETOR

    def __iter__(self):
        return iter(_LEGACY_CNAE_TO_SETOR)

    def __len__(self) -> int:
        return len(_LEGACY_CNAE_TO_SETOR)

    def keys(self):
        return _LEGACY_CNAE_TO_SETOR.keys()

    def values(self):
        return _LEGACY_CNAE_TO_SETOR.values()

    def items(self):
        return _LEGACY_CNAE_TO_SETOR.items()


CNAE_TO_SETOR = _LegacyMappingProxy()
