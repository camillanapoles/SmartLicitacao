"""SEO SITEMAP-MV-001: Materialized View-backed sitemap endpoints.

/sitemap/orgaos: orgao_cnpj de mv_sitemap_orgaos (≥5 bids, < 50ms)
/sitemap/contratos-orgao-indexable: mantém query ao vivo sobre
    pncp_supplier_contracts (sem MV específica para contratos por órgão)

Publico (sem auth). Cache: InMemory 24h TTL.
"""

import asyncio
import logging

import sentry_sdk

from pipeline.budget import _run_with_budget
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from metrics import record_sitemap_count
from routes._sitemap_cache_headers import SITEMAP_CACHE_HEADERS
from utils.cnpj_validator import is_valid_cnpj_format

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sitemap"])

_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h success
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60
# Budget reduzido: MV queries < 50ms, 5s é ampla margem de segurança
_BUDGET_S = 5.0
_sitemap_cache: dict[str, tuple[dict, float, float]] = {}  # key -> (data, stored_at, ttl)

_MAX_ORGAOS = 2000


class SitemapOrgaosResponse(BaseModel):
    orgaos: list[str]
    total: int
    updated_at: str


def _get_cached(key: str) -> Optional[dict]:
    if key not in _sitemap_cache:
        return None
    data, ts, ttl = _sitemap_cache[key]
    if time.time() - ts >= ttl:
        del _sitemap_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict, ttl: float = _CACHE_TTL_SECONDS) -> None:
    _sitemap_cache[key] = (data, time.time(), ttl)


def _empty_orgaos_response() -> dict:
    return {
        "orgaos": [],
        "total": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/sitemap/orgaos",
    response_model=SitemapOrgaosResponse,
    summary="Órgãos compradores com ≥1 licitação no datalake (para sitemap)",
)
async def sitemap_orgaos(response: Response):
    response.headers.update(SITEMAP_CACHE_HEADERS)
    cached = _get_cached("orgaos")
    if cached:
        record_sitemap_count("orgaos", len(cached.get("orgaos", [])))
        return SitemapOrgaosResponse(**cached)

    _fresh_fetch = False
    try:
        data = await _run_with_budget(
            asyncio.to_thread(_fetch_top_orgaos),
            budget=_BUDGET_S,
            phase="route",
            source="sitemap_orgaos.sitemap_orgaos",
        )
        _set_cached("orgaos", data, ttl=_CACHE_TTL_SECONDS)
        _fresh_fetch = True
    except asyncio.TimeoutError:
        logger.error(
            "sitemap_orgaos: budget %.0fs exceeded — returning 503 (not caching)",
            _BUDGET_S,
        )
        sentry_sdk.capture_message('sitemap_source_timeout', level='warning',
            tags={'endpoint': 'orgaos', 'outcome': 'timeout'})
        return JSONResponse(
            status_code=503,
            content={"detail": "sitemap_source_timeout"},
            headers={"Retry-After": "30"},
        )
    except Exception as exc:
        logger.error("sitemap_orgaos unexpected error: %s", exc)
        data = _empty_orgaos_response()
        _set_cached("orgaos", data, ttl=_NEGATIVE_CACHE_TTL_SECONDS)

    orgao_list = data.get("orgaos", [])
    # Alert 2: empty despite data — only probe when fresh fetch succeeded to avoid
    # double-querying a degraded DB that already caused timeout/error above.
    if _fresh_fetch and len(orgao_list) == 0:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("pncp_raw_bids").select("orgao_cnpj", count="exact").neq("orgao_cnpj", "").not_.is_("orgao_cnpj", "null").limit(0)
            )
            source_count = resp.count if hasattr(resp, 'count') and resp.count is not None else 0
            if source_count and source_count > 0:
                sentry_sdk.capture_message('sitemap_empty_despite_data', level='error',
                    tags={'endpoint': 'orgaos', 'source_count': source_count})
        except Exception:
            pass
        try:
            sb2 = get_supabase()
            resp2 = await sb_execute(
                sb2.table("pncp_raw_bids").select("data_publicacao").order("data_publicacao", desc=True).limit(1)
            )
            if resp2.data and len(resp2.data) > 0:
                raw = resp2.data[0].get("data_publicacao")
                if raw:
                    last_dt = datetime.fromisoformat(str(raw)[:10]).replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if age_seconds > 93600:
                        sentry_sdk.capture_message('sitemap_source_stale', level='warning',
                            tags={'endpoint': 'orgaos', 'age_hours': round(age_seconds / 3600, 1)})
        except Exception:
            pass

    # Alert 3: stale data — only probe when fresh fetch succeeded (not on timeout/error
    # paths, to avoid extra DB hits when the DB is already degraded).
    # Requires mv_sitemap_orgaos.last_seen column (added in migration
    # 20260510150000_sitemap_mv_orgaos_add_last_seen.sql).
    if _fresh_fetch:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("mv_sitemap_orgaos")
                .select("last_seen")
                .order("last_seen", desc=True)
                .limit(1)
            )
            if resp.data and len(resp.data) > 0 and resp.data[0].get("last_seen"):
                last_refresh = resp.data[0]["last_seen"]
                if isinstance(last_refresh, str):
                    last_refresh = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
                if last_refresh.tzinfo is None:
                    last_refresh = last_refresh.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - last_refresh).total_seconds()
                if age_seconds > 93600:  # 26h
                    sentry_sdk.capture_message('sitemap_mv_stale', level='warning',
                        tags={'endpoint': 'orgaos', 'age_hours': round(age_seconds/3600, 1)})
        except Exception:
            pass

    record_sitemap_count("orgaos", len(orgao_list))
    return SitemapOrgaosResponse(**data)


