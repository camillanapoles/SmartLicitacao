"""SEO Onda 2: Public stats endpoint for órgão comprador pages.

Aggregates bid statistics for a single government buying organization
from the local pncp_raw_bids datalake. Queries only local DB — no
external API calls. Public (no auth). Cache: InMemory 24h TTL per CNPJ.
"""

import asyncio
import logging
import re
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.budget import _run_with_budget

logger = logging.getLogger(__name__)
router = APIRouter(tags=["orgao-publico"])

_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h
_orgao_cache: dict[str, tuple[dict, float]] = {}

_CNPJ_RE = re.compile(r"^\d{14}$")

_ESFERA_LABELS = {"F": "Federal", "E": "Estadual", "M": "Municipal", "D": "Distrital"}

_STOPWORDS = frozenset({
    "de", "do", "da", "dos", "das", "para", "com", "por", "em", "a", "o", "e",
    "ou", "que", "na", "no", "nas", "nos", "um", "uma", "uns", "umas", "ao",
    "aos", "às", "se", "seu", "sua", "seus", "suas", "mais", "como", "mas",
    "foi", "não", "pelo", "pela", "pelos", "pelas", "este", "essa", "esse",
    "esta", "são", "ser", "ter", "tem", "num", "numa", "entre", "sobre",
    "quando", "também", "até", "já", "foi", "era", "está", "seu", "sua",
    "tipo", "cada", "todo", "toda", "todos", "todas", "outros", "outras",
    "outro", "outra", "cujo", "cuja", "qual", "quais", "cujos", "cujas",
})


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class LicitacaoRecente(BaseModel):
    objeto_compra: str
    modalidade_nome: str
    valor_total_estimado: Optional[float] = None
    data_publicacao: str
    uf: str


class ModalidadeCount(BaseModel):
    nome: str
    count: int


class FornecedorTop(BaseModel):
    nome: str
    cnpj: str
    total_contratos: int
    valor_total: float


class OrgaoStatsResponse(BaseModel):
    nome: str
    cnpj: str
    esfera: str
    uf: str
    municipio: str
    total_licitacoes: int
    licitacoes_30d: int
    licitacoes_90d: int
    licitacoes_365d: int
    valor_medio_estimado: float
    valor_total_estimado: float
    top_modalidades: list[ModalidadeCount]
    top_setores: list[str]
    ultimas_licitacoes: list[LicitacaoRecente]
    top_fornecedores: list[FornecedorTop] = []
    total_contratos_24m: int = 0
    valor_total_contratos_24m: float = 0.0
    aviso_legal: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

# STORY-417 Fase 1: Redis quick-win cache (15min TTL).
# The underlying query scans up to 5000 rows in pncp_raw_bids and was
# showing statement_timeout (57014) on 25 events during the 2026-04-10
# incident. In-memory cache alone is per-worker — Redis lets two
# Gunicorn workers share a single expensive computation, cutting p95
# latency on a cache miss from ~5s to ~0 for the other worker.
_REDIS_CACHE_TTL_SECONDS = 15 * 60  # 15 minutes
_REDIS_CACHE_PREFIX = "orgao_stats:v1:"

# RES-BE-015: Negative-cache TTL for DB saturation paths.
# 5min keeps Googlebot retry storms from re-saturating the pool while a
# successful crawl wave can refresh the cache normally.
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60
# Per-query budget. MUST be < Supabase service_role ``statement_timeout=15s``
# (FLOOR validated; memory feedback_pool_leak_caller_timeout_vs_sql_timeout).
_ORGAO_QUERY_BUDGET_S = 5.0


async def _redis_get(cnpj: str) -> Optional[dict]:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return None
        raw = await redis.get(_REDIS_CACHE_PREFIX + cnpj)
        if raw is None:
            return None
        import json as _json

        return _json.loads(raw)
    except Exception as e:
        logger.debug("STORY-417: orgao_stats Redis get failed (%s) — falling back", e)
        return None


async def _redis_set(cnpj: str, data: dict) -> None:
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            return
        import json as _json

        await redis.setex(
            _REDIS_CACHE_PREFIX + cnpj,
            _REDIS_CACHE_TTL_SECONDS,
            _json.dumps(data, default=str),
        )
    except Exception as e:
        logger.debug("STORY-417: orgao_stats Redis set failed (%s) — cache skipped", e)


