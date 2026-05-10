"""Issue #1007: pSEO data blocks — Top 5 fornecedores + 5 últimos editais.

Public (no auth required) endpoints that serve DataLake-sourced social proof
blocks for programmatic SEO pages.

Endpoints:
  GET /pseo/top-suppliers   — Top suppliers by contract volume (sector × UF)
  GET /pseo/recent-editais  — Most recent open editais (sector × UF)

Cache: InMemory 6h TTL on success, 5min negative TTL on error/timeout.
Budget: 5s per query (< Supabase service_role statement_timeout=15s).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.budget import _run_with_budget
from sectors import SECTORS
from utils.postgrest_paginate import paginate_full

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pseo-data"])

# ---------------------------------------------------------------------------
# Cache (InMemory, same pattern as contratos_publicos.py)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 6 * 60 * 60        # 6h success
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60    # 5min on error
_SECTOR_QUERY_BUDGET_S = 5.0             # budget < statement_timeout=15s

# dict: key -> (data_dict, stored_at, ttl)
_suppliers_cache: dict[str, tuple[dict, float, float]] = {}
_editais_cache: dict[str, tuple[dict, float, float]] = {}


def _get_cached(cache: dict, key: str) -> Optional[dict]:
    entry = cache.get(key)
    if entry is None:
        return None
    data, ts, ttl = entry
    if time.time() - ts >= ttl:
        del cache[key]
        return None
    return data


def _set_cached(cache: dict, key: str, data: dict, ttl: float = _CACHE_TTL_SECONDS) -> None:
    cache[key] = (data, time.time(), ttl)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TopSupplierItem(BaseModel):
    razao_social: str
    cnpj: str                     # kept in response for link generation (LGPD: not rendered as text)
    contratos_count: int
    valor_total: float


class TopSuppliersResponse(BaseModel):
    setor: str
    uf: Optional[str] = None
    municipio: Optional[str] = None
    items: list[TopSupplierItem]
    total_contracts_in_scope: int  # used for threshold check
    last_updated: str


class RecentEditalItem(BaseModel):
    orgao: str
    objeto: str
    valor_estimado: Optional[float] = None
    data_limite: Optional[str] = None
    data_publicacao: Optional[str] = None
    link_interno: str             # /licitacoes/{setor}?query={orgao}


class RecentEditaisResponse(BaseModel):
    setor: str
    uf: Optional[str] = None
    municipio: Optional[str] = None
    items: list[RecentEditalItem]
    total: int
    last_updated: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]

_MIN_CONTRACTS_FOR_SOCIAL_PROOF = 10


def _resolve_sector(setor: str) -> Optional[str]:
    """Resolve slug or ID to a valid sector_id. Returns None if not found."""
    sector_id = setor.replace("-", "_")
    if sector_id in SECTORS:
        return sector_id
    return None


async def _fetch_supplier_contracts(sector_id: str, uf_upper: Optional[str]) -> tuple[list[dict], bool]:
    """Fetch pncp_supplier_contracts filtered by sector keywords and optional UF.

    Returns (matched_rows, timed_out).
    Mirrors _fetch_sector_contracts in contratos_publicos.py.
    """
    sector = SECTORS[sector_id]
    keywords_lower = {kw.lower() for kw in sector.keywords}

    def _sync_query() -> list[dict]:
        from supabase_client import get_supabase
        sb = get_supabase()
        builder = (
            sb.table("pncp_supplier_contracts")
            .select("ni_fornecedor,nome_fornecedor,orgao_cnpj,orgao_nome,valor_global,objeto_contrato")
            .eq("is_active", True)
            .order("data_assinatura", desc=True)
        )
        if uf_upper:
            builder = builder.eq("uf", uf_upper)
        return paginate_full(
            builder,
            batch_size=1000,
            max_total=5000,
            route="pseo_data.supplier_contracts",
            entity_type="pncp_supplier_contracts",
        )

    try:
        rows = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=_SECTOR_QUERY_BUDGET_S,
            phase="route",
            source="pseo_data.supplier_contracts",
        )
    except asyncio.TimeoutError:
        logger.warning("pseo_data supplier query exceeded %.1fs budget (%s/%s)", _SECTOR_QUERY_BUDGET_S, sector_id, uf_upper)
        return [], True
    except Exception as exc:
        logger.error("pseo_data supplier DB query failed (%s/%s): %s", sector_id, uf_upper, exc)
        return [], True

    matched = [
        row for row in rows
        if any(kw in (row.get("objeto_contrato") or "").lower() for kw in keywords_lower)
    ]
    return matched, False


async def _fetch_recent_bids(sector_id: str, uf_upper: Optional[str], limit: int = 5) -> tuple[list[dict], bool]:
    """Fetch most recent bids from pncp_raw_bids filtered by sector keywords.

    Returns (items, timed_out).
    Fetches a wider page, then filters Python-side on sector keywords (same
    pattern as _fetch_sector_contracts but targeting pncp_raw_bids).
    """
    sector = SECTORS[sector_id]
    keywords_lower = {kw.lower() for kw in sector.keywords}

    def _sync_query() -> list[dict]:
        from supabase_client import get_supabase
        sb = get_supabase()
        builder = (
            sb.table("pncp_raw_bids")
            .select(
                "pncp_id,uf,municipio,orgao_razao_social,objeto_compra,"
                "valor_total_estimado,data_publicacao,data_encerramento,link_pncp"
            )
            .order("data_publicacao", desc=True)
        )
        if uf_upper:
            builder = builder.eq("uf", uf_upper)
        # Pull a wider window for Python-side sector filtering
        return paginate_full(
            builder,
            batch_size=500,
            max_total=500,
            route="pseo_data.recent_bids",
            entity_type="pncp_raw_bids",
        )

    try:
        rows = await _run_with_budget(
            asyncio.to_thread(_sync_query),
            budget=_SECTOR_QUERY_BUDGET_S,
            phase="route",
            source="pseo_data.recent_bids",
        )
    except asyncio.TimeoutError:
        logger.warning("pseo_data recent_bids query exceeded %.1fs budget (%s/%s)", _SECTOR_QUERY_BUDGET_S, sector_id, uf_upper)
        return [], True
    except Exception as exc:
        logger.error("pseo_data recent_bids DB query failed (%s/%s): %s", sector_id, uf_upper, exc)
        return [], True

    matched = [
        row for row in rows
        if any(kw in (row.get("objeto_compra") or "").lower() for kw in keywords_lower)
    ]
    return matched[:limit], False


# ---------------------------------------------------------------------------
# Endpoint: Top Suppliers
# ---------------------------------------------------------------------------

@router.get(
    "/pseo/top-suppliers",
    response_model=TopSuppliersResponse,
    summary="Top 5 fornecedores por volume de contratos no setor (público)",
)
async def get_top_suppliers(
    setor: str,
    uf: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = 5,
):
    """Top suppliers by contract volume in sector, last 12 months.

    Returns cnpj, razao_social, contratos_count, valor_total.
    If total contracts < 10, returns empty list (avoid weak social proof).
    Cache: 6h InMemory.
    """
    sector_id = _resolve_sector(setor)
    if sector_id is None:
        raise HTTPException(status_code=404, detail=f"Setor '{setor}' não encontrado")

    uf_upper = uf.upper() if uf else None
    if uf_upper and uf_upper not in ALL_UFS:
        raise HTTPException(status_code=400, detail=f"UF '{uf}' inválida")

    cache_key = f"top_suppliers:{sector_id}:{uf_upper or ''}:{municipio or ''}:{limit}"
    cached = _get_cached(_suppliers_cache, cache_key)
    if cached:
        return TopSuppliersResponse(**cached)

    rows, timed_out = await _fetch_supplier_contracts(sector_id, uf_upper)

    now = datetime.now(timezone.utc)

    if timed_out:
        data = {
            "setor": sector_id,
            "uf": uf_upper,
            "municipio": municipio,
            "items": [],
            "total_contracts_in_scope": 0,
            "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        _set_cached(_suppliers_cache, cache_key, data, ttl=_NEGATIVE_CACHE_TTL_SECONDS)
        return TopSuppliersResponse(**data)

    # Threshold check: avoid weak social proof
    total_contracts = len(rows)
    if total_contracts < _MIN_CONTRACTS_FOR_SOCIAL_PROOF:
        data = {
            "setor": sector_id,
            "uf": uf_upper,
            "municipio": municipio,
            "items": [],
            "total_contracts_in_scope": total_contracts,
            "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        _set_cached(_suppliers_cache, cache_key, data)
        return TopSuppliersResponse(**data)

    # Aggregate by supplier CNPJ
    agg: dict[str, dict] = defaultdict(lambda: {"razao_social": "", "cnpj": "", "contratos_count": 0, "valor_total": 0.0})
    for row in rows:
        cnpj = (row.get("ni_fornecedor") or "").strip()
        if not cnpj:
            continue
        agg[cnpj]["cnpj"] = cnpj
        agg[cnpj]["razao_social"] = row.get("nome_fornecedor") or cnpj
        agg[cnpj]["contratos_count"] += 1
        try:
            agg[cnpj]["valor_total"] += float(row.get("valor_global") or 0)
        except (TypeError, ValueError):
            pass

    top = sorted(agg.values(), key=lambda x: x["contratos_count"], reverse=True)[:limit]

    items = [TopSupplierItem(**entry) for entry in top]
    data = {
        "setor": sector_id,
        "uf": uf_upper,
        "municipio": municipio,
        "items": [item.model_dump() for item in items],
        "total_contracts_in_scope": total_contracts,
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _set_cached(_suppliers_cache, cache_key, data)
    return TopSuppliersResponse(**data)


# ---------------------------------------------------------------------------
# Endpoint: Recent Editais
# ---------------------------------------------------------------------------

@router.get(
    "/pseo/recent-editais",
    response_model=RecentEditaisResponse,
    summary="5 últimos editais abertos no setor (público)",
)
async def get_recent_editais(
    setor: str,
    uf: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = 5,
):
    """Most recent open editais for sector+UF.

    Returns orgao, objeto, valor_estimado, data_limite, link_interno.
    link_interno = /licitacoes/{setor}?query={orgao}
    Cache: 6h InMemory.
    """
    sector_id = _resolve_sector(setor)
    if sector_id is None:
        raise HTTPException(status_code=404, detail=f"Setor '{setor}' não encontrado")

    uf_upper = uf.upper() if uf else None
    if uf_upper and uf_upper not in ALL_UFS:
        raise HTTPException(status_code=400, detail=f"UF '{uf}' inválida")

    cache_key = f"recent_editais:{sector_id}:{uf_upper or ''}:{municipio or ''}:{limit}"
    cached = _get_cached(_editais_cache, cache_key)
    if cached:
        return RecentEditaisResponse(**cached)

    setor_slug = sector_id.replace("_", "-")
    rows, timed_out = await _fetch_recent_bids(sector_id, uf_upper, limit=limit)

    now = datetime.now(timezone.utc)

    if timed_out:
        data = {
            "setor": sector_id,
            "uf": uf_upper,
            "municipio": municipio,
            "items": [],
            "total": 0,
            "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        _set_cached(_editais_cache, cache_key, data, ttl=_NEGATIVE_CACHE_TTL_SECONDS)
        return RecentEditaisResponse(**data)

    items = []
    for row in rows:
        orgao = row.get("orgao_razao_social") or ""
        objeto_raw = row.get("objeto_compra") or ""
        objeto = objeto_raw[:80] + ("…" if len(objeto_raw) > 80 else "")
        valor = row.get("valor_total_estimado")
        try:
            valor_float = float(valor) if valor is not None else None
        except (TypeError, ValueError):
            valor_float = None

        link_interno = f"/licitacoes/{setor_slug}?query={orgao}"
        items.append(RecentEditalItem(
            orgao=orgao,
            objeto=objeto,
            valor_estimado=valor_float,
            data_limite=row.get("data_encerramento"),
            data_publicacao=row.get("data_publicacao"),
            link_interno=link_interno,
        ))

    data = {
        "setor": sector_id,
        "uf": uf_upper,
        "municipio": municipio,
        "items": [item.model_dump() for item in items],
        "total": len(items),
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _set_cached(_editais_cache, cache_key, data)
    return RecentEditaisResponse(**data)
