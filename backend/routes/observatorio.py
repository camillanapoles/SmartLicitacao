"""STORY-431: Observatory public endpoint — monthly procurement stats.

Returns aggregated stats from the PNCP datalake for a specific month/year,
enabling the /observatorio monthly reports (data journalism / linkbait).

Public (no auth). Cache: InMemory 24h TTL on success per (mes, ano), 5min
negative TTL on timeout/error (AC10). Empty current month → 404 + noindex
header (anti-Soft 404). Empty historical month → 200 + is_empty_period:true
+ X-Robots-Tag: noindex (AC11).
"""

import asyncio
import calendar
import csv
import io
import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

import sentry_sdk
from fastapi import APIRouter, HTTPException, Path, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from metrics import OBSERVATORIO_BUDGET_EXCEEDED
from pipeline.budget import _run_with_budget

logger = logging.getLogger(__name__)
router = APIRouter(tags=["observatorio"])

# STORY-431 AC10 + RES-BE-015: hard budget per Supabase round-trip
# (current+prev month). Tightened from 15.0s to 8.0s — the previous value
# tied the budget at the Supabase service_role ``statement_timeout`` floor
# (15s) which means the cancelled future cleanup ran on the event loop just
# as the SQL was firing server-side. New floor is < statement_timeout so the
# DB closes its side of the connection before Python tries to clean up
# (memory feedback_pool_leak_caller_timeout_vs_sql_timeout).
_QUERY_BUDGET_S = 8.0
_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h on success
# STORY-431 AC10: negative cache TTL on timeout/error — same pattern as PR #535 (sitemap)
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60

# STORY-431 AC11: empty-period behavior toggle for testing
# 'auto' (default) | '404' (force HTTPException) | 'noindex' (force 200 + noindex) | 'render' (no special handling)
_EMPTY_PERIOD_BEHAVIOR = os.getenv("OBSERVATORIO_EMPTY_PERIOD_BEHAVIOR", "auto").lower()

# 3-tuple cache entry: (data, stored_at, ttl) — supports per-entry TTL
_obs_cache: dict[str, tuple[dict, float, float]] = {}

MONTH_NAMES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

MODALIDADE_NAMES: dict[int, str] = {
    4: "Concorrência Eletrônica",
    5: "Concorrência Presencial",
    6: "Pregão Eletrônico",
    7: "Pregão Presencial",
    8: "Dispensa de Licitação",
    12: "Credenciamento",
}

UF_NAMES: dict[str, str] = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
    "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class UfCount(BaseModel):
    uf: str
    uf_name: str
    total: int
    pct: float


class ModalidadeCount(BaseModel):
    modalidade_id: int
    modalidade_name: str
    total: int
    pct: float


class SetorHighlight(BaseModel):
    setor_id: str
    setor_name: str
    total_atual: int
    total_anterior: int
    variacao_pct: float


class MonthlyTrend(BaseModel):
    semana: str
    total: int


class RelatorioMensal(BaseModel):
    mes: int
    ano: int
    mes_nome: str
    periodo: str
    total_editais: int
    valor_total: float
    valor_medio: float
    top_ufs: list[UfCount]
    modalidades: list[ModalidadeCount]
    tendencia_semanal: list[MonthlyTrend]
    setores_em_alta: list[SetorHighlight]
    gerado_em: str
    fonte: str
    license: str
    # STORY-431 AC11: marker for historical empty months (no data ingested in window).
    # Frontend uses this to render EmptyStatePeriod CTA instead of "R$ 0,00" cards.
    is_empty_period: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _is_period_historical(mes: int, ano: int) -> bool:
    """STORY-431 AC11: treat months >30d in the past as historical.

    Used by route handler to choose between 404 (current empty) and
    200+is_empty_period (historical empty).
    """
    try:
        return (date.today() - date(ano, mes, 1)).days > 30
    except ValueError:
        return False