@router.get(
    "/orgao/{cnpj}/stats",
    response_model=OrgaoStatsResponse,
    summary="Estatísticas públicas de um órgão comprador por CNPJ",
)
async def orgao_stats(cnpj: str):
    cnpj_clean = re.sub(r"\D", "", cnpj)

    if not _CNPJ_RE.match(cnpj_clean):
        raise HTTPException(status_code=400, detail="CNPJ inválido — informe 14 dígitos numéricos")

    # In-memory cache first (free, no network hop)
    cached = _get_cached(cnpj_clean)
    if cached:
        return OrgaoStatsResponse(**cached)

    # STORY-417 Fase 1: Redis cross-worker cache (15 min TTL).
    redis_cached = await _redis_get(cnpj_clean)
    if redis_cached is not None:
        _set_cached(cnpj_clean, redis_cached)
        return OrgaoStatsResponse(**redis_cached)

    data, partial = await _build_orgao_stats(cnpj_clean)
    if partial:
        # RES-BE-015: cache the unavailable shape under a short TTL so a
        # Googlebot retry storm does not re-saturate the pool, but the
        # next non-degraded request can still refresh the cache.
        _orgao_cache[cnpj_clean] = (data, time.time() - _CACHE_TTL_SECONDS + _NEGATIVE_CACHE_TTL_SECONDS)
    else:
        _set_cached(cnpj_clean, data)
        await _redis_set(cnpj_clean, data)
    return OrgaoStatsResponse(**data)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cached(key: str) -> Optional[dict]:
    if key not in _orgao_cache:
        return None
    data, ts = _orgao_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _orgao_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _orgao_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Top-setores extraction (word-frequency heuristic)
# ---------------------------------------------------------------------------

def _extract_top_setores(rows: list[dict], top_n: int = 5) -> list[str]:
    """Extract top meaningful words from objeto_compra across all bids."""
    word_counts: Counter = Counter()
    for row in rows:
        texto = (row.get("objeto_compra") or "").lower()
        # Remove punctuation / numbers
        texto = re.sub(r"[^\w\s]", " ", texto)
        texto = re.sub(r"\d+", " ", texto)
        for word in texto.split():
            if len(word) >= 4 and word not in _STOPWORDS:
                word_counts[word] += 1

    return [word for word, _ in word_counts.most_common(top_n)]


# ---------------------------------------------------------------------------
# Build stats
# ---------------------------------------------------------------------------

def _build_orgao_unavailable(cnpj: str) -> dict:
    """Minimal partial response when DB saturates / times out.

    Returns a payload that still validates against ``OrgaoStatsResponse`` so
    Googlebot receives a valid 200 (cached for 5 min) instead of 502 — a 502
    storm during the 2026-04-29 Stage 5 outage was the trigger that wedged
    the worker. Caller marks the result with negative-cache TTL.
    """
    return {
        "nome": "Órgão",
        "cnpj": cnpj,
        "esfera": "Não informado",
        "uf": "",
        "municipio": "Não informado",
        "total_licitacoes": 0,
        "licitacoes_30d": 0,
        "licitacoes_90d": 0,
        "licitacoes_365d": 0,
        "valor_medio_estimado": 0.0,
        "valor_total_estimado": 0.0,
        "top_modalidades": [],
        "top_setores": [],
        "ultimas_licitacoes": [],
        "top_fornecedores": [],
        "total_contratos_24m": 0,
        "valor_total_contratos_24m": 0.0,
        "aviso_legal": (
            "Dados temporariamente indisponíveis. Tente novamente em alguns minutos."
        ),
    }


