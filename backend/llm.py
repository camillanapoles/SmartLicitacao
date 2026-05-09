"""
LLM integration module for generating executive summaries of procurement bids.

This module uses OpenAI's GPT-4.1-nano model with structured output to create
actionable summaries of filtered procurement opportunities. It includes:
- Token-optimized input preparation (max 50 bids)
- Structured output using Pydantic schemas
- Error handling for API failures
- Empty input handling

Usage:
    from llm import gerar_resumo
    from schemas import ResumoLicitacoes

    licitacoes = [...]  # List of filtered bids
    resumo = gerar_resumo(licitacoes)
    print(resumo.resumo_executivo)
"""

from datetime import datetime
from typing import Any
import hashlib
import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

from schemas import ResumoLicitacoes, ResumoEstrategico, Recomendacao
from excel import parse_datetime

import re as _re_llm


def _fmt_brl(value: float) -> str:
    """Format float as pt-BR currency (e.g., 360.366,00)."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ground_truth_summary(resumo: "ResumoLicitacoes") -> None:
    """ISSUE-039 v2: Replace LLM-hallucinated numbers in free-text fields.

    The LLM may write "totalizando R$ 386.000.000,00" in resumo_executivo
    while the ground-truth valor_total is R$ 11.831.152,97.  This function
    patches the free-text so both the stats box and the paragraph agree.

    Also fixes the bid count (e.g., "15 licitações" → actual count).
    """
    if not resumo.resumo_executivo:
        return

    # 1. Replace monetary values in resumo_executivo with ground truth
    _money_pat = r"R\$\s*[\d.,]+(?:\s*(?:mil|milh[oõ]es|bilh[oõ]es|bi))?"
    _correct_valor = _fmt_brl(resumo.valor_total) if resumo.valor_total > 0 else "0,00"
    resumo.resumo_executivo = _re_llm.sub(
        _money_pat,
        f"R$ {_correct_valor}",
        resumo.resumo_executivo,
        count=1,
        flags=_re_llm.IGNORECASE,
    )

    # 1b. ISSUE-041: Clean up remaining abbreviated monetary values
    # Matches patterns like "R$ 1.2M", "R$ 500 mil", "R$ 2,3 milhões"
    def _normalize_money(match: "_re_llm.Match[str]") -> str:
        raw = match.group(0)
        # Extract numeric part (before suffix)
        num_str = _re_llm.search(r"R\$\s*([\d.,]+)", raw)
        if not num_str:
            return raw
        num_part = num_str.group(1).replace(".", "").replace(",", ".")
        try:
            value = float(num_part)
        except ValueError:
            return raw
        suffix_lower = raw.lower()
        if "bilh" in suffix_lower or suffix_lower.rstrip().endswith("bi"):
            value *= 1_000_000_000
        elif "milh" in suffix_lower or suffix_lower.rstrip().endswith("m"):
            value *= 1_000_000
        elif "mil" in suffix_lower:
            value *= 1_000
        return f"R$ {_fmt_brl(value)}"

    _abbrev_money_pat = r"R\$\s*[\d.,]+\s*(?:mil|milh[oõ]es?|bilh[oõ]es?|bi|M)\b"
    resumo.resumo_executivo = _re_llm.sub(
        _abbrev_money_pat, _normalize_money, resumo.resumo_executivo,
        flags=_re_llm.IGNORECASE,
    )

    # 2. Replace bid count in resumo_executivo (ISSUE-046: singular/plural)
    # ISSUE-039 v3: Also match "N oportunidades" — LLM sometimes uses this word
    _count_pat = r"\b(\d+)\s+(?:licita[çc][oõã]es?|oportunidades?)\b"
    _lic_word = "licitação" if resumo.total_oportunidades == 1 else "licitações"
    resumo.resumo_executivo = _re_llm.sub(
        _count_pat,
        f"{resumo.total_oportunidades} {_lic_word}",
        resumo.resumo_executivo,
        count=1,
        flags=_re_llm.IGNORECASE,
    )

    # 3. ISSUE-042: Remove stale absolute dates from resumo_executivo
    # Detect DD/MM/YYYY patterns and replace past dates with "[data encerrada]"
    _abs_date_pat = r"\b(\d{2})/(\d{2})/(\d{4})\b"
    _now = datetime.now()

    def _replace_stale_date(match: "_re_llm.Match[str]") -> str:
        try:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            dt = datetime(year, month, day)
            if dt < _now:
                return "[data encerrada]"
        except (ValueError, OverflowError):
            pass
        return match.group(0)

    resumo.resumo_executivo = _re_llm.sub(
        _abs_date_pat, _replace_stale_date, resumo.resumo_executivo
    )


def recompute_temporal_alerts(
    resumo: "ResumoLicitacoes",
    licitacoes: list[dict],
) -> None:
    """ISSUE-042: Recompute time-sensitive fields based on current datetime.

    LLM-generated destaques and alerta_urgencia contain absolute dates that
    become stale when served from cache.  This function replaces them with
    deterministic computations using actual bid deadlines vs now().
    """
    from datetime import timedelta, timezone as _tz

    now = datetime.now(_tz.utc)

    urgent_bids: list[tuple[dict, datetime]] = []
    closing_soon: list[tuple[dict, datetime]] = []

    for lic in licitacoes:
        deadline_str = (
            lic.get("dataEncerramentoProposta")
            or lic.get("dataAberturaProposta")
        )
        if not deadline_str:
            continue
        try:
            deadline = parse_datetime(deadline_str)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=_tz.utc)
            delta = deadline - now
            if timedelta(0) < delta <= timedelta(hours=24):
                urgent_bids.append((lic, deadline))
            elif timedelta(hours=24) < delta <= timedelta(days=7):
                closing_soon.append((lic, deadline))
        except (ValueError, TypeError, AttributeError):
            continue

    # Replace alerta_urgencia with ground-truth
    if urgent_bids:
        _n = len(urgent_bids)
        _verbo_urgencia = "licitação encerra" if _n == 1 else "licitações encerram"
        resumo.alerta_urgencia = f"⚠️ {_n} {_verbo_urgencia} nas próximas 24 horas."
    elif closing_soon:
        _n = len(closing_soon)
        _verbo_7d = "licitação encerra" if _n == 1 else "licitações encerram"
        resumo.alerta_urgencia = f"⚠️ {_n} {_verbo_7d} em até 7 dias."
    else:
        resumo.alerta_urgencia = None

    # Filter date-containing destaques and replace with computed ones
    if resumo.destaques:
        _date_re = _re_llm.compile(
            r"\d{2}/\d{2}/\d{4}|encerram?\b|prazo de abertura|vence",
            _re_llm.IGNORECASE,
        )
        resumo.destaques = [
            d for d in resumo.destaques if not _date_re.search(d)
        ]

    if not resumo.destaques:
        resumo.destaques = []

    if urgent_bids:
        for lic, dl in urgent_bids[:3]:
            obj = (lic.get("objetoCompra") or "")[:60]
            resumo.destaques.append(
                f"URGENTE: \"{obj}\" encerra em {dl.strftime('%d/%m/%Y')}"
            )
    elif closing_soon:
        count_7d = len(closing_soon)
        _verbo_abertura = "licitação com abertura" if count_7d == 1 else "licitações com abertura"
        resumo.destaques.append(
            f"{count_7d} {_verbo_abertura} nos próximos 7 dias"
        )


def gerar_resumo(licitacoes: list[dict[str, Any]], *, sector_name: str = "licitações", termos_busca: str | None = None, setor_id: str | None = None) -> ResumoLicitacoes:
    """
    Generate AI-powered executive summary of procurement bids using GPT-4.1-nano.

    This function calls OpenAI's API with structured output to create a comprehensive
    summary of filtered procurement opportunities. It optimizes for token usage by
    limiting input to 50 bids and truncating long descriptions.

    Args:
        licitacoes: List of filtered procurement bid dictionaries from PNCP API.
                   Each dict should contain keys: objetoCompra, nomeOrgao, uf,
                   municipio, valorTotalEstimado, dataAberturaProposta

    Returns:
        ResumoLicitacoes: Structured summary containing:
            - resumo_executivo: 1-2 sentence overview
            - total_oportunidades: Count of opportunities
            - valor_total: Sum of all bid values in BRL
            - destaques: 2-5 key highlights
            - alerta_urgencia: Optional time-sensitive alert

    Raises:
        ValueError: If OPENAI_API_KEY environment variable is not set
        OpenAI API errors: Network issues, rate limits, auth failures

    Examples:
        >>> licitacoes = [
        ...     {
        ...         "objetoCompra": "Uniforme escolar",
        ...         "nomeOrgao": "Prefeitura de São Paulo",
        ...         "uf": "SP",
        ...         "valorTotalEstimado": 100000.0,
        ...         "dataAberturaProposta": "2025-02-15T10:00:00"
        ...     }
        ... ]
        >>> resumo = gerar_resumo(licitacoes)
        >>> resumo.total_oportunidades
        1
    """
    # ISSUE-016/017: Resolve display context — prefer termos_busca over sector_name
    if termos_busca:
        _context_label = f"busca por termos específicos: {termos_busca}"
    elif sector_name and sector_name != "licitações":
        _context_label = sector_name
    else:
        _context_label = "licitações"

    # Handle empty input
    if not licitacoes:
        return ResumoLicitacoes(
            resumo_executivo=f"Nenhuma licitação de {_context_label.lower()} encontrada no período selecionado.",
            total_oportunidades=0,
            valor_total=0.0,
            destaques=[],
            alerta_urgencia=None,
        )

    # Validate API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. "
            "Please configure your OpenAI API key."
        )

    # Prepare data for LLM (limit to 50 bids to avoid token overflow)
    dados_resumidos = []
    for lic in licitacoes[:50]:
        dados_resumidos.append(
            {
                "objeto": (lic.get("objetoCompra") or "")[
                    :200
                ],  # Truncate to 200 chars
                "orgao": lic.get("nomeOrgao") or "",
                "uf": lic.get("uf") or "",
                "municipio": lic.get("municipio") or "",
                "valor": lic.get("valorTotalEstimado") or 0,
                "abertura": lic.get("dataAberturaProposta") or "",
            }
        )

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)

    # ISSUE-026: Load sector keywords for contextual summary if setor_id provided
    _sector_context_line = ""
    if setor_id and not termos_busca:
        try:
            from sectors import get_sector as _get_sector_llm
            _sec = _get_sector_llm(setor_id)
            _sec_kws = sorted(getattr(_sec, "keywords", []), key=len, reverse=True)[:10]
            if _sec_kws:
                _sector_context_line = (
                    f"\nSETOR ALVO: {sector_name}\n"
                    f"Palavras-chave relevantes: {', '.join(_sec_kws)}\n"
                    f"- Foque o resumo nos itens mais relevantes para o setor {sector_name}. "
                    f"Ignore itens claramente fora do escopo do setor.\n"
                )
        except Exception:
            pass

    # System prompt with expert persona and rules
    system_prompt = f"""Você é um analista de licitações.
