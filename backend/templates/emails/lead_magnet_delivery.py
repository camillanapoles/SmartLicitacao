"""COPY-COP-006 (#1127): Lead magnet delivery email template.

Template for sending the requested lead magnet PDF to a prospect.
The actual email is sent by the lead capture flow after the user
submits their email.

Usage:
    >>> from templates.emails.lead_magnet_delivery import render_lead_magnet_delivery
    >>> html = render_lead_magnet_delivery(
    ...     email="user@example.com",
    ...     lead_magnet_title="Guia Prático: Como Avaliar Editais com IA",
    ...     pdf_url="https://smartlic.tech/api/lead-magnet/guia-pratico",
    ... )
"""

from __future__ import annotations

from templates.emails.base import email_base

SMARTLIC_GREEN = "#2E7D32"
FRONTEND_URL = "https://smartlic.tech"


def render_lead_magnet_delivery(
    email: str,
    lead_magnet_title: str,
    pdf_url: str,
) -> str:
    """Render the lead magnet delivery email as HTML.

    Args:
        email: Recipient email address (for personalization).
        lead_magnet_title: Display name of the lead magnet (e.g. "Guia Prático").
        pdf_url: Direct download URL for the PDF.

    Returns:
        Full HTML email string suitable for send_email().
    """
    body_html = f"""
    <p style="font-size: 16px; color: #333; margin-bottom: 16px;">
        Olá!
    </p>
    <p style="font-size: 15px; color: #555; margin-bottom: 16px; line-height: 1.6;">
        Obrigado pelo seu interesse no <strong>{lead_magnet_title}</strong>.
        Preparamos este material para ajudar sua empresa a identificar e
        analisar oportunidades em licitações públicas com mais eficiência.
    </p>
    <p style="text-align: center; margin: 24px 0;">
        <a href="{pdf_url}"
           class="btn"
           style="display: inline-block; padding: 14px 32px;
                  background-color: {SMARTLIC_GREEN}; color: #ffffff !important;
                  text-decoration: none; border-radius: 8px;
                  font-weight: 600; font-size: 16px;">
            Baixar {lead_magnet_title}
        </a>
    </p>
    <p style="font-size: 14px; color: #777; margin-bottom: 16px; line-height: 1.5;">
        <strong>Dica:</strong> Após conferir o material, crie sua conta gratuita
        no SmartLic e comece a receber análises de viabilidade das licitações
        do seu setor em minutos.
    </p>
    <p style="text-align: center; margin: 20px 0;">
        <a href="{FRONTEND_URL}/signup?source=lead-magnet-email&email={email}"
           style="color: {SMARTLIC_GREEN}; font-weight: 600; text-decoration: underline;">
            Quero testar o SmartLic grátis por 14 dias →
        </a>
    </p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
    <p style="font-size: 13px; color: #999; line-height: 1.4;">
        Se você não solicitou este material, ignore este email.
    </p>
    """

    subject = f"Seu material SmartLic: {lead_magnet_title}"
    return email_base(
        title=subject,
        body_html=body_html,
        is_transactional=True,
    )


def render_lead_magnet_subject(lead_magnet_title: str) -> str:
    """Return the email subject line for a lead magnet delivery."""
    return f"Seu material SmartLic: {lead_magnet_title}"