async def _build_orgao_stats(cnpj: str) -> tuple[dict, bool]:
    """Query pncp_raw_bids and aggregate stats for a single órgão.

    Returns ``(data, partial)`` where ``partial=True`` means the underlying
    query exceeded ``_ORGAO_QUERY_BUDGET_S`` or failed; ``data`` is then a
    valid-shape unavailable payload. Callers should cache partial responses
    under ``_NEGATIVE_CACHE_TTL_SECONDS``.
    """
    def _sync_query() -> list[dict]:
        from supabase_client import get_supabase

        sb = get_supabase()
        resp = (
            sb.table("pncp_raw_bids")
            .select(
                "orgao_razao_social,"
                "esfera_id,"
                "uf,"
                "municipio,"
                "modalidade_nome,"
                "objeto_compra,"
                "valor_total_estimado,"
                "data_publicacao"
            )
            .eq("orgao_cnpj", cnpj)
            .eq("is_active", True)
            .limit(5000)
            .execute()
        )
        return resp.data or []

    try:
        rows = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=_ORGAO_QUERY_BUDGET_S,
            phase="route",
            source="orgao_publico.orgao_stats",
        )
    except asyncio.TimeoutError:
        logger.warning(
            "orgao_stats query exceeded %.1fs budget for %s — returning unavailable partial",
            _ORGAO_QUERY_BUDGET_S, cnpj,
        )
        return _build_orgao_unavailable(cnpj), True
    except Exception as e:
        logger.error("orgao_stats DB query failed for %s: %s", cnpj, e)
        return _build_orgao_unavailable(cnpj), True

    if not rows:
        raise HTTPException(status_code=404, detail="Órgão não encontrado no datalake")

    # Basic info from first row
    first = rows[0]
    nome = (first.get("orgao_razao_social") or "").strip() or "Não informado"
    esfera_raw = (first.get("esfera_id") or "").strip().upper()
    esfera = _ESFERA_LABELS.get(esfera_raw, esfera_raw or "Não informado")
    uf = (first.get("uf") or "").strip().upper()
    municipio = (first.get("municipio") or "").strip() or "Não informado"

    # Date windows
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_90d = now - timedelta(days=90)
    cutoff_365d = now - timedelta(days=365)

    licitacoes_30d = 0
    licitacoes_90d = 0
    licitacoes_365d = 0
    valores: list[float] = []
    modalidade_counter: Counter = Counter()

    # Sort for ultimas_licitacoes (desc by data_publicacao)
    rows_sorted = sorted(
        rows,
        key=lambda r: (r.get("data_publicacao") or ""),
        reverse=True,
    )

    for row in rows:
        # Date-window counts
        data_pub_str = (row.get("data_publicacao") or "")[:10]  # YYYY-MM-DD
        if data_pub_str:
            try:
                data_pub = datetime.fromisoformat(data_pub_str).replace(tzinfo=timezone.utc)
                if data_pub >= cutoff_365d:
                    licitacoes_365d += 1
                if data_pub >= cutoff_90d:
                    licitacoes_90d += 1
                if data_pub >= cutoff_30d:
                    licitacoes_30d += 1
            except ValueError:
                pass

        # Valor
        v = row.get("valor_total_estimado")
        if v is not None:
            try:
                fv = float(v)
                if fv > 0:
                    valores.append(fv)
            except (ValueError, TypeError):
                pass

        # Modalidade
        mod = (row.get("modalidade_nome") or "Não informado").strip()
        if mod:
            modalidade_counter[mod] += 1

    total_licitacoes = len(rows)
    valor_total = round(sum(valores), 2)
    valor_medio = round(valor_total / len(valores), 2) if valores else 0.0

    # Top 5 modalidades
    top_modalidades = [
        {"nome": nome_mod, "count": cnt}
        for nome_mod, cnt in modalidade_counter.most_common(5)
    ]

    # Top setores (word-frequency heuristic)
    top_setores = _extract_top_setores(rows, top_n=5)

    # Last 10 bids
    ultimas_licitacoes = []
    for row in rows_sorted[:10]:
        objeto = (row.get("objeto_compra") or "").strip()
        if len(objeto) > 200:
            objeto = objeto[:197] + "..."
        v = row.get("valor_total_estimado")
        valor_bid: Optional[float] = None
        if v is not None:
            try:
                fv = float(v)
                if fv > 0:
                    valor_bid = fv
            except (ValueError, TypeError):
                pass
        ultimas_licitacoes.append({
            "objeto_compra": objeto or "Não informado",
            "modalidade_nome": (row.get("modalidade_nome") or "Não informado").strip(),
            "valor_total_estimado": valor_bid,
            "data_publicacao": (row.get("data_publicacao") or "")[:10],
            "uf": (row.get("uf") or uf or "").strip().upper(),
        })

    # Contracts data from pncp_supplier_contracts (graceful: empty if backfill not done)
    contracts_data = await _fetch_contracts_data(cnpj)

    return {
        "nome": nome,
        "cnpj": cnpj,
        "esfera": esfera,
        "uf": uf,
        "municipio": municipio,
        "total_licitacoes": total_licitacoes,
        "licitacoes_30d": licitacoes_30d,
        "licitacoes_90d": licitacoes_90d,
        "licitacoes_365d": licitacoes_365d,
        "valor_medio_estimado": valor_medio,
        "valor_total_estimado": valor_total,
        "top_modalidades": top_modalidades,
        "top_setores": top_setores,
        "ultimas_licitacoes": ultimas_licitacoes,
        "top_fornecedores": contracts_data["top_fornecedores"],
        "total_contratos_24m": contracts_data["total_contratos_24m"],
        "valor_total_contratos_24m": contracts_data["valor_total_contratos_24m"],
        "aviso_legal": (
            "Dados de fontes públicas: Portal Nacional de Contratações Públicas (PNCP). "
            "Atualização diária."
        ),
    }, False