def _fetch_top_orgaos() -> dict:
    """Query mv_sitemap_orgaos for orgao_cnpj com ≥5 licitações em 12 meses.

    SEO-SITEMAP-MV-001: MV pré-agregada substitui RPC + fallback paginado.
    Query < 50ms.
    """
    try:
        from supabase_client import get_supabase

        sb = get_supabase()

        rows: list[str] = []
        page_size = 1000
        offset = 0
        while True:
            resp = (
                sb.table("mv_sitemap_orgaos")
                .select("cnpj")
                .order("cnpj")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not resp.data:
                break
            for r in resp.data:
                cnpj = (r.get("cnpj") or "").strip()
                if is_valid_cnpj_format(cnpj):
                    rows.append(cnpj)
            if len(resp.data) < page_size:
                break
            offset += page_size

        orgao_list = rows[:_MAX_ORGAOS]

        logger.info(
            "sitemap_orgaos (MV): %d órgãos from mv_sitemap_orgaos (páginas=%d)",
            len(orgao_list),
            (offset // page_size) if page_size else 0,
        )

        return {
            "orgaos": orgao_list,
            "total": len(orgao_list),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("sitemap_orgaos MV query failed: %s", e)
        return {
            "orgaos": [],
            "total": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# SEO-460: /sitemap/contratos-orgao-indexable — órgãos com contratos reais
#
# NOTA: Este endpoint NÃO foi convertido para MV porque não há MV específica
# para orgao_cnpj em pncp_supplier_contracts. O volume (~2k orgaos) e a query
# com índice idx_psc_orgao_cnpj mantém performance aceitável.
# Futuro: criar mv_sitemap_contratos_orgao se necessário.
# ---------------------------------------------------------------------------

_contratos_orgao_cache: dict[str, tuple[dict, float, float]] = {}  # key -> (data, stored_at, ttl)
_MAX_CONTRATOS_ORGAOS = 2000


class SitemapContratosOrgaoResponse(BaseModel):
    orgaos: list[str]
    total: int
    updated_at: str


@router.get(
    "/sitemap/contratos-orgao-indexable",
    response_model=SitemapContratosOrgaoResponse,
    summary="Órgãos compradores com contratos em pncp_supplier_contracts (para sitemap /contratos/orgao/)",
)
async def sitemap_contratos_orgao_indexable(response: Response):
    """Retorna CNPJs de órgãos com ≥1 contrato ativo em pncp_supplier_contracts.

    Diferente de /sitemap/orgaos (que usa mv_sitemap_orgaos/pncp_raw_bids), este
    endpoint consulta pncp_supplier_contracts — a tabela que alimenta
    /contratos/orgao/{cnpj}/stats. Garante que o sitemap só inclui URLs
    que retornam 200, eliminando os 794 404s reportados no GSC.
    Cache: 24h em memória.
    """
    response.headers.update(SITEMAP_CACHE_HEADERS)
    key = "contratos_orgao_indexable"
    cached_entry = _contratos_orgao_cache.get(key)
    if cached_entry:
        data, ts, ttl = cached_entry
        if time.time() - ts < ttl:
            record_sitemap_count("contratos-orgao-indexable", len(data.get("orgaos", [])))
            return SitemapContratosOrgaoResponse(**data)
        del _contratos_orgao_cache[key]

    _fresh_fetch = True
    try:
        data = await _run_with_budget(
            asyncio.to_thread(_fetch_contratos_orgao_indexable),
            budget=_BUDGET_S,
            phase="route",
            source="sitemap_orgaos.sitemap_contratos_orgao_indexable",
        )
        _contratos_orgao_cache[key] = (data, time.time(), _CACHE_TTL_SECONDS)
    except asyncio.TimeoutError:
        logger.error(
            "sitemap_contratos_orgao_indexable: budget %.0fs exceeded — returning 503 (not caching)",
            _BUDGET_S,
        )
        sentry_sdk.capture_message('sitemap_source_timeout', level='warning',
            tags={'endpoint': 'contratos-orgao-indexable', 'outcome': 'timeout'})
        return JSONResponse(
            status_code=503,
            content={"detail": "sitemap_source_timeout"},
            headers={"Retry-After": "30"},
        )
    except Exception as exc:
        logger.error("sitemap_contratos_orgao_indexable unexpected error: %s", exc)
        data = _empty_orgaos_response()
        _contratos_orgao_cache[key] = (data, time.time(), _NEGATIVE_CACHE_TTL_SECONDS)

    contratos_list = data.get("orgaos", [])
    if _fresh_fetch and len(contratos_list) == 0:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("pncp_supplier_contracts").select("id", count="exact").limit(0)
            )
            source_count = resp.count if hasattr(resp, 'count') and resp.count is not None else 0
            if source_count and source_count > 0:
                sentry_sdk.capture_message('sitemap_empty_despite_data', level='error',
                    tags={'endpoint': 'contratos-orgao-indexable', 'source_count': source_count})
        except Exception:
            pass

    record_sitemap_count("contratos-orgao-indexable", len(contratos_list))
    return SitemapContratosOrgaoResponse(**data)


def _fetch_contratos_orgao_indexable() -> dict:
    """Scan pncp_supplier_contracts para distinct orgao_cnpj com is_active=True.

    Mantém query ao vivo (sem MV) — não há MV específica para contratos
    por órgão. Performance aceitável com idx_psc_orgao_cnpj.
    """
    try:
        from supabase_client import get_supabase
        sb = get_supabase()

        counts: dict[str, int] = {}
        page_size = 1000
        offset = 0

        while len(counts) < _MAX_CONTRATOS_ORGAOS * 5:
            resp = (
                sb.table("pncp_supplier_contracts")
                .select("orgao_cnpj")
                .eq("is_active", True)
                .not_.is_("orgao_cnpj", "null")
                .neq("orgao_cnpj", "")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not resp.data:
                break
            for row in resp.data:
                cnpj = (row.get("orgao_cnpj") or "").strip()
                if is_valid_cnpj_format(cnpj):
                    counts[cnpj] = counts.get(cnpj, 0) + 1
            if len(resp.data) < page_size:
                break
            offset += page_size

        # Ordenar por volume de contratos (mais contratos = maior valor SEO)
        orgao_list = [
            cnpj
            for cnpj, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ][:_MAX_CONTRATOS_ORGAOS]

        logger.info(
            "sitemap_contratos_orgao_indexable: %d orgãos com contratos de %d distintos",
            len(orgao_list),
            len(counts),
        )

        return {
            "orgaos": orgao_list,
            "total": len(orgao_list),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("sitemap_contratos_orgao_indexable failed: %s", e)
        return {
            "orgaos": [],
            "total": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
