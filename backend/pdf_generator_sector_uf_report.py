"""pdf_generator_sector_uf_report.py — INTEL-REPORT-002: Panorama Setorial × UF PDF.

Generates an A4 PDF from data returned by the `sector_uf_intel` RPC.
Follows the same ReportLab conventions as pdf_generator_intel_report.py.

Usage (called by ARQ job in jobs/queue/jobs.py):
    >>> from pdf_generator_sector_uf_report import generate_sector_uf_report
    >>> bio = generate_sector_uf_report(db=supabase_client, entity_key="limpeza:SP")
    >>> pdf_bytes = bio.getvalue()

entity_key format: "sector_id:UF" — e.g. "limpeza:SP", "construcao:RJ".
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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
# Brand colors — kept in sync with pdf_generator_intel_report.py
# ---------------------------------------------------------------------------
BRAND_DARK_BLUE = colors.HexColor("#1B3A5C")
BRAND_MEDIUM_BLUE = colors.HexColor("#2C5F8A")
BRAND_LIGHT_BLUE = colors.HexColor("#E8F0FE")
BRAND_ACCENT = colors.HexColor("#3B82F6")

VIABILITY_GREEN = colors.HexColor("#16A34A")
VIABILITY_YELLOW = colors.HexColor("#CA8A04")
VIABILITY_GRAY = colors.HexColor("#64748B")

TABLE_HEADER_BG = BRAND_DARK_BLUE
TABLE_ALT_ROW = colors.HexColor("#F8FAFC")
TABLE_BORDER = colors.HexColor("#CBD5E1")
METRIC_BOX_BG = colors.HexColor("#EFF6FF")  # blue-50

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

FOOTER_TEXT = "SmartLic Intelligence — smartlic.tech | Dados: PNCP | Atualizado em {data}"

ESFERA_LABELS = {
    "F": "Federal",
    "E": "Estadual",
    "M": "Municipal",
    "D": "Distrital",
}

# ---------------------------------------------------------------------------
# Helpers (duplicated from pdf_generator_intel_report to keep modules independent)
# ---------------------------------------------------------------------------


def _sanitize(value: Any) -> str:
    if value is None:
        return ""
    return ILLEGAL_CHARACTERS_RE.sub(" ", html.escape(str(value)))


def _fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return "—"
    if v == 0:
        return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "—"
    try:
        parts = str(date_str).split("T")[0].split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        return _sanitize(date_str)


def _trunc(text: Any, max_chars: int = 80) -> str:
    s = _sanitize(text)
    if len(s) <= max_chars:
        return s
    return s[:max_chars - 1] + "…"


def _build_styles() -> dict:
    base = getSampleStyleSheet()

    def _ps(name: str, **kw) -> ParagraphStyle:
        parent = kw.pop("parent", base["Normal"])
        return ParagraphStyle(name, parent=parent, **kw)

    return {
        "title": _ps(
            "SURTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "subtitle": _ps(
            "SURSubtitle",
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=BRAND_MEDIUM_BLUE,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "section": _ps(
            "SURSection",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=BRAND_DARK_BLUE,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        ),
        "body": _ps(
            "SURBody",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
            spaceAfter=2 * mm,
        ),
        "caption": _ps(
            "SURCaption",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "label": _ps(
            "SURLabel",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=BRAND_DARK_BLUE,
        ),
        "metric_val": _ps(
            "SURMetricVal",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
        ),
        "metric_label": _ps(
            "SURMetricLabel",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "warning": _ps(
            "SURWarning",
            fontName="Helvetica-Oblique",
            fontSize=7,
            leading=9,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "tbl_header": _ps(
            "SURTblHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
        ),
        "tbl_cell": _ps(
            "SURTblCell",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
        ),
        "tbl_cell_num": _ps(
            "SURTblCellNum",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
            alignment=TA_RIGHT,
        ),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_cover(data: dict, styles: dict) -> list:
    """Page 1 — Cover."""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    sector_label = _sanitize(data.get("sector_label") or data.get("sector") or "Setor")
    uf = _sanitize(data.get("uf") or "")
    window_months = data.get("window_months") or 24

    story = []

    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        '<font color="#1B3A5C"><b>SmartLic</b></font>'
        '<font color="#3B82F6"> Intelligence</font>',
        ParagraphStyle(
            "CoverLogo",
            parent=styles["title"],
            fontSize=18,
            spaceBefore=0,
            spaceAfter=2 * mm,
        ),
    ))
    story.append(HRFlowable(
        width=CONTENT_WIDTH,
        thickness=2,
        color=BRAND_ACCENT,
        spaceAfter=6 * mm,
    ))

    story.append(Paragraph("Panorama Setorial", styles["title"]))
    story.append(Spacer(1, 4 * mm))

    if uf:
        story.append(Paragraph(f"{sector_label} — {uf}", styles["subtitle"]))
    else:
        story.append(Paragraph(sector_label, styles["subtitle"]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Janela de análise: {window_months} meses", styles["caption"]))
    story.append(Paragraph(f"Data de geração: {now_str}", styles["caption"]))

    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(
        width=CONTENT_WIDTH,
        thickness=0.5,
        color=TABLE_BORDER,
        spaceAfter=4 * mm,
    ))
    story.append(Paragraph(
        "Análise baseada em dados do PNCP — Contratos registrados por órgãos públicos",
        styles["warning"],
    ))

    story.append(PageBreak())
    return story


def _build_executive_summary(data: dict, styles: dict) -> list:
    """Page 2 — Sumário Executivo com métricas principais."""
    story = []
    story.append(Paragraph("Sumário Executivo", styles["section"]))

    total_c = data.get("total_contracts") or 0
    valor_t = data.get("total_value") or 0.0
    avg_t = data.get("avg_ticket") or 0.0
    median_t = data.get("median_ticket") or 0.0
    p90_t = data.get("p90_ticket") or 0.0
    sector_label = _sanitize(data.get("sector_label") or data.get("sector") or "")
    uf = _sanitize(data.get("uf") or "")
    window_months = data.get("window_months") or 24

    narrative = (
        f"O mercado de {sector_label} no estado de {uf} registrou "
        f"{_fmt_int(total_c)} contrato(s) nos últimos {window_months} meses, "
        f"totalizando {_fmt_currency(valor_t)} em valor contratado. "
        f"O ticket médio foi de {_fmt_currency(avg_t)}, "
        f"com mediana de {_fmt_currency(median_t)} e P90 de {_fmt_currency(p90_t)}. "
        "Veja as seções seguintes para detalhes sobre fornecedores, "
        "órgãos compradores e evolução temporal."
    )
    story.append(Paragraph(narrative, styles["body"]))
    story.append(Spacer(1, 4 * mm))

    metrics = [
        (_fmt_int(total_c), "Total de Contratos"),
        (_fmt_currency(valor_t), "Valor Total"),
        (_fmt_currency(avg_t), "Ticket Médio"),
        (_fmt_currency(median_t), "Mediana"),
    ]

    col_w = CONTENT_WIDTH / 4
    metric_rows = [[
        Table(
            [[Paragraph(v, styles["metric_val"])], [Paragraph(lbl, styles["metric_label"])]],
            colWidths=[col_w - 4 * mm],
        )
        for v, lbl in metrics
    ]]
    metric_tbl = Table(metric_rows, colWidths=[col_w] * 4)
    metric_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), METRIC_BOX_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(metric_tbl)

    # P90 note
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"P90 (percentil 90 de ticket): {_fmt_currency(p90_t)}",
        styles["caption"],
    ))
    story.append(PageBreak())
    return story


def _table_style_standard(num_rows: int) -> TableStyle:
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, TABLE_BORDER),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, num_rows):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))
    return TableStyle(commands)


def _build_top_fornecedores(data: dict, styles: dict) -> list:
    """Page 3 — Top 20 Fornecedores por Valor."""
    story = []
    story.append(Paragraph("Top 20 Fornecedores por Valor Contratado", styles["section"]))

    fornecedores = data.get("top_fornecedores") or []
    if not fornecedores:
        story.append(Paragraph("Nenhum dado disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    total_value = sum(float(f.get("valor_total") or 0) for f in fornecedores)

    header = [
        Paragraph("#", styles["tbl_header"]),
        Paragraph("Fornecedor", styles["tbl_header"]),
        Paragraph("CNPJ", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
        Paragraph("% Share", styles["tbl_header"]),
    ]

    rows = [header]
    for rank, f in enumerate(fornecedores[:20], start=1):
        vt = float(f.get("valor_total") or 0)
        pct = (vt / total_value * 100) if total_value > 0 else 0.0
        rows.append([
            Paragraph(str(rank), styles["tbl_cell_num"]),
            Paragraph(_trunc(f.get("nome_fornecedor") or "—", 40), styles["tbl_cell"]),
            Paragraph(_sanitize(f.get("ni_fornecedor") or "—"), styles["tbl_cell"]),
            Paragraph(_fmt_int(f.get("count") or 0), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(vt), styles["tbl_cell_num"]),
            Paragraph(_fmt_pct(pct), styles["tbl_cell_num"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.05,
        CONTENT_WIDTH * 0.33,
        CONTENT_WIDTH * 0.16,
        CONTENT_WIDTH * 0.13,
        CONTENT_WIDTH * 0.20,
        CONTENT_WIDTH * 0.13,
    ]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _build_top_orgaos(data: dict, styles: dict) -> list:
    """Page 4 — Top 10 Órgãos Compradores."""
    story = []
    story.append(Paragraph("Top 10 Órgãos Compradores", styles["section"]))

    orgaos = data.get("top_orgaos") or []
    if not orgaos:
        story.append(Paragraph("Nenhum dado disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    total_val = sum(float(o.get("valor_total") or 0) for o in orgaos)

    header = [
        Paragraph("Órgão", styles["tbl_header"]),
        Paragraph("CNPJ Órgão", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
        Paragraph("% Share", styles["tbl_header"]),
    ]

    rows = [header]
    for o in orgaos[:10]:
        vt = float(o.get("valor_total") or 0)
        pct = (vt / total_val * 100) if total_val > 0 else 0.0
        rows.append([
            Paragraph(_trunc(o.get("orgao_nome") or "—", 50), styles["tbl_cell"]),
            Paragraph(_sanitize(o.get("orgao_cnpj") or "—"), styles["tbl_cell"]),
            Paragraph(_fmt_int(o.get("count") or 0), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(vt), styles["tbl_cell_num"]),
            Paragraph(_fmt_pct(pct), styles["tbl_cell_num"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.38,
        CONTENT_WIDTH * 0.18,
        CONTENT_WIDTH * 0.13,
        CONTENT_WIDTH * 0.18,
        CONTENT_WIDTH * 0.13,
    ]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _build_temporal_evolution(data: dict, styles: dict) -> list:
    """Page 5 — Evolução Temporal Mensal."""
    story = []
    story.append(Paragraph("Evolução Temporal", styles["section"]))

    temporal = data.get("serie_temporal") or []
    if not temporal:
        story.append(Paragraph("Nenhum dado temporal disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    header = [
        Paragraph("Mês/Ano", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
    ]

    rows = [header]
    for entry in temporal:
        mes = _sanitize(entry.get("mes") or "—")
        n = entry.get("count") or 0
        v = float(entry.get("valor_total") or 0)
        rows.append([
            Paragraph(mes, styles["tbl_cell"]),
            Paragraph(_fmt_int(n), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(v), styles["tbl_cell_num"]),
        ])

    col_widths = [CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.40]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Nota: meses sem contratos registrados apresentam valor zero — série completa para análise de sazonalidade.",
        styles["caption"],
    ))
    story.append(PageBreak())
    return story


def _build_top_objetos(data: dict, styles: dict) -> list:
    """Page 6 — Top 10 Objetos Contratados."""
    story = []
    story.append(Paragraph("Top 10 Objetos Contratados", styles["section"]))

    objetos = data.get("top_objetos") or []
    if not objetos:
        story.append(Paragraph("Nenhum dado disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    header = [
        Paragraph("Objeto (descrição)", styles["tbl_header"]),
        Paragraph("Frequência", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
    ]

    rows = [header]
    for o in objetos[:10]:
        n = o.get("count") or 0
        vt = float(o.get("valor_total") or 0)
        rows.append([
            Paragraph(_trunc(o.get("objeto_resumo") or "—", 70), styles["tbl_cell"]),
            Paragraph(_fmt_int(n), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(vt), styles["tbl_cell_num"]),
        ])

    col_widths = [CONTENT_WIDTH * 0.60, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.22]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _build_esfera_distribution(data: dict, styles: dict) -> list:
    """Page 7 — Distribuição por Esfera."""
    story = []
    story.append(Paragraph("Distribuição por Esfera", styles["section"]))

    esfera_items = data.get("distribuicao_esfera") or []
    if not esfera_items:
        story.append(Paragraph("Nenhum dado disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    total_val = sum(float(e.get("valor_total") or 0) for e in esfera_items)

    header = [
        Paragraph("Esfera", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
        Paragraph("% do Total", styles["tbl_header"]),
    ]
    rows = [header]
    for e in esfera_items:
        code = str(e.get("esfera") or "?").upper()
        label = ESFERA_LABELS.get(code, _sanitize(code))
        cnt = e.get("count") or 0
        vt = float(e.get("valor_total") or 0)
        pct = (vt / total_val * 100) if total_val > 0 else 0.0
        rows.append([
            Paragraph(label, styles["tbl_cell"]),
            Paragraph(_fmt_int(cnt), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(vt), styles["tbl_cell_num"]),
            Paragraph(_fmt_pct(pct), styles["tbl_cell_num"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.25,
        CONTENT_WIDTH * 0.20,
        CONTENT_WIDTH * 0.30,
        CONTENT_WIDTH * 0.25,
    ]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    story.append(PageBreak())
    return story


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def _fetch_rpc_data(db: Any, sector_id: str, keywords: list[str], uf: str) -> dict:
    """Call sector_uf_intel RPC and return the JSONB payload as a dict."""
    result = db.rpc(
        "sector_uf_intel",
        {
            "p_sector": sector_id,
            "p_keywords": keywords,
            "p_uf": uf,
            "p_window_months": 24,
        },
    ).execute()

    payload = getattr(result, "data", None)
    if not payload:
        raise ValueError(
            f"sector_uf_intel returned no data for sector={sector_id!r} uf={uf!r}"
        )

    # PostgREST wraps RPC results in a list when returning a scalar JSONB
    if isinstance(payload, list) and len(payload) == 1:
        item = payload[0]
        # If wrapped in {"sector_uf_intel": {...}}
        if isinstance(item, dict) and "sector_uf_intel" in item:
            return item["sector_uf_intel"]
        return item

    if isinstance(payload, dict):
        return payload

    raise ValueError(
        f"sector_uf_intel returned unexpected shape: {type(payload).__name__}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_sector_uf_report(db: Any, entity_key: str) -> BytesIO:
    """Generate an A4 PDF for the INTEL-REPORT-002 Panorama Setorial × UF.

    Args:
        db: Supabase client (service role) — used to call the sector_uf_intel RPC.
        entity_key: Format "sector_id:UF" — e.g. "limpeza:SP", "construcao:RJ".
            sector_id must match a key in backend/sectors_data.yaml.

    Returns:
        BytesIO positioned at start containing the PDF.

    Raises:
        ValueError: If entity_key format is invalid, sector not found, or RPC returns no data.
    """
    # --- Parse entity_key ---
    if ":" not in entity_key:
        raise ValueError(
            f"Invalid entity_key {entity_key!r}. Expected format 'sector_id:UF'"
        )
    sector_id, uf = entity_key.split(":", 1)
    sector_id = sector_id.strip().lower()
    uf = uf.strip().upper()

    if not sector_id or not uf or len(uf) != 2:
        raise ValueError(
            f"Invalid entity_key {entity_key!r}. "
            "sector_id must be non-empty and UF must be 2 letters."
        )

    # --- Resolve keywords from sectors_data.yaml ---
    try:
        from sectors import get_sector  # noqa: PLC0415
        sector_config = get_sector(sector_id)
        keywords = list(sector_config.keywords)
        sector_label = sector_config.name if hasattr(sector_config, "name") else sector_id.capitalize()
    except Exception as exc:
        raise ValueError(
            f"Cannot resolve keywords for sector {sector_id!r}: {exc}"
        ) from exc

    logger.info(
        "sector_uf_intel: sector=%s uf=%s keywords_count=%d",
        sector_id, uf, len(keywords),
    )

    # --- Fetch RPC data ---
    data = _fetch_rpc_data(db=db, sector_id=sector_id, keywords=keywords, uf=uf)

    # --- Enrich with display fields ---
    data["sector_label"] = sector_label
    data.setdefault("sector", sector_id)
    data.setdefault("uf", uf)

    # --- Build PDF ---
    buf = BytesIO()
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=2.5 * cm,
        title=f"SmartLic Intelligence — Panorama {sector_label} × {uf}",
        author="SmartLic",
    )

    styles = _build_styles()

    story: list = []
    story.extend(_build_cover(data, styles))
    story.extend(_build_executive_summary(data, styles))
    story.extend(_build_top_fornecedores(data, styles))
    story.extend(_build_top_orgaos(data, styles))
    story.extend(_build_temporal_evolution(data, styles))
    story.extend(_build_top_objetos(data, styles))
    story.extend(_build_esfera_distribution(data, styles))

    def _footer(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(VIABILITY_GRAY)
        footer = FOOTER_TEXT.format(data=now_str)
        canvas.drawCentredString(PAGE_WIDTH / 2, 1.2 * cm, footer)
        canvas.drawRightString(
            PAGE_WIDTH - MARGIN,
            1.2 * cm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
