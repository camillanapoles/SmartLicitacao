"""
Internal helpers for `templates.emails.trial` email templates.

Extracted from `trial.py` (EMAIL-TRIAL-006 #1005) to keep that module under the
godmodule LOC threshold without changing render output. All functions here are
pure HTML fragment builders consumed by the public `render_trial_*` functions.

Re-exported via `templates.emails.trial` for backwards-compatible imports.
"""

from templates.emails.base import SMARTLIC_GREEN, FRONTEND_URL


# ============================================================================
# EMAIL-TRIAL-006: Founders cross-sell helpers
# ============================================================================

# R$397/mes × 12 = R$4.764 vs R$997 vitalício = economia R$3.767 no primeiro ano
FOUNDERS_PRICE_BRL = "R$ 997"
FOUNDERS_PRICE_BRL_NUMERIC = 997
PRO_MONTHLY_BRL = "R$ 397"
PRO_ANNUAL_TOTAL_BRL = "R$ 4.764"


def _founders_cross_sell_block(seats_remaining: int | None = None) -> str:
    """Render the Plano Fundadores cross-sell block.

    Used on Day 7/10/13 trial emails. Falls back to generic copy when
    ``seats_remaining`` is None (counter API unavailable — issue #1002).
    """
    if seats_remaining is not None and seats_remaining > 0:
        scarcity_line = (
            f"<strong>{seats_remaining} vagas vitalícias restantes</strong> · "
            f"oferta encerra em 30/06/2026"
        )
    else:
        scarcity_line = (
            "<strong>Vagas vitalícias limitadas</strong> · oferta encerra em 30/06/2026"
        )

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin: 20px 0 24px;">
      <tr>
        <td style="background-color: #fff8e1; border: 2px solid #f59e0b; border-radius: 12px; padding: 20px;">
          <p style="color: #92400e; font-size: 12px; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700;">
            Plano Fundadores · vitalício
          </p>
          <p style="color: #78350f; font-size: 18px; font-weight: 700; margin: 0 0 8px; line-height: 1.3;">
            Pague {FOUNDERS_PRICE_BRL} uma vez. Use pra sempre.
          </p>
          <p style="color: #555; font-size: 14px; margin: 0 0 12px; line-height: 1.5;">
            Em vez de {PRO_MONTHLY_BRL}/mês ({PRO_ANNUAL_TOTAL_BRL} no primeiro ano), você
            paga {FOUNDERS_PRICE_BRL} <em>uma única vez</em> e mantém o SmartLic Pro vitalício.
          </p>
          <p style="color: #92400e; font-size: 13px; margin: 0 0 14px;">
            {scarcity_line}
          </p>
          <a href="{FRONTEND_URL}/fundadores"
             style="display: inline-block; padding: 12px 24px; background-color: #f59e0b; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 15px;">
            Ver Plano Fundadores →
          </a>
        </td>
      </tr>
    </table>"""


def _founders_pricing_table_html() -> str:
    """Day 7 specific: visual table comparing Pro mensal vs Vitalício.

    Belgray-style "show me the math" — concrete numbers beat abstract value props.
    """
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin: 20px 0 24px; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
      <tr>
        <td colspan="3" style="background-color: #f9fafb; padding: 12px 16px; border-bottom: 1px solid #e5e7eb;">
          <p style="color: #374151; font-size: 14px; font-weight: 600; margin: 0;">
            A conta nua e crua:
          </p>
        </td>
      </tr>
      <tr style="background-color: #ffffff;">
        <td style="padding: 12px 16px; color: #6b7280; font-size: 14px; border-bottom: 1px solid #f3f4f6;">
          SmartLic Pro mensal
        </td>
        <td style="padding: 12px 16px; color: #374151; font-size: 14px; text-align: right; border-bottom: 1px solid #f3f4f6;">
          {PRO_MONTHLY_BRL}/mês
        </td>
        <td style="padding: 12px 16px; color: #ef4444; font-size: 14px; font-weight: 600; text-align: right; border-bottom: 1px solid #f3f4f6;">
          {PRO_ANNUAL_TOTAL_BRL}/ano
        </td>
      </tr>
      <tr style="background-color: #fef3c7;">
        <td style="padding: 14px 16px; color: #78350f; font-size: 14px; font-weight: 700;">
          Plano Fundadores
        </td>
        <td style="padding: 14px 16px; color: #78350f; font-size: 14px; font-weight: 700; text-align: right;">
          {FOUNDERS_PRICE_BRL} uma vez
        </td>
        <td style="padding: 14px 16px; color: {SMARTLIC_GREEN}; font-size: 14px; font-weight: 700; text-align: right;">
          economiza R$ 3.767
        </td>
      </tr>
    </table>"""


