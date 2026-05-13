"""SEO SITEMAP-MV-001: Materialized View-backed sitemap endpoints.

/sitemap/cnpjs: orgao_cnpj de mv_sitemap_cnpjs (compradores, < 50ms)
/sitemap/fornecedores-cnpj: ni_fornecedor de mv_sitemap_fornecedores (fornecedores, < 50ms)

Antes (live aggregate, ~30-45s): RPC + fallback paginado — timeout sob SSG
Depois (MV pre-agregado, < 50ms): SELECT simples — sem timeout

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
# Negative cache: quando a MV falha (ex: pg_cron atrasado), retorna vazio
# por 5 min para evitar que o ISR rebuild sature o backend no mesmo padrão
# do PR #529 perfil-b2g hotfix.
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60
# Budget reduzido: MV queries < 50ms, 5s é ampla margem de segurança
_BUDGET_S = 5.0
_sitemap_cache: dict[str, tuple[dict, float, float]] = {}  # key -> (data, stored_at, ttl)

_MAX_CNPJS = 5000

# Seed list: CNPJs de empresas fornecedoras (B2G suppliers) com relatórios intel gerados.
# Estes aparecem PRIMEIRO no sitemap (prioridade sobre compradores/órgãos)
# para garantir indexação de fornecedores com conteúdo rico de contratos.
_SEED_SUPPLIER_CNPJS: list[str] = [
    "01721078000168",  # LCM Construções
    "07186297000170",  # CRV Construtora Rezende & Alvarenga
    "09225035000101",  # GJS Construções
    "18742098000118",  # Trena Terraplenagem
    "24515063000149",  # Extra Empreiteira
    "26420889000150",  # Gamarra Construtora
    "27735305000106",  # Infrainga Engenharia
    "33256335000124",  # Distriminas
    "39336452000184",  # Construsol Sobralense
    "42192677000119",  # LCA Infraestrutura
    "47673948000171",  # Borges Gomes
]


class SitemapCnpjsResponse(BaseModel):
    cnpjs: list[str]
    total: int
    updated_at: str


class SitemapFornecedoresCnpjResponse(BaseModel):
    cnpjs: list[str]
    total: int
    updated_at: str


_MAX_FORNECEDORES_CNPJS = 5000

_fornecedores_sitemap_cache: dict[str, tuple[dict, float, float]] = {}  # key -> (data, stored_at, ttl)


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


def _get_fornecedores_cached(key: str) -> Optional[dict]:
    if key not in _fornecedores_sitemap_cache:
        return None
    data, ts, ttl = _fornecedores_sitemap_cache[key]
    if time.time() - ts >= ttl:
        del _fornecedores_sitemap_cache[key]
        return None
    return data


def _set_fornecedores_cached(key: str, data: dict, ttl: float = _CACHE_TTL_SECONDS) -> None:
    _fornecedores_sitemap_cache[key] = (data, time.time(), ttl)


@router.get(
    "/sitemap/cnpjs",
    response_model=SitemapCnpjsResponse,
    summary="CNPJs com ≥1 licitação no datalake (para sitemap)",
)
async def sitemap_cnpjs(response: Response):
    response.headers.update(SITEMAP_CACHE_HEADERS)
    cached = _get_cached("cnpjs")
    if cached:
        record_sitemap_count("cnpjs", len(cached.get("cnpjs", [])))
        return SitemapCnpjsResponse(**cached)

    _fresh_fetch = True
    try:
        data = await _run_with_budget(
            asyncio.to_thread(_fetch_top_cnpjs),
            budget=_BUDGET_S,
            phase="route",
            source="sitemap_cnpjs.sitemap_cnpjs",
        )
        _set_cached("cnpjs", data, ttl=_CACHE_TTL_SECONDS)
    except asyncio.TimeoutError:
        logger.error(
            "sitemap_cnpjs: budget %.0fs exceeded — returning 503 (not caching)",
            _BUDGET_S,
        )
        sentry_sdk.capture_message('sitemap_source_timeout', level='warning',
            tags={'endpoint': 'cnpjs', 'outcome': 'timeout'})
        return JSONResponse(
            status_code=503,
            content={"detail": "sitemap_source_timeout"},
            headers={"Retry-After": "30"},
        )
    except Exception as exc:
        logger.error("sitemap_cnpjs unexpected error: %s", exc)
        data = _empty_cnpjs_response()
        _set_cached("cnpjs", data, ttl=_NEGATIVE_CACHE_TTL_SECONDS)

    cnpj_list = data.get("cnpjs", [])
    # Alert: empty despite data exists in source table (only on fresh fetches)
    if _fresh_fetch and len(cnpj_list) == 0:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("pncp_raw_bids").select("orgao_cnpj", count="exact").neq("orgao_cnpj", "").not_.is_("orgao_cnpj", "null").limit(0)
            )
            source_count = resp.count if hasattr(resp, 'count') and resp.count is not None else 0
            if source_count and source_count > 0:
                sentry_sdk.capture_message('sitemap_empty_despite_data', level='error',
                    tags={'endpoint': 'cnpjs', 'source_count': source_count})
        except Exception:
            pass
    # Alert: stale data - check max data_publicacao in source table (only on fresh fetches)
    if _fresh_fetch:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("pncp_raw_bids")
                .select("data_publicacao")
                .order("data_publicacao", desc=True)
                .limit(1)
            )
            if resp.data and len(resp.data) > 0:
                raw = resp.data[0].get("data_publicacao")
                if raw:
                    last_dt = datetime.fromisoformat(str(raw)[:10]).replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if age_seconds > 93600:
                        sentry_sdk.capture_message('sitemap_source_stale', level='warning',
                            tags={'endpoint': 'cnpjs', 'age_hours': round(age_seconds / 3600, 1)})
        except Exception:
            pass
    record_sitemap_count("cnpjs", len(cnpj_list))
    return SitemapCnpjsResponse(**data)


def _empty_cnpjs_response() -> dict:
    return {
        "cnpjs": [],
        "total": 0,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _merge_with_seed(buyer_cnpjs: list[str]) -> list[str]:
    """Merge seed supplier CNPJs (priority) with buyer CNPJs, dedup, cap at _MAX_CNPJS."""
    seen: set[str] = set()
    result: list[str] = []
    # Seed suppliers first — they have richer contract content
    for cnpj in _SEED_SUPPLIER_CNPJS:
        if cnpj not in seen:
            seen.add(cnpj)
            result.append(cnpj)
    # Then buyer CNPJs (orgaos)
    for cnpj in buyer_cnpjs:
        if cnpj not in seen:
            seen.add(cnpj)
            result.append(cnpj)
    return result[:_MAX_CNPJS]


def _fetch_top_cnpjs() -> dict:
    """Query mv_sitemap_cnpjs for distinct orgao_cnpj com ≥1 licitação ativa.

    SEO-SITEMAP-MV-001: MV pré-agregada substitui RPC + fallback paginado.
    Query < 50ms contra < 1ms no MV indexado.

    Sync — supabase-py is sync, so caller wraps this in asyncio.to_thread.
    """
    try:
        from supabase_client import get_supabase

        sb = get_supabase()

        rows: list[str] = []
        page_size = 1000
        offset = 0
        while True:
            resp = (
                sb.table("mv_sitemap_cnpjs")
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

        cnpj_list = _merge_with_seed(rows)
        logger.info(
            "sitemap_cnpjs (MV): %d CNPJs from mv_sitemap_cnpjs (pages=%d)",
            len(cnpj_list),
            (offset // page_size) if page_size else 0,
        )

        return {
            "cnpjs": cnpj_list,
            "total": len(cnpj_list),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("sitemap_cnpjs MV query failed: %s", e)
        return {
            "cnpjs": [],
            "total": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Sprint 3 Parte 13: sitemap de fornecedores por CNPJ (/fornecedores/{cnpj})
# ---------------------------------------------------------------------------

@router.get(
    "/sitemap/fornecedores-cnpj",
    response_model=SitemapFornecedoresCnpjResponse,
    summary="Top CNPJs de fornecedores com contratos no datalake (para sitemap)",
)
async def sitemap_fornecedores_cnpj(response: Response):
    """Retorna os CNPJs de fornecedores com mais contratos em pncp_supplier_contracts.

    SEO-SITEMAP-MV-001: agora usa mv_sitemap_fornecedores (MV pré-agregada).
    Usado pelo frontend para gerar /fornecedores/{cnpj} no sitemap.xml.
    Limite: 5.000 CNPJs por volume de contratos.
    Cache: 24h em memoria sucesso, 5min em falha (negative cache PR #529 pattern).
    """
    response.headers.update(SITEMAP_CACHE_HEADERS)
    cached = _get_fornecedores_cached("fornecedores_cnpj")
    if cached:
        record_sitemap_count("fornecedores-cnpj", len(cached.get("cnpjs", [])))
        return SitemapFornecedoresCnpjResponse(**cached)

    _fresh_fetch = True
    try:
        data = await _run_with_budget(
            _fetch_top_fornecedores_cnpjs(),
            budget=_BUDGET_S,
            phase="route",
            source="sitemap_cnpjs.sitemap_fornecedores_cnpj",
        )
        _set_fornecedores_cached("fornecedores_cnpj", data, ttl=_CACHE_TTL_SECONDS)
    except asyncio.TimeoutError:
        logger.error(
            "sitemap_fornecedores_cnpj: budget %.0fs exceeded — returning 503 (not caching)",
            _BUDGET_S,
        )
        sentry_sdk.capture_message('sitemap_source_timeout', level='warning',
            tags={'endpoint': 'fornecedores-cnpj', 'outcome': 'timeout'})
        return JSONResponse(
            status_code=503,
            content={"detail": "sitemap_source_timeout"},
            headers={"Retry-After": "30"},
        )
    except Exception as exc:
        logger.error("sitemap_fornecedores_cnpj unexpected error: %s", exc)
        data = _empty_cnpjs_response()
        _set_fornecedores_cached("fornecedores_cnpj", data, ttl=_NEGATIVE_CACHE_TTL_SECONDS)

    fornecedores_list = data.get("cnpjs", [])
    # Alert: empty despite data exists in source table (only on fresh fetches)
    if _fresh_fetch and len(fornecedores_list) == 0:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("pncp_supplier_contracts").select("id", count="exact").limit(0)
            )
            source_count = resp.count if hasattr(resp, 'count') and resp.count is not None else 0
            if source_count and source_count > 0:
                sentry_sdk.capture_message('sitemap_empty_despite_data', level='error',
                    tags={'endpoint': 'fornecedores-cnpj', 'source_count': source_count})
        except Exception:
            pass
    # Alert: stale data - check max data_assinatura in source table (only on fresh fetches)
    if _fresh_fetch:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            resp = await sb_execute(
                sb.table("pncp_supplier_contracts")
                .select("data_assinatura")
                .order("data_assinatura", desc=True)
                .limit(1)
            )
            if resp.data and len(resp.data) > 0:
                raw = resp.data[0].get("data_assinatura")
                if raw:
                    last_dt = datetime.fromisoformat(str(raw)[:10]).replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if age_seconds > 93600:
                        sentry_sdk.capture_message('sitemap_source_stale', level='warning',
                            tags={'endpoint': 'fornecedores-cnpj', 'age_hours': round(age_seconds / 3600, 1)})
        except Exception:
            pass

    record_sitemap_count("fornecedores-cnpj", len(fornecedores_list))
    return SitemapFornecedoresCnpjResponse(**data)


async def _fetch_top_fornecedores_cnpjs() -> dict:
    """Busca os CNPJs de fornecedores mais ativos em mv_sitemap_fornecedores.

    SEO-SITEMAP-MV-001: MV pré-agregada substitui paginated scan de
    pncp_supplier_contracts. Query < 50ms.

    Async com sb_execute() para retry HTTP/2 (SEN-BE-004).
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()

        rows: list[str] = []
        page_size = 1000
        offset = 0
        while True:
            resp = await sb_execute(
                sb.table("mv_sitemap_fornecedores")
                .select("cnpj")
                .order("cnpj")
                .range(offset, offset + page_size - 1)
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

        cnpj_list = rows[:_MAX_FORNECEDORES_CNPJS]

        logger.info(
            "sitemap_fornecedores_cnpj (MV): %d CNPJs de mv_sitemap_fornecedores",
            len(cnpj_list),
        )

        return {
            "cnpjs": cnpj_list,
            "total": len(cnpj_list),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("sitemap_fornecedores_cnpj MV query failed: %s", e)
        return {
            "cnpjs": [],
            "total": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
