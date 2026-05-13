"""Lead magnet PDF generator — datalake-powered market insights.

Produces a 3-4 page A4 PDF with exclusive PNCP datalake analytics that
no competitor can replicate. Used as the email attachment for lead capture
conversion (#1169).

Pages:
  1. National panorama (volume by sector, modality distribution, total value)
  2. Geography & top buyers (UF heatmap data, top contracting organs)
  3. Sector intelligence (personalized, only when lead provides a sector)
  4. CTA + data freshness stamp

Dependencies: ReportLab (already in requirements.txt). No matplotlib needed —
charts are rendered as styled tables with metric boxes.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand & layout constants (synced with pdf_generator_edital.py)
# ---------------------------------------------------------------------------
SMARTLIC_GREEN = colors.HexColor("#2E7D32")
SMARTLIC_DARK = colors.HexColor("#1B5E20")
BRAND_NAVY = colors.HexColor("#1B3A5C")
BRAND_LIGHT_BG = colors.HexColor("#E8F0FE")
ACCENT_BLUE = colors.HexColor("#3B82F6")

TABLE_HEADER_BG = BRAND_NAVY
TABLE_ALT_ROW = colors.HexColor("#F8FAFC")
TABLE_BORDER = colors.HexColor("#CBD5E1")
METRIC_BOX_BG = colors.HexColor("#EFF6FF")
HIGHLIGHT_GREEN_BG = colors.HexColor("#DCFCE7")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

FOOTER_TEXT = "SmartLic — smartlic.tech | Dados: PNCP (datalake proprietário) | {data}"

# Modalidade display names
MODALIDADE_LABELS: dict[int, str] = {
    4: "Pregão Eletrônico",
    5: "Concorrência",
    6: "Dispensa",
    7: "Inexigibilidade",
    8: "Tomada de Preços",
    12: "Leilão",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _s(text: Any) -> str:
    if text is None:
        return ""
    return ILLEGAL_CHARACTERS_RE.sub(" ", html.escape(str(text)))


def _fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v >= 1_000_000_000:
        return f"R$ {v / 1e9:.1f} bi"
    if v >= 1_000_000:
        return f"R$ {v / 1e6:.1f} mi"
    if v >= 1_000:
        return f"R$ {v / 1e3:,.0f} mil"
    return f"R$ {v:,.2f}"


def _fmt_int(value: Any) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", ".")


def _fmt_pct(value: float | None, total: float | None = None) -> str:
    if value is None:
        return "—"
    if total and total > 0:
        return f"{value / total * 100:.1f}%"
    return f"{value * 100:.1f}%" if value <= 1 else f"{value:.1f}%"


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    parent = base["Normal"]

    def _ps(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=parent, **kw)

    return {
        "title": _ps("lm-title", fontSize=22, leading=26, textColor=BRAND_NAVY,
                       spaceAfter=6, fontName="Helvetica-Bold"),
        "subtitle": _ps("lm-subtitle", fontSize=12, leading=16, textColor=colors.HexColor("#64748B"),
                          spaceAfter=12, fontName="Helvetica"),
        "h2": _ps("lm-h2", fontSize=16, leading=20, textColor=SMARTLIC_DARK,
                   spaceBefore=16, spaceAfter=8, fontName="Helvetica-Bold"),
        "h3": _ps("lm-h3", fontSize=13, leading=16, textColor=BRAND_NAVY,
                   spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold"),
        "body": _ps("lm-body", fontSize=10, leading=14, textColor=colors.HexColor("#334155"),
                     spaceAfter=6, fontName="Helvetica"),
        "metric_value": _ps("lm-metric", fontSize=28, leading=32, textColor=SMARTLIC_DARK,
                             fontName="Helvetica-Bold", alignment=TA_CENTER),
        "metric_label": _ps("lm-mlabel", fontSize=9, leading=12, textColor=colors.HexColor("#64748B"),
                              alignment=TA_CENTER, fontName="Helvetica"),
        "caption": _ps("lm-caption", fontSize=8, leading=10, textColor=colors.HexColor("#94A3B8"),
                        alignment=TA_CENTER, fontName="Helvetica"),
        "cta": _ps("lm-cta", fontSize=13, leading=18, textColor=SMARTLIC_GREEN,
                    fontName="Helvetica-Bold", alignment=TA_CENTER),
        "small": _ps("lm-small", fontSize=8, leading=10, textColor=colors.HexColor("#94A3B8"),
                      fontName="Helvetica"),
    }


# ---------------------------------------------------------------------------
# Metric boxes (header KPI strip)
# ---------------------------------------------------------------------------
def _metric_box(label: str, value: str, styles: dict) -> Table:
    """Single KPI box: big number + label."""
    data = [[Paragraph(value, styles["metric_value"])],
            [Paragraph(label, styles["metric_label"])]]
    t = Table(data, colWidths=[CONTENT_WIDTH / 3 - 4 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), METRIC_BOX_BG),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def _metric_strip(metrics: list[tuple[str, str]], styles: dict) -> Table:
    """Horizontal row of 3 KPI boxes."""
    boxes = [_metric_box(label, value, styles) for label, value in metrics]
    return Table([boxes], colWidths=[CONTENT_WIDTH / 3] * len(boxes))


# ---------------------------------------------------------------------------
# Data tables
# ---------------------------------------------------------------------------
def _styled_table(headers: list[str], rows: list[list[str]],
                  col_widths: list[float] | None = None,
                  alignments: list[int] | None = None) -> Table:
    """Consistent table with navy header + alternating rows."""
    header_row = [Paragraph(f"<b>{h}</b>",
                   ParagraphStyle("th", fontSize=9, leading=12, textColor=colors.white,
                                  fontName="Helvetica-Bold"))
                  for h in headers]
    data = [header_row]
    for row in rows:
        data.append([Paragraph(cell, ParagraphStyle("td", fontSize=9, leading=12,
                               textColor=colors.HexColor("#334155"), fontName="Helvetica"))
                     for cell in row])

    if col_widths is None:
        col_widths = [CONTENT_WIDTH / len(headers)] * len(headers)
    if alignments is None:
        alignments = [TA_LEFT] * len(headers)

    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, align in enumerate(alignments):
        style_cmds.append(("ALIGN", (i, 0), (i, -1), align))

    # Alternating row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))

    t.setStyle(TableStyle(style_cmds))
    return t


# ---------------------------------------------------------------------------
# Datalake queries
# ---------------------------------------------------------------------------
async def _query_national_insights(sb) -> dict:
    """National-level datalake metrics (cached 6h in caller)."""
    from supabase_client import sb_execute

    now = datetime.now(timezone.utc)
    ninety_days_ago = now.replace(day=now.day - 90).isoformat() if now.day > 90 else \
        now.replace(month=now.month - 3).isoformat()

    # Total value + count
    total_resp = await sb_execute(
        sb.rpc("search_datalake", {
            "p_ufs": ["SP", "MG", "RJ", "RS", "PR", "SC", "BA", "DF", "GO", "PE",
                       "CE", "PA", "MT", "MS", "AM", "ES", "MA", "PB", "RN", "AL",
                       "PI", "SE", "RO", "TO", "AC", "AP", "RR"],
            "p_data_inicial": ninety_days_ago[:10],
            "p_data_final": now.strftime("%Y-%m-%d"),
            "p_limit": 20000,
        }),
        category="rpc",
    )
    rows = total_resp.data or []

    total_count = len(rows)
    total_value = sum((r.get("valor_total_estimado") or 0) for r in rows)

    # Modality distribution
    modality_counts: dict[str, int] = {}
    for r in rows:
        mn = r.get("modalidade_nome") or "Outro"
        modality_counts[mn] = modality_counts.get(mn, 0) + 1

    top_modalities = sorted(modality_counts.items(), key=lambda x: -x[1])[:6]

    # UF distribution (top 10)
    uf_counts: dict[str, int] = {}
    for r in rows:
        uf = r.get("uf") or "??"
        uf_counts[uf] = uf_counts.get(uf, 0) + 1

    top_ufs = sorted(uf_counts.items(), key=lambda x: -x[1])[:10]

    # Top buying organs
    orgao_counts: dict[str, int] = {}
    orgao_values: dict[str, float] = {}
    for r in rows:
        org = r.get("orgao_razao_social") or "Não informado"
        orgao_counts[org] = orgao_counts.get(org, 0) + 1
        orgao_values[org] = orgao_values.get(org, 0) + (r.get("valor_total_estimado") or 0)

    top_orgaos = sorted(orgao_counts.items(), key=lambda x: -x[1])[:5]

    # Average value by modality
    modality_values: dict[str, list[float]] = {}
    for r in rows:
        mn = r.get("modalidade_nome") or "Outro"
        v = r.get("valor_total_estimado")
        if v and v > 0:
            modality_values.setdefault(mn, []).append(v)

    avg_by_modality = {mn: sum(vals) / len(vals) for mn, vals in modality_values.items()}

    return {
        "period_days": 90,
        "total_count": total_count,
        "total_value": total_value,
        "top_modalities": top_modalities,
        "top_ufs": top_ufs,
        "top_orgaos": [(org, orgao_counts[org], _fmt_currency(orgao_values.get(org)))
                       for org, _ in top_orgaos],
        "avg_value_by_modality": avg_by_modality,
        "generated_at": now.isoformat(),
    }


async def _query_sector_insights(sb, setor: str, uf: str | None = None) -> dict | None:
    """Sector-specific datalake insights. Returns None if no data."""
    from supabase_client import sb_execute
    from sectors import SECTORS

    sector_config = SECTORS.get(setor, {})
    keywords = sector_config.get("keywords", [])[:10]

    if not keywords:
        return None

    now = datetime.now(timezone.utc)
    ninety_days_ago = (now.replace(day=1) if now.day > 90
                       else now.replace(month=max(1, now.month - 3), day=1))

    ufs = [uf] if uf else ["SP", "MG", "RJ", "RS", "PR", "SC", "BA", "DF", "GO",
                            "PE", "CE", "PA", "MT", "MS", "AM", "ES", "MA", "PB",
                            "RN", "AL", "PI", "SE", "RO", "TO", "AC", "AP", "RR"]

    # Query with keyword filter
    tsquery = " | ".join(keywords[:5])
    resp = await sb_execute(
        sb.rpc("search_datalake", {
            "p_ufs": ufs,
            "p_data_inicial": ninety_days_ago.strftime("%Y-%m-%d"),
            "p_data_final": now.strftime("%Y-%m-%d"),
            "p_tsquery": tsquery,
            "p_limit": 5000,
        }),
        category="rpc",
    )
    rows = resp.data or []
    if not rows:
        return None

    total_count = len(rows)
    total_value = sum((r.get("valor_total_estimado") or 0) for r in rows)

    # Top UFs for this sector
    uf_counts: dict[str, int] = {}
    for r in rows:
        u = r.get("uf") or "??"
        uf_counts[u] = uf_counts.get(u, 0) + 1
    top_ufs = sorted(uf_counts.items(), key=lambda x: -x[1])[:5]

    # Active opportunities (encerramento in future)
    active = [r for r in rows
              if r.get("data_encerramento")
              and r["data_encerramento"] > now.isoformat()]
    active_value = sum((r.get("valor_total_estimado") or 0) for r in active)

    avg_value = total_value / total_count if total_count > 0 else 0

    return {
        "setor": setor,
        "sector_name": sector_config.get("name", setor),
        "total_count": total_count,
        "total_value": total_value,
        "active_count": len(active),
        "active_value": active_value,
        "avg_value": avg_value,
        "top_ufs": top_ufs,
    }


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------
def _build_header_footer(canvas, doc):
    """Page template with header line + footer."""
    canvas.saveState()
    # Header: thin green line
    canvas.setStrokeColor(SMARTLIC_GREEN)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, PAGE_HEIGHT - MARGIN + 10,
                PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN + 10)
    # Footer
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(MARGIN, 1.2 * cm,
                      FOOTER_TEXT.format(data=datetime.now().strftime("%d/%m/%Y")))
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 1.2 * cm,
                           f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def _page_1_national(insights: dict, styles: dict) -> list:
    """Cover + national panorama."""
    story: list = []

    # Title
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Panorama de Licitações", styles["title"]))
    story.append(Paragraph("Brasil — Inteligência de Mercado B2G", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=SMARTLIC_GREEN,
                             spaceBefore=6, spaceAfter=10))

    # KPI strip
    story.append(_metric_strip([
        ("Licitações (90 dias)", _fmt_int(insights["total_count"])),
        ("Valor Total Movimentado", _fmt_currency(insights["total_value"])),
        ("Fontes", "PNCP — Datalake\nProprietário"),
    ], styles))
    story.append(Spacer(1, 8 * mm))

    # Insight blurb
    story.append(Paragraph(
        f"Análise baseada em <b>{_fmt_int(insights['total_count'])} licitações</b> "
        f"publicadas nos últimos 90 dias no PNCP (Portal Nacional de Contratações "
        f"Públicas), abrangendo os 27 estados brasileiros. Dados processados pelo "
        f"datalake proprietário SmartLic — cobertura diária, atualização automática.",
        styles["body"],
    ))

    # Section: Modalities
    story.append(Paragraph("Distribuição por Modalidade", styles["h2"]))
    mod_headers = ["Modalidade", "Volume", "Participação"]
    mod_rows = []
    total_mod = sum(c for _, c in insights["top_modalities"])
    for name, count in insights["top_modalities"]:
        mod_rows.append([name, _fmt_int(count),
                         _fmt_pct(count, total_mod)])
    mod_widths = [CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.25, CONTENT_WIDTH * 0.30]
    story.append(_styled_table(mod_headers, mod_rows, mod_widths, [TA_LEFT, TA_RIGHT, TA_RIGHT]))
    story.append(Spacer(1, 6 * mm))

    # Average value by modality
    if insights.get("avg_value_by_modality"):
        story.append(Paragraph("Valor Médio por Modalidade", styles["h3"]))
        avg_headers = ["Modalidade", "Valor Médio"]
        avg_rows = []
        for mn, avg in sorted(insights["avg_value_by_modality"].items(),
                              key=lambda x: -x[1])[:6]:
            avg_rows.append([mn, _fmt_currency(avg)])
        avg_widths = [CONTENT_WIDTH * 0.55, CONTENT_WIDTH * 0.45]
        story.append(_styled_table(avg_headers, avg_rows, avg_widths, [TA_LEFT, TA_RIGHT]))

    return story


def _page_2_geography(insights: dict, styles: dict) -> list:
    """Geography + top buyers."""
    story: list = []
    story.append(Paragraph("Geografia das Oportunidades", styles["h2"]))

    # Top UFs
    uf_headers = ["UF", "Volume de Licitações", "Posição"]
    uf_rows = []
    for i, (uf, count) in enumerate(insights["top_ufs"], 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
        uf_rows.append([uf, _fmt_int(count), medal])
    uf_widths = [CONTENT_WIDTH * 0.25, CONTENT_WIDTH * 0.50, CONTENT_WIDTH * 0.25]
    story.append(_styled_table(uf_headers, uf_rows, uf_widths, [TA_LEFT, TA_RIGHT, TA_CENTER]))
    story.append(Spacer(1, 10 * mm))

    # Top buyers
    story.append(Paragraph("Maiores Compradores Públicos", styles["h2"]))
    story.append(Paragraph(
        "Órgãos que mais publicaram licitações nos últimos 90 dias. "
        "Conhecer os compradores é o primeiro passo para uma estratégia B2G eficaz.",
        styles["body"],
    ))
    buyer_headers = ["Órgão", "Licitações", "Valor Total"]
    buyer_rows = []
    for org, count, val in insights["top_orgaos"][:5]:
        buyer_rows.append([_s(org)[:60], _fmt_int(count), val])
    buyer_widths = [CONTENT_WIDTH * 0.50, CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.28]
    story.append(_styled_table(buyer_headers, buyer_rows, buyer_widths,
                                [TA_LEFT, TA_RIGHT, TA_RIGHT]))

    story.append(Spacer(1, 10 * mm))

    # Insight box
    insight_text = (
        "<b>💡 Insight SmartLic:</b> Os 5 maiores órgãos concentram parcela "
        "significativa do volume de licitações. Empresas que monitoram esses "
        "compradores têm vantagem competitiva na preparação de propostas."
    )
    story.append(_insight_box(insight_text, styles))

    return story


def _page_3_sector(sector_data: dict, styles: dict) -> list:
    """Personalized sector intelligence page."""
    story: list = []
    sector_name = sector_data.get("sector_name", sector_data["setor"])

    story.append(Paragraph(f"Inteligência Setorial: {sector_name}", styles["h2"]))
    story.append(Paragraph(
        "Análise personalizada com base no setor que você informou. "
        "Dados extraídos em tempo real do datalake SmartLic.",
        styles["body"],
    ))

    # Sector KPI strip
    story.append(_metric_strip([
        ("Licitações no Setor (90d)", _fmt_int(sector_data["total_count"])),
        ("Valor Total no Setor", _fmt_currency(sector_data["total_value"])),
        ("Valor Médio por Edital", _fmt_currency(sector_data["avg_value"])),
    ], styles))
    story.append(Spacer(1, 6 * mm))

    # Active opportunities highlight
    story.append(Paragraph("Oportunidades Abertas Agora", styles["h3"]))
    active_box = Table(
        [[Paragraph(
            f"<b>{_fmt_int(sector_data['active_count'])}</b> licitações com prazo "
            f"aberto totalizando <b>{_fmt_currency(sector_data['active_value'])}</b>",
            ParagraphStyle("active", fontSize=11, leading=16,
                           textColor=SMARTLIC_DARK, fontName="Helvetica")
        )]],
        colWidths=[CONTENT_WIDTH - 12],
    )
    active_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HIGHLIGHT_GREEN_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    story.append(active_box)
    story.append(Spacer(1, 8 * mm))

    # Top UFs for this sector
    story.append(Paragraph(f"Top UFs para {sector_name}", styles["h3"]))
    uf_headers = ["UF", "Volume"]
    uf_rows = [[uf, _fmt_int(count)] for uf, count in sector_data["top_ufs"]]
    uf_widths = [CONTENT_WIDTH * 0.40, CONTENT_WIDTH * 0.60]
    story.append(_styled_table(uf_headers, uf_rows, uf_widths, [TA_LEFT, TA_RIGHT]))

    return story


def _page_4_cta(insights: dict, sector_data: dict | None, styles: dict) -> list:
    """CTA + freshness stamp."""
    story: list = []
    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph("Transforme Dados em Contratos", styles["title"]))
    story.append(Paragraph("Sua vantagem começa agora", styles["subtitle"]))
    story.append(Spacer(1, 10 * mm))

    # Summary numbers
    story.append(_metric_strip([
        ("Licitações no Datalake", "1.5M+"),
        ("Setores Mapeados", "20"),
        ("Atualização", "Diária"),
    ], styles))
    story.append(Spacer(1, 12 * mm))

    # CTA box
    cta_html = (
        "<b>O SmartLic monitora automaticamente</b> novos editais compatíveis com "
        "seu setor e região. Você recebe alertas diários, analisa a viabilidade "
        "de cada oportunidade e organiza seu pipeline de licitações — tudo em um só lugar."
    )
    story.append(Paragraph(cta_html, styles["body"]))
    story.append(Spacer(1, 8 * mm))

    cta_text = "Experimente o SmartLic grátis por 14 dias → smartlic.tech/cadastro"
    story.append(Paragraph(cta_text, styles["cta"]))
    story.append(Spacer(1, 8 * mm))

    # Secondary CTA
    if sector_data:
        setor_slug = sector_data["setor"]
        busca_cta = f"Ver licitações de {sector_data.get('sector_name', setor_slug)} agora → smartlic.tech/buscar?setor={setor_slug}"
        story.append(Paragraph(busca_cta, styles["cta"]))
        story.append(Spacer(1, 6 * mm))

    # Freshness stamp
    gen_time = insights.get("generated_at", datetime.now(timezone.utc).isoformat())
    try:
        gen_dt = datetime.fromisoformat(gen_time)
        stamp = f"Dados atualizados em {gen_dt.strftime('%d/%m/%Y às %H:%M')} (horário de Brasília)"
    except (ValueError, TypeError):
        stamp = "Dados extraídos do datalake SmartLic em tempo real"
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph(stamp, styles["caption"]))

    # Footer note
    story.append(Spacer(1, 15 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TABLE_BORDER,
                             spaceBefore=6, spaceAfter=6))
    story.append(Paragraph(
        "Este guia foi gerado automaticamente com dados do PNCP processados pelo "
        "SmartLic. Os insights são exclusivos e não podem ser replicados sem acesso "
        "ao nosso datalake proprietário. CONFENGE Avaliações e Inteligência "
        "Artificial LTDA — CNPJ 52.407.089/0001-09.",
        styles["small"],
    ))

    return story


def _insight_box(text: str, styles: dict) -> Table:
    """Highlighted insight callout box."""
    p = Paragraph(text, ParagraphStyle("insight", fontSize=10, leading=14,
                  textColor=BRAND_NAVY, fontName="Helvetica-Oblique"))
    t = Table([[p]], colWidths=[CONTENT_WIDTH - 16])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def generate_lead_magnet_pdf(
    email: str,
    setor: str | None = None,
    uf: str | None = None,
) -> bytes:
    """Generate the lead magnet PDF with datalake insights.

    Args:
        email: Lead email (for tracking, not embedded in PDF).
        setor: Optional sector key for personalized page 3.
        uf: Optional UF for geographic focus.

    Returns:
        PDF bytes ready for email attachment.
    """
    from supabase_client import get_supabase

    sb = get_supabase()
    styles = _build_styles()

    # National insights (always)
    logger.info("lead_magnet: fetching national datalake insights")
    insights = await _query_national_insights(sb)

    # Sector insights (only if lead provided a sector)
    sector_data = None
    if setor:
        try:
            logger.info(f"lead_magnet: fetching sector insights for {setor}")
            sector_data = await _query_sector_insights(sb, setor, uf)
        except Exception:
            logger.warning(f"lead_magnet: sector insights failed for {setor}", exc_info=True)

    # Build PDF
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 8,
        bottomMargin=MARGIN + 10,
        title="Guia de Oportunidades B2G — SmartLic",
        author="SmartLic",
        subject="Panorama de Licitações Públicas",
    )

    story: list = []
    story.extend(_page_1_national(insights, styles))
    story.append(PageBreak())
    story.extend(_page_2_geography(insights, styles))

    if sector_data:
        story.append(PageBreak())
        story.extend(_page_3_sector(sector_data, styles))

    story.append(PageBreak())
    story.extend(_page_4_cta(insights, sector_data, styles))

    doc.build(story, onFirstPage=_build_header_footer, onLaterPages=_build_header_footer)
    pdf_bytes = buf.getvalue()

    logger.info(
        f"lead_magnet: PDF generated ({len(pdf_bytes)} bytes) "
        f"setor={setor} uf={uf} bids={insights['total_count']}"
    )
    return pdf_bytes