Analise as licitações fornecidas e gere um resumo executivo.
{_sector_context_line}
REGRAS:
- Seja direto e objetivo
- Destaque as maiores oportunidades por valor
- Alerte sobre prazos próximos (< 7 dias)
- Mencione a distribuição geográfica
- Use linguagem profissional, não técnica demais
- Valores sempre em reais (R$) no formato R$ 1.234.567,89 (com centavos, sem abreviações como 'M' ou 'mil')
- NÃO mencione datas absolutas de encerramento no resumo. Use prazos relativos como 'nos próximos X dias'
- IMPORTANTE: NÃO afirme que todas as licitações são sobre um tema específico a menos que realmente sejam. Descreva o que os objetos REALMENTE tratam, baseado nos textos fornecidos.
- Se os objetos tratam de assuntos variados, diga isso explicitamente.
"""

    # UX-427: Explicitly state the searched sector/terms in the user prompt so
    # the LLM does not drift to a different sector even if some bids are ambiguous.
    _busca_label = ""
    if termos_busca:
        _busca_label = f"\nSETOR/TERMOS BUSCADOS PELO USUÁRIO: {termos_busca}\n"
    elif sector_name and sector_name != "licitações":
        _busca_label = f"\nSETOR BUSCADO PELO USUÁRIO: {sector_name}\n"

    # User prompt with context — grounded, no assumption of relevance
    user_prompt = f"""Analise estas {len(licitacoes)} licitações e gere um resumo baseado nos OBJETOS REAIS listados abaixo:
{_busca_label}
{json.dumps(dados_resumidos, ensure_ascii=False, indent=2)}