def _apply_empty_period_response(
    data: dict,
    mes: int,
    ano: int,
    response: Optional[Response],
) -> Optional[RelatorioMensal]:
    """STORY-431 AC11: route the empty-period response per behavior toggle.

    Returns the RelatorioMensal to serve (with appropriate headers set) OR
    raises HTTPException(404) for a current empty month.

    Returns None if the period is non-empty (caller proceeds normally).
    """
    if data.get("total_editais", 0) > 0:
        return None

    behavior = _EMPTY_PERIOD_BEHAVIOR
    is_historical = _is_period_historical(mes, ano)

    sentry_sdk.set_tag("observatorio_outcome", "empty_period")

    if behavior == "render":
        # Force-render the empty payload as if it were a normal response (test override).
        return RelatorioMensal(**data)

    if behavior == "404" or (behavior == "auto" and not is_historical):
        # Current month with no data yet — anti-Soft 404 per AC11.
        raise HTTPException(
            status_code=404,
            detail="Relatório não disponível para este período",
            headers={"X-Robots-Tag": "noindex, nofollow"},
        )

    # behavior in {"noindex", "auto"+historical} → 200 + is_empty_period + noindex
    # Mark the payload as an empty period so the frontend renders the
    # EmptyStatePeriod CTA rather than the misleading "R$ 0,00" cards.
    if response is not None:
        response.headers["X-Robots-Tag"] = "noindex"
    payload = {**data, "is_empty_period": True}
    return RelatorioMensal(**payload)


@router.get(
    "/observatorio/relatorio/{mes}/{ano}",
    response_model=RelatorioMensal,
    summary="Relatório mensal do Observatório de Licitações (público)",
)
async def get_relatorio_mensal(
    mes: int = Path(..., ge=1, le=12, description="Mês (1-12)"),
    ano: int = Path(..., ge=2024, le=2030, description="Ano"),
    response: Response = None,
):
    # STORY-431 AC5: CORS wildcard para permitir embed em domínios externos
    if response is not None:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"

    # STORY-431 AC14: default outcome tag — overridden in error/empty paths.
    sentry_sdk.set_tag("observatorio_outcome", "success")

    cache_key = f"{mes}:{ano}"
    cached = _get_cached(cache_key)
    if cached is not None:
        empty_resp = _apply_empty_period_response(cached, mes, ano, response)
        if empty_resp is not None:
            return empty_resp
        return RelatorioMensal(**cached)

    data = await _generate_relatorio(mes, ano)

    # STORY-431 AC10: shorter TTL when payload is empty (negative cache 5min)
    # so the next request retries quickly once data ingestion catches up.
    cache_ttl = (
        _NEGATIVE_CACHE_TTL_SECONDS if data.get("total_editais", 0) == 0
        else _CACHE_TTL_SECONDS
    )
    _set_cached(cache_key, data, ttl=cache_ttl)

    # STORY-431 AC11: empty period → 404 (current) or 200+noindex (historical)
    empty_resp = _apply_empty_period_response(data, mes, ano, response)
    if empty_resp is not None:
        return empty_resp

    return RelatorioMensal(**data)


@router.get(
    "/observatorio/relatorio/{mes}/{ano}/csv",
    summary="Download CSV do relatório mensal (público)",
)
async def get_relatorio_csv(
    mes: int = Path(..., ge=1, le=12),
    ano: int = Path(..., ge=2024, le=2030),
    response: Response = None,
):
    cache_key = f"{mes}:{ano}"
    cached = _get_cached(cache_key)
    if not cached:
        cached = await _generate_relatorio(mes, ano)
        _set_cached(cache_key, cached)

    relatorio = RelatorioMensal(**cached)
    csv_content = _build_csv(relatorio)
    filename = f"smartlic-raio-x-{MONTH_NAMES_PT[mes].replace('ç', 'c').replace('ã', 'a')}-{ano}.csv"

    # STORY-431 AC5: CORS wildcard para embed/download em domínios externos
    cors_headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
    }
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8-sig")),
        media_type="text/csv; charset=utf-8",
        headers=cors_headers,
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cached(key: str) -> Optional[dict]:
    entry = _obs_cache.get(key)
    if entry is None:
        return None
    data, ts, ttl = entry
    if time.time() - ts >= ttl:
        del _obs_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict, ttl: float = _CACHE_TTL_SECONDS) -> None:
    _obs_cache[key] = (data, time.time(), ttl)


