"""COPY-COP-006 (#1127): Lead magnet PDF delivery endpoint.

Stub PDF generation for lead magnets. The actual LLM-generated content
will replace the placeholder text in a future story. For now, returns
a minimal PDF with the structure and a CTA to start a free trial.

Endpoints:
    GET /v1/lead-magnet/{type} — returns a placeholder PDF for the
      given lead magnet type (guia-pratico | checklist-5-sinais).
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet

from templates.emails.base import SMARTLIC_GREEN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lead-magnet", tags=["lead-magnet"])

LeadMagnetType = Literal["guia-pratico", "checklist-5-sinais"]

LEAD_MAGNET_META: dict[str, dict[str, str]] = {
    "guia-pratico": {
        "title": "Guia Prático: Como Avaliar Editais com Inteligência Artificial",
        "subtitle": "Um guia passo a passo para empresas B2G",
        "sections": (
            "1. Por que usar IA na análise de editais\n\n"
            "Milhares de licitações são publicadas todos os dias nos portais oficiais. "
            "Sem um filtro inteligente, sua equipe perde horas analisando manualmente "
            "editais que não têm relação com seu negócio.\n\n"
            "2. Os 4 fatores de viabilidade\n\n"
            "Modalidade (30%), Prazo (25%), Valor Estimado (25%) e Geografia (20%) "
            "são os pilares para decidir se vale a pena participar de um edital.\n\n"
            "3. Como o SmartLic automatiza esse processo\n\n"
            "O SmartLic busca nas 3 principais fontes oficiais (PNCP, PCP, ComprasGov), "
            "classifica por setor com IA e calcula o score de viabilidade automaticamente.\n\n"
            "4. Próximos passos\n\n"
            "Comece seu teste gratuito de 14 dias no SmartLic e descubra oportunidades "
            "que sua concorrência já está vendo."
        ),
    },
    "checklist-5-sinais": {
        "title": "Checklist: 5 Sinais de que Você Está Perdendo Oportunidades em Licitações",
        "subtitle": "Diagnóstico rápido para empresas B2G",
        "sections": (
            "Sinal 1: Você só consulta um portal oficial\n\n"
            "O PNCP é apenas uma das fontes. PCP v2 e ComprasGov v3 têm dados "
            "complementares. O SmartLic consolida tudo em uma busca.\n\n"
            "Sinal 2: Sua equipe gasta mais de 10h/semana filtrando editais\n\n"
            "Com classificação por IA, o filtro que leva horas é feito em segundos.\n\n"
            "Sinal 3: Você já perdeu um prazo por não ter visto o edital a tempo\n\n"
            "Alertas automáticos por email evitam que oportunidades passem despercebidas.\n\n"
            "Sinal 4: Você participa de editais sem saber se tem chance real\n\n"
            "O score de viabilidade do SmartLic considera 4 fatores objetivos "
            "para priorizar as melhores oportunidades.\n\n"
            "Sinal 5: Você não tem dados para decidir entre editais concorrentes\n\n"
            "Comparação lado a lado com análise de risco e recomendação automatizada."
        ),
    },
}


def _build_pdf_bytes(magnet_type: str) -> bytes:
    """Build a minimal placeholder PDF for the given lead magnet type."""
    meta = LEAD_MAGNET_META.get(magnet_type)
    if not meta:
        raise HTTPException(status_code=404, detail="Tipo de lead magnet não encontrado")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading1"]
    body_style = styles["Normal"]

    story = [
        Paragraph(meta["title"], title_style),
        Spacer(1, 0.5 * cm),
        Paragraph(meta["subtitle"], heading_style),
        Spacer(1, 0.5 * cm),
    ]

    # Add sections as plain paragraphs
    for paragraph_text in meta["sections"].split("\n\n"):
        if paragraph_text.strip():
            story.append(Paragraph(paragraph_text.replace("\n", "<br/>"), body_style))
            story.append(Spacer(1, 0.3 * cm))

    # Trial CTA footer
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            f'<para align="center"><strong>Teste o SmartLic grátis por 14 dias — '
            f'<a href="https://smartlic.tech/signup?source=lead-magnet-{magnet_type}" '
            f'color="{SMARTLIC_GREEN}">smartlic.tech/signup</a></strong></para>',
            body_style,
        )
    )

    doc.build(story)
    return buf.getvalue()


@router.get("/{magnet_type}", response_model=None, responses={200: {"content": {"application/pdf": {}}}})
async def get_lead_magnet(magnet_type: LeadMagnetType):
    """Return a placeholder PDF for the requested lead magnet type.

    This is a minimal/stub implementation — the real LLM-generated content
    will replace the placeholder text in a future story.
    """
    if magnet_type not in LEAD_MAGNET_META:
        raise HTTPException(
            status_code=404,
            detail=f"Lead magnet type '{magnet_type}' not found. "
                   f"Available: {', '.join(LEAD_MAGNET_META.keys())}",
        )

    try:
        pdf_bytes = await _build_pdf_bytes_async(magnet_type)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to generate lead magnet PDF")
        raise HTTPException(status_code=500, detail="Erro ao gerar PDF")

    meta = LEAD_MAGNET_META[magnet_type]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{magnet_type}.pdf"',
            "X-Lead-Magnet-Title": meta["title"],
        },
    )


async def _build_pdf_bytes_async(magnet_type: str) -> bytes:
    """Thread-safe wrapper for PDF generation."""
    import asyncio
    return await asyncio.to_thread(_build_pdf_bytes, magnet_type)