Data atual: {datetime.now().strftime("%d/%m/%Y")}
"""

    # Call OpenAI API with structured output
    response = client.beta.chat.completions.parse(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=ResumoLicitacoes,
        temperature=0.3,
        max_tokens=500,
    )

    # Extract parsed response
    resumo = response.choices[0].message.parsed

    if not resumo:
        raise ValueError("OpenAI API returned empty response")

    # DEBT-v3-S2 AC1-AC2: Track LLM cost and tokens for summary generation
    try:
        if response.usage:
            _input_tokens = response.usage.prompt_tokens or 0
            _output_tokens = response.usage.completion_tokens or 0
            from metrics import LLM_COST_USD, LLM_TOKENS_DETAILED
            _model_name = "gpt-4.1-nano"
            # gpt-4.1-nano pricing: $0.10/1M input, $0.40/1M output
            _cost_usd = _input_tokens * 0.10 / 1_000_000 + _output_tokens * 0.40 / 1_000_000
            LLM_COST_USD.labels(model=_model_name, operation="summary").inc(_cost_usd)
            LLM_TOKENS_DETAILED.labels(model=_model_name, operation="summary", direction="input").inc(_input_tokens)
            LLM_TOKENS_DETAILED.labels(model=_model_name, operation="summary", direction="output").inc(_output_tokens)

            # STORY-2.11 (EPIC-TD-2026Q2 P0): Track cost in monthly budget counter.
            # Fire-and-forget — nunca bloqueia a request.
            # CIG-BE-asyncio-run-production-scan Phase 2 Option C:
            # skip tracking instead of spinning a throwaway loop via asyncio.run()
            # when invoked from a thread pool worker. Long-term fix (Option A) is
            # run_coroutine_threadsafe on the main app loop — tracked as dívida.
            try:
                import asyncio as _asyncio
                from llm_budget import track_llm_cost as _track

                try:
                    _loop = _asyncio.get_running_loop()
                    _asyncio.ensure_future(_track(_cost_usd))
                except RuntimeError:
                    from metrics import LLM_BUDGET_TRACK_SKIPPED as _skipped

                    _skipped.labels(reason="no_running_loop").inc()
            except Exception:
                pass
    except Exception:
        pass  # Never let metrics break summary generation

    # ISSUE-039: Ground summary stats on actual data, not LLM counts.
    # The LLM may independently re-analyze relevance and report a different
    # count/value than what the pipeline actually returns to the frontend.
    resumo.total_oportunidades = len(licitacoes)
    resumo.valor_total = sum(
        float(lic.get("valorTotalEstimado") or 0) for lic in licitacoes
    )

    # ISSUE-039 v2: Also fix the free-text resumo_executivo which may contain
    # LLM-hallucinated monetary values different from the ground-truth total.
    # The frontend displays BOTH the stats box (correct) and the paragraph text
    # (potentially wrong) — they must agree.
    _ground_truth_summary(resumo)

    # ISSUE-042: Recompute time-sensitive fields with current datetime
    recompute_temporal_alerts(resumo, licitacoes)

    return resumo


def generate_cnpj_narrative(data: dict[str, Any]) -> dict[str, str]:
    """Generate competitive intelligence narrative for a CNPJ supplier report.

    Uses GPT-4.1-nano to produce a structured narrative covering
    competitive patterns, key clients, focus sectors, and risk points. Falls back
    to a deterministic text generator if the LLM call fails for any reason.

    Args:
        data: Aggregated supplier data from the `cnpj_supplier_intel` RPC.
              Relevant keys: total_contratos, valor_total, orgaos_top,
              objetos_top, uf_breakdown, esfera_breakdown.

    Returns:
        dict with keys:
            padrao_competitivo: Overview of competitive patterns.
            principais_clientes: Key buyer agencies.
            setores_foco: Focus sectors and contract objects.
            pontos_atencao: Risks and attention points.
    """
    # Always try LLM first; deterministic fallback on any exception.
    try:
        return _generate_cnpj_narrative_llm(data)
    except Exception:
        logger.warning("cnpj narrative LLM failed, using fallback", exc_info=True)
    return _generate_cnpj_narrative_fallback(data)


def _build_cnpj_narrative_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Prepare a compact token-efficient payload for the LLM."""
    orgaos = (data.get("orgaos_top") or [])[:10]
    orgaos_summary = [
        {
            "orgao": str(o.get("orgao_nome") or o.get("orgao") or ""),
            "uf": o.get("uf") or "",
            "contratos": o.get("total_contratos") or o.get("n_contratos") or 0,
            "valor": o.get("valor_total") or 0,
        }
        for o in orgaos
    ]

    objetos = (data.get("objetos_top") or [])[:10]
    objetos_summary = [
        {
            "objeto": (o.get("objeto") or o.get("descricao") or "")[:100],
            "frequencia": o.get("frequencia") or o.get("count") or 0,
        }
        for o in objetos
    ]

    uf_bd = data.get("uf_breakdown") or {}
    esfera_bd = data.get("esfera_breakdown") or {}

    return {
        "total_contratos": data.get("total_contratos") or 0,
        "valor_total": data.get("valor_total") or 0,
        "orgaos_top": orgaos_summary,
        "objetos_top": objetos_summary,
        "uf_breakdown": {k: (v if not isinstance(v, dict) else v.get("total_contratos", 0)) for k, v in uf_bd.items()},
        "esfera_breakdown": esfera_bd,
    }