def _empty_relatorio_payload(mes: int, ano: int) -> dict:
    """STORY-431 AC10/AC11: zero-filled payload returned on timeout/error or
    historical empty period. Marked with is_empty_period=True so the frontend
    can render the EmptyStatePeriod CTA instead of misleading "R$ 0,00" cards.
    """
    mes_nome = MONTH_NAMES_PT.get(mes, str(mes))
    try:
        _, last_day = calendar.monthrange(ano, mes)
    except calendar.IllegalMonthError:
        last_day = 30
    return {
        "mes": mes,
        "ano": ano,
        "mes_nome": mes_nome,
        "periodo": f"Editais publicados de 1 a {last_day} de {mes_nome} de {ano}",
        "total_editais": 0,
        "valor_total": 0.0,
        "valor_medio": 0.0,
        "top_ufs": [],
        "modalidades": [],
        "tendencia_semanal": [],
        "setores_em_alta": [],
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "SmartLic Observatório — dados PNCP (Portal Nacional de Contratações Públicas)",
        "license": "Creative Commons BY 4.0 — https://creativecommons.org/licenses/by/4.0/",
        "is_empty_period": True,
    }


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def _query_historical_sync(data_inicial: str, data_final: str) -> list[dict]:
    """Direct Supabase query bypassing is_active filter — for historical months.

    Used when the requested month is >30 days ago and data may be soft-deleted
    (is_active=False) by the purge job. Queries pncp_raw_bids without the RPC
    search_datalake which filters is_active=true.
    """
    from supabase_client import get_supabase
    sb = get_supabase()
    resp = (
        sb.table("pncp_raw_bids")
        .select("pncp_id, objeto_compra, valor_total_estimado, modalidade_id, uf, data_publicacao")
        .gte("data_publicacao", data_inicial)
        .lte("data_publicacao", data_final + "T23:59:59")
        .limit(5000)
        .execute()
    )
    rows = resp.data or []
    # Normalize to keys expected by _generate_relatorio processing
    normalized: list[dict] = []
    for r in rows:
        dp = r.get("data_publicacao") or ""
        normalized.append({
            "uf": (r.get("uf") or "").upper(),
            "modalidade_id": r.get("modalidade_id") or 0,
            "valor_estimado": float(r.get("valor_total_estimado") or 0),
            "data_publicacao": str(dp)[:10] if dp else "",
            "titulo": r.get("objeto_compra") or "",
        })
    return normalized