async def _fetch_contracts_data(orgao_cnpj: str, limit: int = 10) -> dict:
    """Query pncp_supplier_contracts for top suppliers and aggregate contract stats.

    Returns dict with 'top_fornecedores', 'total_contratos_24m', 'valor_total_contratos_24m'.
    Returns empty/zero gracefully when table is empty (during/before backfill) or
    when the query exceeds ``_ORGAO_QUERY_BUDGET_S`` (RES-BE-015 negative cache).
    """
    result = {"top_fornecedores": [], "total_contratos_24m": 0, "valor_total_contratos_24m": 0.0}

    def _sync_query() -> list[dict]:
        from supabase_client import get_supabase
        sb = get_supabase()
        # Aggregate by supplier CNPJ — Supabase doesn't support GROUP BY directly,
        # so we fetch up to 2000 rows and aggregate in Python (table grows large post-backfill;
        # a proper RPC would be ideal but this is zero-infra and works for cache=24h).
        resp = (
            sb.table("pncp_supplier_contracts")
            .select("ni_fornecedor,nome_fornecedor,valor_global")
            .eq("orgao_cnpj", orgao_cnpj)
            .eq("is_active", True)
            .limit(2000)
            .execute()
        )
        return resp.data or []

    try:
        rows = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=_ORGAO_QUERY_BUDGET_S,
            phase="route",
            source="orgao_publico.contracts_data",
        )
        if not rows:
            return result

        # Aggregate totals for the organ
        total_valor = 0.0
        for r in rows:
            try:
                total_valor += float(r.get("valor_global") or 0)
            except (ValueError, TypeError):
                pass

        result["total_contratos_24m"] = len(rows)
        result["valor_total_contratos_24m"] = round(total_valor, 2)

        # Aggregate by supplier
        from collections import defaultdict
        agg: dict[str, dict] = defaultdict(lambda: {"nome": "", "cnpj": "", "contratos": 0, "valor": 0.0})
        for r in rows:
            ni = r.get("ni_fornecedor") or ""
            if not ni:
                continue
            agg[ni]["cnpj"] = ni
            agg[ni]["nome"] = r.get("nome_fornecedor") or ni
            agg[ni]["contratos"] += 1
            try:
                agg[ni]["valor"] += float(r.get("valor_global") or 0)
            except (ValueError, TypeError):
                pass

        top = sorted(agg.values(), key=lambda x: x["valor"], reverse=True)[:limit]
        result["top_fornecedores"] = [
            {
                "nome": t["nome"],
                "cnpj": t["cnpj"],
                "total_contratos": t["contratos"],
                "valor_total": round(t["valor"], 2),
            }
            for t in top
            if t["valor"] > 0
        ]

    except asyncio.TimeoutError:
        logger.warning(
            "contracts_data query exceeded %.1fs budget for %s",
            _ORGAO_QUERY_BUDGET_S, orgao_cnpj,
        )
    except Exception as exc:
        logger.warning("contracts_data query failed for %s: %s", orgao_cnpj, exc)

    return result
