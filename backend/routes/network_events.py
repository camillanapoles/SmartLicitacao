"""NETINT-001: Network Events Aggregation endpoints.

Routes for recording and querying anonymized network intelligence events
(LGPD-first design). All data is strictly aggregated — never individual.

Endpoints:
  POST /v1/network-events/record  — Record an anonymized event (opt-in gated)
  GET  /v1/network-events/top     — Top dimensions by event type
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require_auth
from database import get_db
from supabase_client import sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/network-events", tags=["network-events"])


# ============================================================================
# Pydantic schemas (response_model)
# ============================================================================

class RecordEventRequest(BaseModel):
    evento_tipo: str = Field(
        ..., description="Tipo do evento: search_query, sector_view, org_view, cnpj_lookup"
    )
    dimensao_tipo: str = Field(
        ..., description="Tipo da dimensao: setor, uf, modalidade, orgao"
    )
    dimensao_valor: str = Field(
        ..., description="Valor da dimensao (ex: saude, SP, pregao)"
    )
    metadados: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadados adicionais (setores, ufs, modalidades). NUNCA PII.",
    )


class RecordEventResponse(BaseModel):
    success: bool = True
    message: str = "Evento registrado com sucesso"


class TopItem(BaseModel):
    dimensao_valor: str
    contagem: int


class TopResponse(BaseModel):
    evento_tipo: str
    periodo_inicio: str
    periodo_fim: str
    items: list[TopItem]


# ============================================================================
# POST /network-events/record — Record an event (opt-in gated)
# ============================================================================

ALLOWED_EVENTO_TIPOS = frozenset({
    "search_query", "sector_view", "org_view", "cnpj_lookup",
    "discount_view", "migration_view", "competitor_view",
})

ALLOWED_DIMENSAO_TIPOS = frozenset({
    "setor", "uf", "modalidade", "orgao", "municipio",
})


@router.post("/record", response_model=RecordEventResponse)
async def record_network_event(
    body: RecordEventRequest,
    user: dict = Depends(require_auth),
    db=Depends(get_db),
):
    """Record an anonymized network event.

    Only collects data if user has explicitly opted in
    (profiles.allow_network_analytics = true). LGPD Art. 6, I.
    """
    user_id = user["id"]

    # ── Opt-in check ───────────────────────────────────────────────────────
    try:
        profile_result = await sb_execute(
            db.table("profiles")
            .select("allow_network_analytics")
            .eq("id", user_id)
            .limit(1)
            .single()
        )
    except Exception as e:
        logger.warning("Failed to check opt-in for user %s: %s", user_id[:8], e)
        return RecordEventResponse(
            success=False,
            message="Nao foi possivel verificar consentimento. Tente novamente.",
        )

    allow = profile_result.data.get("allow_network_analytics") if profile_result.data else None
    if allow is not True:
        # NULL or false: opt-out — nao coleta
        logger.debug(
            "User %s opted out (allow_network_analytics=%s) — event skipped",
            user_id[:8], allow,
        )
        # Return success silently (do not reveal opt-out status to caller)
        return RecordEventResponse(
            success=True,
            message="Evento registrado com sucesso",
        )

    # ── Input validation ───────────────────────────────────────────────────
    if body.evento_tipo not in ALLOWED_EVENTO_TIPOS:
        raise HTTPException(
            status_code=422,
            detail=f"evento_tipo invalido: {body.evento_tipo}. "
                   f"Permitidos: {sorted(ALLOWED_EVENTO_TIPOS)}",
        )

    if body.dimensao_tipo not in ALLOWED_DIMENSAO_TIPOS:
        raise HTTPException(
            status_code=422,
            detail=f"dimensao_tipo invalido: {body.dimensao_tipo}. "
                   f"Permitidos: {sorted(ALLOWED_DIMENSAO_TIPOS)}",
        )

    # ── Call RPC ───────────────────────────────────────────────────────────
    try:
        await sb_execute(db.rpc("network_record_event", {
            "p_evento_tipo": body.evento_tipo,
            "p_dimensao_tipo": body.dimensao_tipo,
            "p_dimensao_valor": body.dimensao_valor,
            "p_metadados": body.metadados,
        }))
    except Exception as e:
        error_msg = str(e)
        if "rejeitado por seguranca LGPD" in error_msg:
            raise HTTPException(
                status_code=422,
                detail=f"Metadados rejeitados pela sanitizacao LGPD: {error_msg}",
            )
        logger.warning("Failed to record network event: %s", error_msg)
        return RecordEventResponse(
            success=False,
            message="Erro ao registrar evento.",
        )

    logger.debug("Network event recorded: %s/%s/%s",
                 body.evento_tipo, body.dimensao_tipo, body.dimensao_valor)
    return RecordEventResponse()


# ============================================================================
# GET /network-events/top — Top dimensions by event type
# ============================================================================

@router.get("/top", response_model=TopResponse)
async def get_top_network_events(
    evento_tipo: str = Query(..., description="Tipo de evento para filtrar"),
    dimensao_tipo: str = Query("setor", description="Dimensao para agregar"),
    dias: int = Query(30, ge=1, le=365, description="Janela em dias"),
    limite: int = Query(20, ge=1, le=100, description="Maximo de resultados"),
    db=Depends(get_db),
):
    """Get top dimension values for a given event type.

    Public endpoint — returns only anonymized aggregated data.
    """
    # ── Input validation ───────────────────────────────────────────────────
    if evento_tipo not in ALLOWED_EVENTO_TIPOS:
        raise HTTPException(
            status_code=422,
            detail=f"evento_tipo invalido: {evento_tipo}. "
                   f"Permitidos: {sorted(ALLOWED_EVENTO_TIPOS)}",
        )
    if dimensao_tipo not in ALLOWED_DIMENSAO_TIPOS:
        raise HTTPException(
            status_code=422,
            detail=f"dimensao_tipo invalido: {dimensao_tipo}. "
                   f"Permitidos: {sorted(ALLOWED_DIMENSAO_TIPOS)}",
        )

    data_inicio = date.today() - timedelta(days=dias)
    data_fim = date.today()

    try:
        result = await sb_execute(
            db.table("network_events_agg")
            .select("dimensao_valor, contagem")
            .eq("evento_tipo", evento_tipo)
            .eq("dimensao_tipo", dimensao_tipo)
            .gte("periodo", data_inicio.isoformat())
            .lte("periodo", data_fim.isoformat())
            .order("contagem", desc=True)
            .limit(limite)
        )
    except Exception as e:
        logger.warning("Failed to query network events: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar eventos.")

    items = result.data if result.data else []
    return TopResponse(
        evento_tipo=evento_tipo,
        periodo_inicio=data_inicio.isoformat(),
        periodo_fim=data_fim.isoformat(),
        items=[TopItem(dimensao_valor=row["dimensao_valor"], contagem=row["contagem"])
               for row in items],
    )