def _generate_cnpj_narrative_llm(data: dict[str, Any]) -> dict[str, str]:
    """LLM path for generate_cnpj_narrative."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    payload = _build_cnpj_narrative_payload(data)
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "Você é um analista de inteligência competitiva B2G (Business-to-Government) "
        "especializado no mercado de licitações públicas do Brasil. "
        "Com base nos dados agregados de contratos públicos de um fornecedor, "
        "gere uma análise concisa e objetiva em português. "
        "Responda SOMENTE com um JSON com exatamente as 4 chaves solicitadas. "
        "Use linguagem profissional e direta. Máximo 3 parágrafos por campo."
    )

    user_prompt = (
        f"Analise os seguintes dados de contratos públicos de um fornecedor:\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Retorne um JSON com exatamente estas chaves:\n"
        "- padrao_competitivo: Descreva o padrão geral de atuação competitiva do fornecedor.\n"
        "- principais_clientes: Descreva os principais órgãos compradores e sua relevância.\n"
        "- setores_foco: Descreva os setores e tipos de contratos em que o fornecedor se especializa.\n"
        "- pontos_atencao: Identifique riscos, concentração excessiva ou outros pontos de atenção.\n"
    )

    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    return {
        "padrao_competitivo": str(parsed.get("padrao_competitivo") or ""),
        "principais_clientes": str(parsed.get("principais_clientes") or ""),
        "setores_foco": str(parsed.get("setores_foco") or ""),
        "pontos_atencao": str(parsed.get("pontos_atencao") or ""),
    }


def _generate_cnpj_narrative_fallback(data: dict[str, Any]) -> dict[str, str]:
    """Deterministic fallback for generate_cnpj_narrative when LLM is unavailable."""
    total_c = data.get("total_contratos") or 0
    valor_t = float(data.get("valor_total") or 0)

    orgaos = (data.get("orgaos_top") or [])[:3]
    orgaos_str = ", ".join(
        o.get("orgao_nome") or o.get("orgao") or "—"
        for o in orgaos
    ) or "não identificados"

    objetos = (data.get("objetos_top") or [])[:3]
    objetos_str = ", ".join(
        (o.get("objeto") or o.get("descricao") or "")[:60]
        for o in objetos
    ) or "não identificados"

    uf_bd = data.get("uf_breakdown") or {}
    ufs_str = ", ".join(list(uf_bd.keys())[:5]) if uf_bd else "diversas UFs"

    ticket = (valor_t / total_c) if total_c > 0 else 0.0

    padrao = (
        f"Fornecedor com {total_c} contrato(s) registrado(s), "
        f"totalizando R$ {_fmt_brl(valor_t)} e ticket médio de R$ {_fmt_brl(ticket)}."
    )
    clientes = f"Principais compradores: {orgaos_str}."
    setores = f"Principais objetos contratados: {objetos_str}."
    atencao = (
        f"Presença em {ufs_str}. "
        "Verifique concentração de receita nos principais clientes e "
        "eventuais impedimentos de participação em licitações."
    )

    return {
        "padrao_competitivo": padrao,
        "principais_clientes": clientes,
        "setores_foco": setores,
        "pontos_atencao": atencao,
    }


def format_resumo_html(resumo: ResumoLicitacoes) -> str:
    """
    Format executive summary as HTML for frontend display.

    Converts the structured ResumoLicitacoes object into styled HTML with:
    - Executive summary paragraph
    - Statistics cards (count and total value)
    - Urgency alert (if present)
    - Highlights list

    Args:
        resumo: Structured summary from gerar_resumo()

    Returns:
        str: HTML string ready for frontend rendering

    Examples:
        >>> resumo = ResumoLicitacoes(
        ...     resumo_executivo="Encontradas 15 licitações.",
        ...     total_oportunidades=15,
        ...     valor_total=2300000.00,
        ...     destaques=["3 urgentes"],
        ...     alerta_urgencia="⚠️ 5 encerram em 24h"
        ... )
        >>> html = format_resumo_html(resumo)
        >>> "resumo-container" in html
        True
    """
    # Build urgency alert HTML if present
    alerta_html = ""
    if resumo.alerta_urgencia:
        alerta_html = f'<div class="alerta-urgencia">⚠️ {resumo.alerta_urgencia}</div>'

    # Build highlights list HTML
    destaques_html = ""
    if resumo.destaques:
        destaques_items = "".join(f"<li>{d}</li>" for d in resumo.destaques)
        destaques_html = f"""
        <div class="destaques">
            <h4>Destaques:</h4>
            <ul>
                {destaques_items}
            </ul>
        </div>
        """

    # Assemble complete HTML
    html = f"""
    <div class="resumo-container">
        <p class="resumo-executivo">{resumo.resumo_executivo}</p>

        <div class="resumo-stats">
            <div class="stat">
                <span class="stat-value">{resumo.total_oportunidades}</span>
                <span class="stat-label">Licitações</span>
            </div>
            <div class="stat">
                <span class="stat-value">R$ {_fmt_brl(resumo.valor_total)}</span>
                <span class="stat-label">Valor Total</span>
            </div>
        </div>

        {alerta_html}

        {destaques_html}
    </div>
    """

    return html


def gerar_resumo_fallback(
    licitacoes: list[dict[str, Any]],
    *,
    sector_name: str = "licitações",
    termos_busca: str | None = None,
) -> ResumoEstrategico:
    """
    Generate basic executive summary without using LLM (fallback for OpenAI failures).

    This function provides a statistical summary using pure Python logic when the
    OpenAI API is unavailable due to network issues, rate limits, missing API key,
    or any other errors. It maintains the same ResumoEstrategico schema as gerar_resumo()
    for seamless fallback integration.

    Features:
    - Calculates total opportunities and total value
    - Computes UF distribution (state-wise breakdown)
    - Highlights top 3 bids by value
    - Detects urgent bids (deadline < 7 days, excludes expired)
    - Generates actionable recommendations
    - No external dependencies (works offline)

    Args:
        licitacoes: List of filtered procurement bid dictionaries from PNCP API.
                   Each dict should contain keys: objetoCompra, nomeOrgao, uf,
                   valorTotalEstimado, dataAberturaProposta
        sector_name: Name of the sector being searched (e.g., "Engenharia Civil").
                    Defaults to "licitações" for backward compatibility.
        termos_busca: Optional search terms entered by the user. When provided,
                     these are used in the summary instead of sector_name.

    Returns:
        ResumoEstrategico: Structured summary with recommendations and sector insight.

    Examples:
        >>> licitacoes = [
        ...     {
        ...         "nomeOrgao": "Prefeitura de SP",
        ...         "uf": "SP",
        ...         "valorTotalEstimado": 150000.0,
        ...         "dataAberturaProposta": "2025-03-01T10:00:00"
        ...     },
        ...     {
        ...         "nomeOrgao": "Prefeitura do RJ",
        ...         "uf": "RJ",
        ...         "valorTotalEstimado": 200000.0,
        ...         "dataAberturaProposta": "2025-03-15T14:00:00"
        ...     }
        ... ]
        >>> resumo = gerar_resumo_fallback(licitacoes)
        >>> resumo.total_oportunidades
        2
        >>> resumo.valor_total
        350000.0
    """
    # Determine the display label for the summary
    display_label = termos_busca if termos_busca else sector_name

    # Handle empty input
    if not licitacoes:
        if termos_busca:
            _insight = f"Nenhuma oportunidade encontrada para '{termos_busca}'. Considere ampliar o período ou os estados da análise."
        else:
            _insight = f"Setor de {sector_name}: Nenhuma oportunidade encontrada. Considere ampliar o período ou os estados da análise."
        return ResumoEstrategico(
            resumo_executivo="Nenhuma licitação encontrada.",
            total_oportunidades=0,
            valor_total=0.0,
            destaques=[],
            alerta_urgencia=None,
            recomendacoes=[],
            alertas_urgencia=[],
            insight_setorial=_insight,
        )

    # Calculate basic statistics
    total = len(licitacoes)
    valor_total = sum(lic.get("valorTotalEstimado", 0) or 0 for lic in licitacoes)

    # Compute UF distribution (state-wise breakdown)
    dist_uf: dict[str, int] = {}
    for lic in licitacoes:
        uf = lic.get("uf", "N/A")
        dist_uf[uf] = dist_uf.get(uf, 0) + 1

    # Find top 3 bids by value
    top_valor = sorted(
        licitacoes, key=lambda x: x.get("valorTotalEstimado", 0) or 0, reverse=True
    )[:3]

    destaques = [
        f"{lic.get('nomeOrgao', 'N/A')}: R$ {_fmt_brl(lic.get('valorTotalEstimado') or 0)}"
        for lic in top_valor
    ]

    # Check for urgency (deadline < 7 days, exclude expired bids)
    alerta = None
    alertas_urgencia: list[str] = []
    recomendacoes: list[Recomendacao] = []
    hoje = datetime.now()
    for lic in licitacoes:
        data_abertura_str = lic.get("dataAberturaProposta")
        if not data_abertura_str:
            continue

        abertura = parse_datetime(data_abertura_str)
        if abertura:
            dias_restantes = (abertura - hoje).days
            # Only alert for future deadlines (not expired)
            if 0 <= dias_restantes < 7:
                orgao = lic.get("nomeOrgao", "Órgão não informado")
                alerta_text = f"{orgao} encerra em {dias_restantes} dia(s)"
                alertas_urgencia.append(alerta_text)
                if alerta is None:
                    alerta = alerta_text

    # Build recommendations from top bids
    for lic in top_valor:
        valor = lic.get("valorTotalEstimado") or 0
        orgao = lic.get("nomeOrgao", "N/A")
        objeto = (lic.get("objetoCompra") or "Objeto não informado")[:100]

        # Determine urgency from deadline
        urgencia = "baixa"
        data_abertura_str = lic.get("dataAberturaProposta")
        if data_abertura_str:
            abertura = parse_datetime(data_abertura_str)
            if abertura:
                dias = (abertura - hoje).days
                if dias < 0:
                    urgencia = "baixa"  # expired
                elif dias < 3:
                    urgencia = "alta"
                elif dias < 7:
                    urgencia = "media"

        recomendacoes.append(Recomendacao(
            oportunidade=f"{orgao} - {objeto}",
            valor=valor,
            urgencia=urgencia,
            acao_sugerida="Avaliar edital e preparar documentação.",
            justificativa=f"Valor estimado de R$ {_fmt_brl(valor)}.",
        ))

    # Build sector insight
    if termos_busca:
        insight = f"Análise de '{termos_busca}': {total} oportunidade(s) encontrada(s) totalizando R$ {_fmt_brl(valor_total)}."
    else:
        insight = f"Setor de {sector_name}: {total} oportunidade(s) encontrada(s) totalizando R$ {_fmt_brl(valor_total)}."

    # ISSUE-046: singular/plural concordance
    _lic_word_fb = "licitação" if total == 1 else "licitações"
    _encontradas_fb = "Encontrada" if total == 1 else "Encontradas"
    return ResumoEstrategico(
        resumo_executivo=(
            f"{_encontradas_fb} {total} {_lic_word_fb} no período analisado, "
            f"totalizando R$ {_fmt_brl(valor_total)}."
        ),
        total_oportunidades=total,
        valor_total=valor_total,
        destaques=destaques,
        alerta_urgencia=alerta,
        recomendacoes=recomendacoes,
        alertas_urgencia=alertas_urgencia,
        insight_setorial=insight,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Redis cache layer for LLM summaries (Issue #160)
# ─────────────────────────────────────────────────────────────────────────────

_LLM_SUMMARY_CACHE_TTL = 7 * 24 * 3600  # 7 days in seconds


def _build_resumo_cache_key(
    licitacoes: list[dict[str, Any]],
    sector_name: str,
    termos_busca: str | None,
    setor_id: str | None,
) -> str:
    """Build a deterministic SHA-256 cache key for a gerar_resumo call.

    Key components:
    - Sorted list of stable bid IDs (``numeroControlePNCP`` or ``codigoCompra``
      or ``id`` — first truthy wins). Bids without any stable ID are skipped
      from the key but still included in the LLM payload (they're rare edge cases).
    - sector_name, termos_busca, setor_id — all affect the generated text.
    """
    bid_ids: list[str] = []
    for lic in licitacoes:
        bid_id = (
            lic.get("numeroControlePNCP")
            or lic.get("codigoCompra")
            or lic.get("id")
        )
        if bid_id:
            bid_ids.append(str(bid_id))

    payload = {
        "bid_ids": sorted(bid_ids),
        "sector_name": sector_name or "",
        "termos_busca": termos_busca or "",
        "setor_id": setor_id or "",
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"llm:summary:{digest}"


async def get_or_generate_resumo_cached(
    licitacoes: list[dict[str, Any]],
    *,
    sector_name: str = "licitações",
    termos_busca: str | None = None,
    setor_id: str | None = None,
) -> ResumoLicitacoes:
    """Async wrapper around gerar_resumo with Redis cache (Issue #160).

    Cache key is a SHA-256 hash of the sorted bid IDs + search parameters.
    TTL: 7 days (summaries don't change for the same set of bids).

    On cache hit  → returns cached ResumoLicitacoes without calling OpenAI.
    On cache miss → calls gerar_resumo(), stores result, returns it.
    Redis unavailable → transparent fallback, calls gerar_resumo() directly.

    NOTE: empty-input case is short-circuited in gerar_resumo() before any
    OpenAI call, so we let it pass through without caching (TTL would be 0s
    anyway since the result is deterministic and fast).
    """
    from metrics import LLM_SUMMARY_CACHE_HITS, LLM_SUMMARY_CACHE_MISSES

    # Do not cache empty-input case — it's a fast, deterministic response.
    if not licitacoes:
        return gerar_resumo(
            licitacoes,
            sector_name=sector_name,
            termos_busca=termos_busca,
            setor_id=setor_id,
        )

    cache_key = _build_resumo_cache_key(licitacoes, sector_name, termos_busca, setor_id)

    # --- Try cache read ---
    try:
        from cache_module import redis_cache

        cached_raw = await redis_cache.get(cache_key)
        if cached_raw:
            resumo = ResumoLicitacoes.model_validate_json(cached_raw)
            LLM_SUMMARY_CACHE_HITS.inc()
            logger.debug("llm.cache_hit key=%s", cache_key)
            # Re-apply temporal alerts (time-sensitive fields must reflect *now*).
            recompute_temporal_alerts(resumo, licitacoes)
            return resumo
    except Exception as _cache_read_err:
        logger.debug("llm.cache_read_error key=%s err=%s", cache_key, _cache_read_err)

    # --- Cache miss: call OpenAI ---
    LLM_SUMMARY_CACHE_MISSES.inc()
    logger.debug("llm.cache_miss key=%s", cache_key)

    resumo = gerar_resumo(
        licitacoes,
        sector_name=sector_name,
        termos_busca=termos_busca,
        setor_id=setor_id,
    )

    # --- Store in cache (fire-and-forget on error) ---
    try:
        from cache_module import redis_cache as _rc  # same singleton

        await _rc.setex(cache_key, _LLM_SUMMARY_CACHE_TTL, resumo.model_dump_json())
        logger.debug("llm.cache_stored key=%s ttl=%d", cache_key, _LLM_SUMMARY_CACHE_TTL)
    except Exception as _cache_write_err:
        logger.debug("llm.cache_write_error key=%s err=%s", cache_key, _cache_write_err)

    return resumo