def _founder_signature_html() -> str:
    """Founder-led signature — Belgray-style personal close."""
    return """
    <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 32px 0 4px;">
      No que eu puder ajudar, é só responder esse email.
    </p>
    <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 4px;">
      Tiago<br/>
      <span style="color: #888; font-size: 13px;">fundador, SmartLic</span>
    </p>"""


def _format_brl(value: float) -> str:
    """Format a float as Brazilian Real currency string."""
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"R$ {value / 1_000:.0f}k"
    return f"R$ {value:,.0f}".replace(",", ".")


def _stats_block(stats: dict, show_pipeline: bool = False) -> str:
    """AC8: Render a stats summary block for email templates."""
    searches = stats.get("searches_count", 0)
    opps = stats.get("opportunities_found", 0)
    value = stats.get("total_value_estimated", 0.0)
    pipeline = stats.get("pipeline_items_count", 0)

    rows = f"""
    <tr>
      <td style="padding: 8px 16px; color: #555; font-size: 15px; border-bottom: 1px solid #eee;">
        Análises realizadas
      </td>
      <td style="padding: 8px 16px; color: #333; font-size: 15px; font-weight: 600; text-align: right; border-bottom: 1px solid #eee;">
        {searches}
      </td>
    </tr>
    <tr>
      <td style="padding: 8px 16px; color: #555; font-size: 15px; border-bottom: 1px solid #eee;">
        Oportunidades encontradas
      </td>
      <td style="padding: 8px 16px; color: #333; font-size: 15px; font-weight: 600; text-align: right; border-bottom: 1px solid #eee;">
        {opps}
      </td>
    </tr>
    <tr>
      <td style="padding: 8px 16px; color: #555; font-size: 15px; border-bottom: 1px solid #eee;">
        Valor total estimado
      </td>
      <td style="padding: 8px 16px; color: {SMARTLIC_GREEN}; font-size: 15px; font-weight: 600; text-align: right; border-bottom: 1px solid #eee;">
        {_format_brl(value)}
      </td>
    </tr>"""

    if show_pipeline:
        rows += f"""
    <tr>
      <td style="padding: 8px 16px; color: #555; font-size: 15px;">
        Itens no pipeline
      </td>
      <td style="padding: 8px 16px; color: #333; font-size: 15px; font-weight: 600; text-align: right;">
        {pipeline}
      </td>
    </tr>"""

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color: #f8f9fa; border-radius: 8px; margin: 16px 0 24px; overflow: hidden;">
      {rows}
    </table>"""


def _unsubscribe_block(unsubscribe_url: str) -> str:
    """Render unsubscribe link block (AC2: RFC 8058 one-click)."""
    if not unsubscribe_url:
        return ""
    return f"""
    <p style="color: #999; font-size: 12px; text-align: center; margin: 24px 0 0;">
      <a href="{unsubscribe_url}" style="color: #999; text-decoration: underline;">
        Não desejo receber emails sobre o trial
      </a>
    </p>"""


def _preheader(text: str) -> str:
    """AC2: Hidden preheader text for email clients (Gmail, Apple Mail)."""
    return (
        f'<div style="display:none;font-size:1px;color:#f4f4f4;'
        f'line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">'
        f'{text}</div>'
    )