async def _generate_relatorio(mes: int, ano: int) -> dict:
    from datalake_query import query_datalake
    from unified_schemas.unified import VALID_UFS

    # Date range for the requested month
    _, last_day = calendar.monthrange(ano, mes)
    data_inicial = f"{ano:04d}-{mes:02d}-01"
    data_final = f"{ano:04d}-{mes:02d}-{last_day:02d}"

    # Date range for previous month (for growth comparison)
    prev_mes = mes - 1 if mes > 1 else 12
    prev_ano = ano if mes > 1 else ano - 1
    _, prev_last = calendar.monthrange(prev_ano, prev_mes)
    prev_inicial = f"{prev_ano:04d}-{prev_mes:02d}-01"
    prev_final = f"{prev_ano:04d}-{prev_mes:02d}-{prev_last:02d}"

    # Detect if month is historical (>30 days ago — data may be soft-deleted)
    today = date.today()
    is_historical = (today - date(ano, mes, 1)).days > 30

    # Query current month
    results: list[dict] = []
    prev_results: list[dict] = []

    # STORY-431 AC10 + RES-BE-015: hard budget per Supabase round-trip with
    # negative cache. ``_run_with_budget(asyncio.to_thread(...))`` increments
    # ``smartlic_pipeline_budget_exceeded_total{phase=route,source=observatorio.*}``
    # AND avoids the wait_for+to_thread pool leak (caller cancel does not stop
    # the Python thread; the cancelled future cleanup ran inline on the event
    # loop and was the Stage 2-8 freeze).
    if is_historical:
        try:
            results = await _run_with_budget(
                asyncio.to_thread(_query_historical_sync, data_inicial, data_final),
                budget=_QUERY_BUDGET_S,
                phase="route",
                source="observatorio.relatorio_historical",
            )
            logger.info(
                "observatorio: historical query for %d/%d returned %d rows",
                mes, ano, len(results),
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[observatorio] budget %.0fs exceeded for %d/%d",
                _QUERY_BUDGET_S, mes, ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="historical").inc()
            sentry_sdk.set_tag("observatorio_outcome", "timeout")
            return _empty_relatorio_payload(mes, ano)
        except Exception as exc:
            logger.error(
                "[observatorio] unexpected error %r for %d/%d", exc, mes, ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="historical").inc()
            sentry_sdk.set_tag("observatorio_outcome", "error")
            return _empty_relatorio_payload(mes, ano)
    else:
        try:
            results = await asyncio.wait_for(
                query_datalake(
                    ufs=list(VALID_UFS),
                    data_inicial=data_inicial,
                    data_final=data_final,
                    limit=5000,
                ),
                timeout=_QUERY_BUDGET_S,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[observatorio] budget %.0fs exceeded (live datalake) for %d/%d",
                _QUERY_BUDGET_S, mes, ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="current").inc()
            sentry_sdk.set_tag("observatorio_outcome", "timeout")
            return _empty_relatorio_payload(mes, ano)
        except Exception as exc:
            logger.error(
                "[observatorio] live datalake error %r for %d/%d", exc, mes, ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="current").inc()
            sentry_sdk.set_tag("observatorio_outcome", "error")
            return _empty_relatorio_payload(mes, ano)

    # Previous month: best-effort under the same budget. A failure here only
    # degrades the "setores em alta" comparison — not a fatal error.
    prev_is_historical = (today - date(prev_ano, prev_mes, 1)).days > 30
    if prev_is_historical:
        try:
            prev_results = await _run_with_budget(
                asyncio.to_thread(_query_historical_sync, prev_inicial, prev_final),
                budget=_QUERY_BUDGET_S,
                phase="route",
                source="observatorio.relatorio_prev_month_historical",
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[observatorio] budget %.0fs exceeded (prev_month historical) for %d/%d",
                _QUERY_BUDGET_S, prev_mes, prev_ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="prev_month").inc()
            prev_results = []
        except Exception as exc:
            logger.warning(
                "[observatorio] prev_month historical error %r for %d/%d",
                exc, prev_mes, prev_ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="prev_month").inc()
            prev_results = []
    else:
        try:
            prev_results = await asyncio.wait_for(
                query_datalake(
                    ufs=list(VALID_UFS),
                    data_inicial=prev_inicial,
                    data_final=prev_final,
                    limit=5000,
                ),
                timeout=_QUERY_BUDGET_S,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[observatorio] budget %.0fs exceeded (prev_month live) for %d/%d",
                _QUERY_BUDGET_S, prev_mes, prev_ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="prev_month").inc()
            prev_results = []
        except Exception as exc:
            logger.warning(
                "[observatorio] prev_month live error %r for %d/%d",
                exc, prev_mes, prev_ano,
            )
            OBSERVATORIO_BUDGET_EXCEEDED.labels(period_age="prev_month").inc()
            prev_results = []

    total = len(results)
    mes_nome = MONTH_NAMES_PT[mes]
    periodo = f"Editais publicados de 1 a {last_day} de {mes_nome} de {ano}"

    # Extract values
    values: list[float] = []
    for r in results:
        v = r.get("valorTotalEstimado") or r.get("valorEstimado") or r.get("valor_estimado")
        if v and isinstance(v, (int, float)) and float(v) > 0:
            values.append(float(v))

    # Exclude P95+ outliers for average
    values_sorted = sorted(values)
    if values_sorted:
        p95_idx = int(len(values_sorted) * 0.95)
        values_filtered = values_sorted[:p95_idx] if p95_idx > 0 else values_sorted
    else:
        values_filtered = []

    valor_total = sum(values_sorted)
    valor_medio = sum(values_filtered) / len(values_filtered) if values_filtered else 0.0

    # Top UFs
    uf_counts: dict[str, int] = defaultdict(int)
    for r in results:
        uf = r.get("uf", "").upper()
        if uf:
            uf_counts[uf] += 1

    top_ufs_raw = sorted(uf_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_ufs = [
        UfCount(
            uf=uf,
            uf_name=UF_NAMES.get(uf, uf),
            total=count,
            pct=round(count / total * 100, 1) if total > 0 else 0.0,
        )
        for uf, count in top_ufs_raw
    ]

    # Modalidade distribution
    modalidade_counts: dict[int, int] = defaultdict(int)
    for r in results:
        mod_id = r.get("codigoModalidadeContratacao") or r.get("modalidade_id") or 0
        if mod_id:
            try:
                modalidade_counts[int(mod_id)] += 1
            except (ValueError, TypeError):
                pass

    modalidades = [
        ModalidadeCount(
            modalidade_id=mod_id,
            modalidade_name=MODALIDADE_NAMES.get(mod_id, f"Modalidade {mod_id}"),
            total=count,
            pct=round(count / total * 100, 1) if total > 0 else 0.0,
        )
        for mod_id, count in sorted(modalidade_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Weekly trend
    week_counts: dict[str, int] = defaultdict(int)
    for r in results:
        pub_date = r.get("dataPublicacaoFormatted") or r.get("data_publicacao", "")
        if pub_date and len(pub_date) >= 10:
            try:
                d = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                week_label = f"Semana {((d.day - 1) // 7) + 1}"
                week_counts[week_label] += 1
            except ValueError:
                pass

    tendencia = [
        MonthlyTrend(semana=week, total=count)
        for week, count in sorted(week_counts.items())
    ]

    # Sectors in high growth
    setores_em_alta = await _compute_setores_em_alta(results, prev_results)

    return {
        "mes": mes,
        "ano": ano,
        "mes_nome": mes_nome,
        "periodo": periodo,
        "total_editais": total,
        "valor_total": round(valor_total, 2),
        "valor_medio": round(valor_medio, 2),
        "top_ufs": [u.model_dump() for u in top_ufs],
        "modalidades": [m.model_dump() for m in modalidades],
        "tendencia_semanal": [t.model_dump() for t in tendencia],
        "setores_em_alta": [s.model_dump() for s in setores_em_alta],
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": "SmartLic Observatório — dados PNCP (Portal Nacional de Contratações Públicas)",
        "license": "Creative Commons BY 4.0 — https://creativecommons.org/licenses/by/4.0/",
        # STORY-431 AC11: marker stays False on success even when total==0 (data
        # really is zero for the period). _empty_relatorio_payload sets it to
        # True only on timeout/error fallback paths.
        "is_empty_period": False,
    }


async def _compute_setores_em_alta(
    results: list[dict], prev_results: list[dict]
) -> list[SetorHighlight]:
    """Compare sector volumes: current vs previous month. Returns top 5 by growth."""
    try:
        from sectors import SECTORS
    except ImportError:
        return []

    def count_by_sector(records: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for setor_id, sector in SECTORS.items():
            keywords_lower = {kw.lower() for kw in sector.keywords}
            count = 0
            for r in records:
                title = (r.get("objetoCompra") or r.get("titulo") or "").lower()
                if any(kw in title for kw in keywords_lower):
                    count += 1
            if count > 0:
                counts[setor_id] = count
        return counts

    current_counts = count_by_sector(results)
    prev_counts = count_by_sector(prev_results)

    highlights: list[SetorHighlight] = []
    for setor_id, sector in SECTORS.items():
        atual = current_counts.get(setor_id, 0)
        anterior = prev_counts.get(setor_id, 0)
        if anterior > 0:
            variacao = round((atual - anterior) / anterior * 100, 1)
        elif atual > 0:
            variacao = 100.0
        else:
            continue

        if variacao > 20 and atual > 10:
            highlights.append(SetorHighlight(
                setor_id=setor_id,
                setor_name=sector.name,
                total_atual=atual,
                total_anterior=anterior,
                variacao_pct=variacao,
            ))

    return sorted(highlights, key=lambda h: h.variacao_pct, reverse=True)[:5]


def _build_csv(relatorio: RelatorioMensal) -> str:
    output = io.StringIO()

    # Header comment with source attribution
    output.write(
        f"# Fonte: SmartLic Observatório (smartlic.tech/observatorio). "
        f"Dados PNCP processados por IA.\n"
        f"# Período: {relatorio.periodo}\n"
        f"# Gerado em: {relatorio.gerado_em}\n"
        f"# Licença: Creative Commons BY 4.0\n\n"
    )

    writer = csv.writer(output)

    # Section 1: Summary
    writer.writerow(["# RESUMO"])
    writer.writerow(["Total de editais", relatorio.total_editais])
    writer.writerow(["Valor total estimado (R$)", f"{relatorio.valor_total:.2f}"])
    writer.writerow(["Valor médio por edital (R$)", f"{relatorio.valor_medio:.2f}"])
    writer.writerow([])

    # Section 2: Top UFs
    writer.writerow(["# TOP UFS"])
    writer.writerow(["UF", "Nome", "Total de editais", "% do total"])
    for uf in relatorio.top_ufs:
        writer.writerow([uf.uf, uf.uf_name, uf.total, f"{uf.pct:.1f}%"])
    writer.writerow([])

    # Section 3: Modalidades
    writer.writerow(["# DISTRIBUIÇÃO POR MODALIDADE"])
    writer.writerow(["Modalidade", "Total", "% do total"])
    for m in relatorio.modalidades:
        writer.writerow([m.modalidade_name, m.total, f"{m.pct:.1f}%"])
    writer.writerow([])

    # Section 4: Sectors in growth
    if relatorio.setores_em_alta:
        writer.writerow(["# SETORES EM ALTA"])
        writer.writerow(["Setor", "Total (mês atual)", "Total (mês anterior)", "Variação (%)"])
        for s in relatorio.setores_em_alta:
            writer.writerow([s.setor_name, s.total_atual, s.total_anterior, f"{s.variacao_pct:+.1f}%"])

    return output.getvalue()
