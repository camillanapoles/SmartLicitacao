"""Post-purchase email templates — CONV-011b-2.

Three-step sequence templates:
  - delivery (0h):   Transactional — product delivery with download link / inline content
  - followup (48h):  Soft upsell — product usage tips + CTA for trial/upgrade
  - reengagement (7d): Reengagement — value reminder + last-chance offer

Each step adapts per product_sku via delivery_config.type:
  - "pdf"  → download link CTA
  - "csv"  → download link CTA
  - "email" → inline content (no download)
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote_plus

from templates.emails.base import FRONTEND_URL, SMARTLIC_DARK, SMARTLIC_GREEN, email_base


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _price_display(price_brl: int) -> str:
    """Format price in BRL cents to display string."""
    reais = price_brl / 100
    if reais == int(reais):
        return f"R${int(reais):,}".replace(",", ".")
    return f"R${reais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _download_button(download_url: str, label: str = "Baixar agora") -> str:
    """Green CTA button for PDF/CSV delivery."""
    return f"""
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;">
      <tr>
        <td align="center" style="background: {SMARTLIC_GREEN}; border-radius: 8px;">
          <a href="{escape(download_url, quote=True)}"
             style="display: inline-block; padding: 14px 32px; color: #ffffff;
                    text-decoration: none; font-weight: 600; font-size: 16px;">
            {escape(label)}
          </a>
        </td>
      </tr>
    </table>"""


def _upsell_box(
    upsell_product_name: str | None = None,
    upsell_product_price: int | None = None,
    upsell_url: str | None = None,
) -> str:
    """Soft upsell callout box shown in followup and reengagement emails."""
    if not upsell_product_name:
        return ""

    price_str = f" por {_price_display(upsell_product_price)}" if upsell_product_price else ""
    cta = ""
    if upsell_url:
        cta = f"""
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 12px auto 0;">
          <tr>
            <td align="center" style="background: {SMARTLIC_DARK}; border-radius: 8px;">
              <a href="{escape(upsell_url, quote=True)}"
                 style="display: inline-block; padding: 10px 24px; color: #ffffff;
                        text-decoration: none; font-weight: 600; font-size: 14px;">
                Ver {escape(upsell_product_name)}
              </a>
            </td>
          </tr>
        </table>"""

    return f"""
    <div style="border: 1px solid {SMARTLIC_GREEN}; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <p style="color: #333; font-size: 15px; line-height: 1.6; margin: 0 0 4px;">
        <strong>💡 Quer ir além?</strong>
      </p>
      <p style="color: #555; font-size: 14px; line-height: 1.6; margin: 0;">
        O <strong>{escape(upsell_product_name)}</strong>{price_str} complementa
        sua análise com dados que empresas concorrentes não têm.
      </p>
      {cta}
    </div>"""


def _expiry_notice(days: int = 30) -> str:
    """Standard link expiry notice."""
    return f"""
    <p style="color: #777; font-size: 14px; line-height: 1.6; margin: 0 0 24px;">
      Este link expira em {days} dias. Guarde uma cópia local se quiser consultar
      depois desse prazo.
    </p>"""


def _buscar_cta(setor: str | None = None) -> str:
    """Soft CTA to the search page."""
    url = f"{FRONTEND_URL}/buscar"
    if setor:
        url += f"?setor={quote_plus(setor)}"
    return f"""
    <p style="color: #888; font-size: 13px; text-align: center; margin: 24px 0 0;">
      Ou <a href="{url}" style="color: {SMARTLIC_GREEN};">veja as licitações abertas agora</a>.
    </p>"""


# ---------------------------------------------------------------------------
# Step 1: Delivery (0h) — transactional
# ---------------------------------------------------------------------------


def render_post_purchase_delivery(
    *,
    user_name: str,
    product_name: str,
    product_sku: str,
    delivery_type: str,  # "pdf" | "csv" | "email"
    download_url: str | None = None,
    setor: str | None = None,
) -> tuple[str, str]:
    """Render the delivery step email.

    For PDF/CSV products: green download button + 30-day expiry notice.
    For email products: inline content notification (content delivered separately).

    Args:
        user_name: Recipient display name.
        product_name: Human-readable product name.
        product_sku: Product SKU for tracking.
        delivery_type: One of "pdf", "csv", "email".
        download_url: The signed download URL (None for email-type products).
        setor: Optional sector key for personalized CTA.

    Returns:
        (subject, html) tuple.
    """
    subject = f"Seu {product_name} está pronto 📊"

    if delivery_type in ("pdf", "csv") and download_url:
        delivery_section = f"""
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
          Seu <strong>{escape(product_name)}</strong> foi gerado com sucesso.
          Clique no botão abaixo para fazer o download.
        </p>
        {_download_button(download_url)}
        {_expiry_notice(30)}
        """
    elif delivery_type == "email":
        delivery_section = f"""
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
          Seu <strong>{escape(product_name)}</strong> foi ativado com sucesso.
        </p>
        <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
          Você receberá o conteúdo diretamente no seu email conforme a
          periodicidade contratada. Acompanhe também pelo painel do SmartLic.
        </p>
        """
    else:
        delivery_section = f"""
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
          Seu <strong>{escape(product_name)}</strong> foi processado com sucesso.
        </p>
        <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
          Acesse seu painel do SmartLic para visualizar o conteúdo.
        </p>
        """

    account_url = f"{FRONTEND_URL}/conta"

    body = f"""
    <h1 style="color: #333; font-size: 24px; margin: 0 0 16px;">
      Olá, {escape(user_name)}
    </h1>

    {delivery_section}

    <p style="color: #777; font-size: 14px; line-height: 1.6; margin: 24px 0 0;">
      Sua compra está registrada em
      <a href="{account_url}" style="color: {SMARTLIC_GREEN};">sua conta SmartLic</a>.
    </p>

    {_buscar_cta(setor)}

    <p style="color: #888; font-size: 13px; text-align: center; margin: 24px 0 0;">
      Este é um email transacional enviado porque você comprou o produto
      <strong>{escape(product_name)}</strong> (SKU: {escape(product_sku)}) no SmartLic.<br>
      CONFENGE Avaliações e Inteligência Artificial LTDA
    </p>
    """

    return subject, email_base(title=subject, body_html=body, is_transactional=True)


# ---------------------------------------------------------------------------
# Step 2: Followup (48h) — soft upsell
# ---------------------------------------------------------------------------


def render_post_purchase_followup(
    *,
    user_name: str,
    product_name: str,
    product_sku: str,
    upsell_product_name: str | None = None,
    upsell_product_price: int | None = None,
    upsell_product_url: str | None = None,
    trial_url: str | None = None,
) -> tuple[str, str]:
    """Render the 48h followup email with soft upsell.

    Args:
        user_name: Recipient display name.
        product_name: Name of the product the user purchased.
        product_sku: Product SKU for tracking.
        upsell_product_name: Name of the upsell product (if configured).
        upsell_product_price: Price in BRL cents (if configured).
        upsell_product_url: URL to the upsell product page.
        trial_url: URL to start a SmartLic trial.

    Returns:
        (subject, html) tuple.
    """
    subject = f"Como está seu {product_name}? 💡"

    if trial_url is None:
        trial_url = f"{FRONTEND_URL}/cadastro?utm_source=post_purchase&utm_medium=email&utm_campaign=followup_48h&utm_content={quote_plus(product_sku)}&product_sku={quote_plus(product_sku)}"

    body = f"""
    <h1 style="color: #333; font-size: 24px; margin: 0 0 16px;">
      Olá, {escape(user_name)}
    </h1>

    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Esperamos que seu <strong>{escape(product_name)}</strong> esteja sendo útil.
      Separamos algumas dicas para aproveitar ao máximo:
    </p>

    <ul style="color: #555; font-size: 15px; line-height: 1.7; padding-left: 20px; margin: 0 0 24px;">
      <li>Compare os dados do relatório com sua carteira atual de clientes públicos</li>
      <li>Use os rankings de órgãos para priorizar sua prospecção</li>
      <li>Exporte para Excel e compartilhe com sua equipe comercial</li>
    </ul>

    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      E se você pudesse <strong>automatizar essa análise</strong>? O SmartLic Pro
      monitora editais diariamente e classifica oportunidades por setor, valor e
      probabilidade de vitória — tudo com IA.
    </p>

    {_upsell_box(upsell_product_name, upsell_product_price, upsell_product_url)}

    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;">
      <tr>
        <td align="center" style="background: {SMARTLIC_GREEN}; border-radius: 8px;">
          <a href="{escape(trial_url, quote=True)}"
             style="display: inline-block; padding: 14px 32px; color: #ffffff;
                    text-decoration: none; font-weight: 600; font-size: 16px;">
            Testar SmartLic grátis por 14 dias
          </a>
        </td>
      </tr>
    </table>

    <p style="color: #888; font-size: 13px; text-align: center; margin: 24px 0 0;">
      Este email faz parte da sequência de ativação do produto
      <strong>{escape(product_name)}</strong>.<br>
      CONFENGE Avaliações e Inteligência Artificial LTDA
    </p>
    """

    return subject, email_base(title=subject, body_html=body, is_transactional=False)


# ---------------------------------------------------------------------------
# Step 3: Reengagement (7d) — value reminder + last-chance
# ---------------------------------------------------------------------------


def render_post_purchase_reengagement(
    *,
    user_name: str,
    product_name: str,
    product_sku: str,
    download_url: str | None = None,
    upsell_product_name: str | None = None,
    upsell_product_price: int | None = None,
    upsell_product_url: str | None = None,
    trial_url: str | None = None,
) -> tuple[str, str]:
    """Render the 7-day reengagement email.

    Reminds user of the value they purchased, offers last-chance upsell,
    and re-opens the trial CTA.

    Args:
        user_name: Recipient display name.
        product_name: Name of the product the user purchased.
        product_sku: Product SKU for tracking.
        download_url: The download URL (still valid for 23 days).
        upsell_product_name: Name of the upsell product.
        upsell_product_price: Price in BRL cents.
        upsell_product_url: URL to upsell product page.
        trial_url: URL to start a SmartLic trial.

    Returns:
        (subject, html) tuple.
    """
    subject = f"Seu {product_name} ainda está disponível 🔔"

    if trial_url is None:
        trial_url = f"{FRONTEND_URL}/cadastro?utm_source=post_purchase&utm_medium=email&utm_campaign=reengagement_7d&utm_content={quote_plus(product_sku)}&product_sku={quote_plus(product_sku)}"

    # Download reminder (for PDF/CSV products) or login reminder (for email products)
    if download_url:
        reminder_section = f"""
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
          Seu <strong>{escape(product_name)}</strong> ainda está disponível para
          download — o link expira em 23 dias.
        </p>
        {_download_button(download_url, "Baixar novamente")}
        """
    else:
        reminder_section = f"""
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
          Seu <strong>{escape(product_name)}</strong> continua ativo. Acesse seu
          painel para acompanhar as atualizações.
        </p>
        """

    body = f"""
    <h1 style="color: #333; font-size: 24px; margin: 0 0 16px;">
      Olá, {escape(user_name)}
    </h1>

    {reminder_section}

    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 24px 0 16px;">
      Empresas que usam o SmartLic Pro descobrem <strong>em média 3× mais
      oportunidades</strong> de licitação por mês do que fazendo busca manual.
    </p>

    {_upsell_box(upsell_product_name, upsell_product_price, upsell_product_url)}

    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;">
      <tr>
        <td align="center" style="background: {SMARTLIC_GREEN}; border-radius: 8px;">
          <a href="{escape(trial_url, quote=True)}"
             style="display: inline-block; padding: 14px 32px; color: #ffffff;
                    text-decoration: none; font-weight: 600; font-size: 16px;">
            Começar trial gratuito de 14 dias
          </a>
        </td>
      </tr>
    </table>

    <p style="color: #888; font-size: 13px; text-align: center; margin: 24px 0 0;">
      Esta é a última mensagem desta sequência.<br>
      CONFENGE Avaliações e Inteligência Artificial LTDA
    </p>
    """

    return subject, email_base(title=subject, body_html=body, is_transactional=False)
