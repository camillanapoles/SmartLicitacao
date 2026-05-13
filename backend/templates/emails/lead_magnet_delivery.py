"""Lead magnet delivery email — sent after lead capture with PDF attachment.

Transactional email (no unsubscribe). Delivers the datalake-powered insights PDF
and a soft CTA to start a trial.
"""

from templates.emails.base import email_base, SMARTLIC_GREEN, FRONTEND_URL


def render_lead_magnet_email(
    setor: str | None = None,
    sector_name: str | None = None,
) -> tuple[str, str]:
    """Render the lead magnet delivery HTML email.

    Args:
        setor: Sector key (for CTA personalization).
        sector_name: Display name of the sector.

    Returns:
        (subject, html) tuple.
    """
    if sector_name:
        subject = f"Seu panorama de licitações — {sector_name} está pronto"
    else:
        subject = "Seu panorama de licitações públicas está pronto"

    busca_url = f"{FRONTEND_URL}/buscar"
    if setor:
        busca_url += f"?setor={setor}"

    trial_url = f"{FRONTEND_URL}/cadastro?utm_source=lead_magnet&utm_medium=email"
    if setor:
        trial_url += f"&setor={setor}"

    sector_line = ""
    if sector_name:
        sector_line = (
            f"<p style=\"color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;\">"
            f"Incluímos uma <strong>análise exclusiva do setor de {sector_name}</strong> "
            f"(página 3 do PDF) — dados que só o SmartLic consegue gerar porque temos "
            f"o maior datalake de licitações do Brasil."
            f"</p>"
        )

    body = f"""
    <h1 style="color: #333; font-size: 24px; margin: 0 0 16px;">
      Seu guia de oportunidades B2G chegou
    </h1>

    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      O PDF em anexo contém um <strong>panorama completo do mercado de licitações
      públicas</strong> — dados reais do PNCP processados pelo datalake SmartLic.
    </p>

    <h2 style="color: #333; font-size: 18px; margin: 32px 0 12px;">
      O que você vai encontrar no PDF
    </h2>
    <ul style="color: #555; font-size: 15px; line-height: 1.7; padding-left: 20px; margin: 0 0 24px;">
      <li><strong>Panorama nacional:</strong> volume de licitações por setor e
      modalidade nos últimos 90 dias — com valores reais do PNCP.</li>
      <li><strong>Mapa de oportunidades:</strong> top 10 estados e maiores
      órgãos compradores do Brasil.</li>
      <li><strong>Valores de mercado:</strong> ticket médio por modalidade
      para precificar suas propostas com inteligência.</li>
    </ul>

    {sector_line}

    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 24px 0 16px;">
      O SmartLic automatiza essa análise para o seu setor e UF — com alertas
      diários de novos editais, análise de viabilidade e pipeline de oportunidades.
    </p>

    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 16px auto 8px;">
      <tr>
        <td align="center" style="background: {SMARTLIC_GREEN}; border-radius: 8px;">
          <a href="{trial_url}"
             style="display: inline-block; padding: 14px 32px; color: #ffffff;
                    text-decoration: none; font-weight: 600; font-size: 16px;">
            Testar SmartLic grátis por 14 dias
          </a>
        </td>
      </tr>
    </table>

    <p style="color: #888; font-size: 13px; text-align: center; margin: 16px 0 0;">
      Ou <a href="{busca_url}" style="color: {SMARTLIC_GREEN};">veja as licitações
      abertas agora</a> sem cadastro.
    </p>

    <p style="color: #888; font-size: 13px; text-align: center; margin: 24px 0 0;">
      Este é um email transacional enviado porque você solicitou o guia de
      oportunidades B2G no site smartlic.tech.<br>
      CONFENGE Avaliações e Inteligência Artificial LTDA
    </p>
    """
    return subject, email_base(
        title=subject,
        body_html=body,
        is_transactional=True,
    )
