"""
STORY-321 AC7-AC9: Trial email templates — 6 emails over 14-day trial.

Compressed sequence (replaces STORY-310 8-email sequence):
- Day 0:  Welcome — onboarding CTA ("Fazer primeira busca")
- Day 3:  Engagement — stats de uso, destaques ("Explorar mais setores")
- Day 7:  Paywall alert — paywall ativa amanhã ("Assine antes do limite")
- Day 10: Valor acumulado — social proof R$X ("Não perca esse progresso")
- Day 13: Último dia — escassez ("Assinar agora")
- Day 16: Expirado — reengajamento com cupom 20% off ("Voltar com 20% off")

EMAIL-TRIAL-006 (#1005): Day 3/7/10/13/16 reformulados em tom Belgray friend-text +
cross-sell Plano Fundadores (R$997 vitalício one-time, deadline 2026-06-30) nos
days 7/10/13. Day 0 (welcome) e Day 16 cupom 20% off preservam estrutura existente
mas voz alinhada (founder-led, "Tiago" assina).
"""

from templates.emails.base import email_base, SMARTLIC_GREEN, FRONTEND_URL
from templates.emails._trial_helpers import (
    FOUNDERS_PRICE_BRL,
    FOUNDERS_PRICE_BRL_NUMERIC,
    PRO_MONTHLY_BRL,
    PRO_ANNUAL_TOTAL_BRL,
    _founders_cross_sell_block,
    _founders_pricing_table_html,
    _founder_signature_html,
    _format_brl,
    _stats_block,
    _unsubscribe_block,
    _preheader,
)

__all__ = [
    "FOUNDERS_PRICE_BRL",
    "FOUNDERS_PRICE_BRL_NUMERIC",
    "PRO_MONTHLY_BRL",
    "PRO_ANNUAL_TOTAL_BRL",
    "_founders_cross_sell_block",
    "_founders_pricing_table_html",
    "_founder_signature_html",
    "_format_brl",
    "_stats_block",
    "_unsubscribe_block",
    "_preheader",
]


# ============================================================================
# Email #1 — Day 0: Boas-vindas (AC7)
# ============================================================================

def render_trial_welcome_email(user_name: str, unsubscribe_url: str = "") -> str:
    """STORY-321 AC7: Day 0 — Welcome email with 3 steps.

    Args:
        user_name: User's display name.
        unsubscribe_url: URL for one-click unsubscribe.
    """
    body = f"""
    {_preheader("Seu trial de 14 dias começou. Faça sua primeira análise agora.")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
      Bem-vindo ao SmartLic, {user_name}!
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Seu trial de 14 dias começou. Agora você tem acesso completo à
      plataforma de inteligência em licitações mais avançada do Brasil.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
      <tr>
        <td style="background-color: #e8f5e9; border-radius: 8px; padding: 16px; border-left: 4px solid {SMARTLIC_GREEN};">
          <p style="color: #1b5e20; font-size: 14px; margin: 0 0 12px; font-weight: 600;">
            3 passos para começar:
          </p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding: 6px 0; color: #555; font-size: 14px;">
                <strong style="color: {SMARTLIC_GREEN}; font-size: 18px; margin-right: 8px;">1.</strong>
                Escolha seu setor e UFs de interesse
              </td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #555; font-size: 14px;">
                <strong style="color: {SMARTLIC_GREEN}; font-size: 18px; margin-right: 8px;">2.</strong>
                Faça sua primeira análise com IA
              </td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #555; font-size: 14px;">
                <strong style="color: {SMARTLIC_GREEN}; font-size: 18px; margin-right: 8px;">3.</strong>
                Arraste oportunidades para o pipeline
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{FRONTEND_URL}/buscar" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Fazer primeira análise
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 16px 0 0;">
      Seu trial gratuito de 14 dias começou hoje.
    </p>
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Bem-vindo ao SmartLic!",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #2 — Day 3: Engajamento (AC7)
# ============================================================================

def render_trial_engagement_email(
    user_name: str,
    stats: dict,
    unsubscribe_url: str = "",
    days_remaining: int = 11,
) -> str:
    """EMAIL-TRIAL-006 (#1005) Day 3: Pergunta direta founder-led, 3-5 frases.

    Belgray friend-text — não vendendo nada, perguntando se tá fazendo sentido.
    PS soft com link Founders (não é o foco do email).

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
        days_remaining: Dias restantes do trial (Day 3 → 11). STORY-321 contract.
    """
    has_usage = stats.get("searches_count", 0) > 0
    value = stats.get("total_value_estimated", 0.0)
    opps = stats.get("opportunities_found", 0)

    # Personalize intro based on usage tier — keep it founder-led, never institutional
    if has_usage and (value > 0 or opps > 0):
        usage_line = (
            f"Vi que você já rodou algumas análises por aí — "
            f"{opps if opps else 'várias'} oportunidades aparecendo até agora."
        )
        question = "Tá batendo com o que sua empresa procura? Falta alguma coisa?"
    elif has_usage:
        usage_line = "Vi que você fez sua primeira busca — bom começo."
        question = "Os filtros tão fazendo sentido? Algum setor faltando que devíamos cobrir?"
    else:
        usage_line = (
            "Vi que você ainda não rodou nenhuma busca — sem stress, "
            "leva uns 30 segundos."
        )
        question = (
            "Antes de você apertar o play: tem algum setor específico que sua empresa atende? "
            "Posso te dar dicas de filtro pra pegar os editais certos."
        )

    body = f"""
    {_preheader("Pergunta rápida: tá fazendo sentido?")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 20px;">
      Tá fazendo sentido?
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {user_name}, aqui é o Tiago, fundador do SmartLic.
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {usage_line}
    </p>
    <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 14px; font-weight: 600;">
      {question}
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">
      Responde esse email com 1 linha — chega direto na minha caixa.
      Leio e respondo todos. Ainda faltam {days_remaining} dias do seu trial,
      dá pra explorar com calma.
    </p>

    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{FRONTEND_URL}/buscar"
         style="display: inline-block; padding: 12px 28px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
        {'Voltar pra busca' if has_usage else 'Fazer minha primeira busca'}
      </a>
    </p>

    {_founder_signature_html()}

    <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 28px 0 0; padding-top: 16px; border-top: 1px solid #f0f0f0;">
      P.S.: existe um <a href="{FRONTEND_URL}/fundadores" style="color: #f59e0b; text-decoration: underline; font-weight: 600;">plano vitalício de R$ 997</a>
      — pra quem tá usando ativo e quer travar o preço pra sempre. Não é pra todo mundo, mas tá lá se interessar.
    </p>

    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Pergunta rápida: tá fazendo sentido?",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #3 — Day 7: Paywall Alert (AC7 — NEW)
# ============================================================================

def render_trial_paywall_alert_email(
    user_name: str,
    stats: dict,
    unsubscribe_url: str = "",
    seats_remaining: int | None = None,
) -> str:
    """EMAIL-TRIAL-006 (#1005) Day 7: Pro vs Vitalício — a conta nua.

    Tom Belgray "ouça antes de decidir" + tabela visual R$397 × 12 = R$4.764 vs R$997.
    CTA primário Founders, CTA secundário Pro mensal.

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
        seats_remaining: From #1002 founders availability. None → fallback genérico.
    """
    has_usage = stats.get("searches_count", 0) > 0
    value = stats.get("total_value_estimated", 0.0)

    if has_usage and value > 0:
        usage_line = (
            f"Em 7 dias você já mapeou <strong>{_format_brl(value)}</strong> em "
            f"oportunidades. Tá funcionando."
        )
    elif has_usage:
        usage_line = "Você já tá usando — bom sinal."
    else:
        usage_line = (
            "Você ainda não rodou uma busca — sem stress, "
            "mas tem 7 dias pra testar antes do trial virar preview limitado."
        )

    body = f"""
    {_preheader("Ouça antes de decidir: a conta do Pro mensal vs vitalício.")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 18px;">
      A conta nua: Pro mensal × Vitalício
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {user_name}, metade do trial e queria ser direto com você.
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {usage_line}
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 12px;">
      Antes de você decidir entre seguir trial ou assinar, dá uma olhada nos números:
    </p>

    {_founders_pricing_table_html()}

    <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 14px;">
      <strong>Por que o vitalício existe:</strong> tô captando os primeiros 50 fundadores
      que vão ajudar o SmartLic a virar a ferramenta certa pra B2G. Em troca, você trava
      acesso pra sempre — sem mensalidade, sem reajuste anual.
    </p>

    {_founders_cross_sell_block(seats_remaining)}

    <p style="text-align: center; margin: 12px 0 8px;">
      <a href="{FRONTEND_URL}/planos"
         style="display: inline-block; padding: 10px 22px; color: {SMARTLIC_GREEN}; text-decoration: none; border: 1px solid {SMARTLIC_GREEN}; border-radius: 6px; font-weight: 600; font-size: 14px;">
        Ou continuar com Pro mensal →
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 8px 0 0;">
      Restam 7 dias do seu trial. Sem pressa, sem cartão.
    </p>

    {_founder_signature_html()}
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Ouça antes de decidir: a conta do Pro vs vitalício",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #4 — Day 10: Valor Acumulado (AC7 — NEW)
# ============================================================================

def _top_opportunity_block(stats: dict) -> str:
    """STORY-371 AC2: Render personalized top opportunity block for day 10 email."""
    top_opp = stats.get("top_opportunity")
    if not top_opp or not top_opp.get("objeto"):
        return ""
    objeto = top_opp.get("objeto", "")
    orgao = top_opp.get("orgao_nome", "")
    valor = top_opp.get("valor_formatado", "")
    dias = top_opp.get("dias_ate_encerramento")
    numero = top_opp.get("numero_controle", "")

    prazo_text = ""
    if dias is not None:
        if dias == 0:
            prazo_text = " · vence hoje"
        elif dias == 1:
            prazo_text = " · vence amanhã"
        else:
            prazo_text = f" · vence em {dias} dias"

    cta_url = f"{FRONTEND_URL}/buscar?highlight={numero}" if numero else f"{FRONTEND_URL}/buscar"

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin: 16px 0 24px;">
      <tr>
        <td style="border: 2px solid #1a6cf6; border-radius: 8px; padding: 16px;">
          <p style="color: #888; font-size: 12px; margin: 0 0 8px; text-transform: uppercase; letter-spacing: 1px;">
            📋 Sua maior oportunidade identificada
          </p>
          <p style="color: #1a1a2e; font-size: 16px; font-weight: 600; margin: 0 0 6px; line-height: 1.4;">
            {objeto}
          </p>
          {"<p style='color: #555; font-size: 14px; margin: 0 0 6px;'>" + orgao + "</p>" if orgao else ""}
          <p style="color: #1a6cf6; font-size: 15px; font-weight: 700; margin: 0 0 12px;">
            {valor}{prazo_text}
          </p>
          <a href="{cta_url}"
             style="display: inline-block; padding: 10px 20px; background-color: #1a6cf6; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px;">
            Ver este edital agora →
          </a>
        </td>
      </tr>
    </table>"""


def render_trial_value_email(
    user_name: str,
    stats: dict,
    unsubscribe_url: str = "",
    seats_remaining: int | None = None,
    days_remaining: int = 4,
) -> str:
    """EMAIL-TRIAL-006 (#1005) Day 10: Chaperon open loop — terceira opção.

    "Antes de você escolher entre cancelar ou virar Pro, tem uma terceira opção
    que talvez ninguém te contou ainda." → Reveal: Founders.

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
        seats_remaining: From #1002. None → fallback copy.
        days_remaining: dias até trial expirar (Day 10 → 4).
    """
    value = stats.get("total_value_estimated", 0.0)
    opps = stats.get("opportunities_found", 0)

    seats_text = (
        f"{seats_remaining} vagas vitalícias"
        if seats_remaining is not None and seats_remaining > 0
        else "vagas vitalícias limitadas"
    )

    preheader_text = (
        f"Faltam {seats_remaining} vagas vitalícias (e {days_remaining} dias)"
        if seats_remaining is not None and seats_remaining > 0
        else f"Antes de decidir: tem uma terceira opção (faltam {days_remaining} dias)"
    )

    if seats_remaining is not None and seats_remaining > 0:
        headline = f"Faltam {seats_remaining} vagas vitalícias (e {days_remaining} dias)"
    else:
        headline = f"Antes de decidir, tem uma terceira opção (faltam {days_remaining} dias)"

    # Open loop intro — Chaperon style
    body = f"""
    {_preheader(preheader_text)}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 18px;">
      {headline}
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {user_name}, faltam {days_remaining} dias do seu trial.
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      A maioria das pessoas chega aqui pensando em duas opções: <strong>cancelar</strong>
      ou <strong>virar Pro mensal</strong> (R$ 397/mês).
    </p>
    <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 14px; font-weight: 600;">
      Mas tem uma terceira opção que talvez ninguém te contou ainda.
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Eu tô abrindo um <strong>Plano Fundadores</strong>: você paga R$ 997 uma vez e
      usa o SmartLic Pro <em>vitalício</em> — sem mensalidade, sem reajuste, pra sempre.
      Restam {seats_text}, e a oferta encerra dia 30/06.
    </p>
    """

    # Inline progress block — concrete proof user is getting value
    if value > 0 or opps > 0:
        body += f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin: 16px 0 20px;">
      <tr>
        <td style="background-color: #f8faf8; border-left: 3px solid {SMARTLIC_GREEN}; padding: 14px 18px;">
          <p style="color: #555; font-size: 14px; margin: 0; line-height: 1.5;">
            Em 10 dias você já mapeou <strong>{opps} oportunidade{'s' if opps != 1 else ''}</strong>
            {f"totalizando <strong>{_format_brl(value)}</strong>" if value > 0 else ""}.
            Não jogue isso fora.
          </p>
        </td>
      </tr>
    </table>
    """

    body += f"""
    {_top_opportunity_block(stats)}
    {_founders_cross_sell_block(seats_remaining)}

    <p style="text-align: center; margin: 12px 0 8px;">
      <a href="{FRONTEND_URL}/planos"
         style="display: inline-block; padding: 10px 22px; color: {SMARTLIC_GREEN}; text-decoration: none; border: 1px solid {SMARTLIC_GREEN}; border-radius: 6px; font-weight: 600; font-size: 14px;">
        Prefiro Pro mensal →
      </a>
    </p>

    {_founder_signature_html()}
    {_unsubscribe_block(unsubscribe_url)}
    """

    title = (
        f"Faltam {seats_remaining} vagas vitalícias"
        if seats_remaining is not None and seats_remaining > 0
        else "Antes de decidir, tem uma terceira opção"
    )

    return email_base(
        title=title,
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #5 — Day 13: Ultimo Dia (AC7)
# ============================================================================

def _day13_comparison_table_html() -> str:
    """3-column comparison: cancelar / Pro mensal / Vitalício.

    EMAIL-TRIAL-006 (#1005) Day 13 — honesty-driven decision aid.
    """
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="margin: 18px 0 22px; border-collapse: separate; border-spacing: 0;">
      <tr>
        <td style="width: 33%; vertical-align: top; padding: 0 4px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #e5e7eb; border-radius: 8px;">
            <tr><td style="padding: 14px; text-align: center;">
              <p style="color: #6b7280; font-size: 12px; margin: 0 0 6px; text-transform: uppercase; font-weight: 600;">Cancelar</p>
              <p style="color: #374151; font-size: 18px; font-weight: 700; margin: 0 0 6px;">R$ 0</p>
              <p style="color: #6b7280; font-size: 12px; margin: 0; line-height: 1.4;">Você perde acesso e os dados ficam salvos por 30 dias.</p>
            </td></tr>
          </table>
        </td>
        <td style="width: 33%; vertical-align: top; padding: 0 4px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #e5e7eb; border-radius: 8px;">
            <tr><td style="padding: 14px; text-align: center;">
              <p style="color: #6b7280; font-size: 12px; margin: 0 0 6px; text-transform: uppercase; font-weight: 600;">Pro mensal</p>
              <p style="color: #374151; font-size: 18px; font-weight: 700; margin: 0 0 6px;">R$ 397/mês</p>
              <p style="color: #6b7280; font-size: 12px; margin: 0; line-height: 1.4;">Acesso completo. Cancele quando quiser.</p>
            </td></tr>
          </table>
        </td>
        <td style="width: 33%; vertical-align: top; padding: 0 4px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border: 2px solid #f59e0b; border-radius: 8px; background-color: #fffbeb;">
            <tr><td style="padding: 13px; text-align: center;">
              <p style="color: #92400e; font-size: 12px; margin: 0 0 6px; text-transform: uppercase; font-weight: 700;">Vitalício</p>
              <p style="color: #78350f; font-size: 18px; font-weight: 700; margin: 0 0 6px;">R$ 997 uma vez</p>
              <p style="color: #92400e; font-size: 12px; margin: 0; line-height: 1.4;">Pague 1×, use pra sempre.</p>
            </td></tr>
          </table>
        </td>
      </tr>
    </table>"""


def render_trial_last_day_email(
    user_name: str,
    stats: dict,
    unsubscribe_url: str = "",
    seats_remaining: int | None = None,
) -> str:
    """EMAIL-TRIAL-006 (#1005) Day 13 (legacy branch): "amanhã vira abóbora" + comparison.

    Tom leve, honest, sem urgência fake. 3-column table cancelar/Pro/Founders lado a lado.

    NOTA: Aplica-se SOMENTE quando user NÃO tem cartão (rollout_branch="legacy").
    Para cartão na mão, ver render_trial_last_day_card_email (compliance copy distinto).

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
        seats_remaining: From #1002. None → fallback genérico.
    """
    value = stats.get("total_value_estimated", 0.0)
    opps = stats.get("opportunities_found", 0)

    if value > 0:
        preheader_text = (
            f"Amanhã seu trial vira abóbora 🎃 — você perde acesso a "
            f"{_format_brl(value)} em oportunidades mapeadas."
        )
    else:
        preheader_text = "Amanhã seu trial vira abóbora 🎃 — sem pressão, mas..."

    if value > 0 and opps > 0:
        progress_line = (
            f"Em 13 dias você mapeou <strong>{opps} oportunidades</strong> totalizando "
            f"<strong>{_format_brl(value)}</strong>. Amanhã esse acesso vai embora — "
            f"os dados ficam salvos por 30 dias, mas a busca/IA/pipeline não."
        )
    elif opps > 0:
        progress_line = (
            f"Você mapeou <strong>{opps} oportunidade{'s' if opps != 1 else ''}</strong> "
            f"até aqui. Amanhã o acesso fecha — sem drama, é só o trial chegando ao fim."
        )
    else:
        progress_line = (
            "Você não chegou a rodar muita coisa, e tudo bem. "
            "Amanhã o trial fecha mesmo assim — queria deixar todas as opções na mesa antes."
        )

    body = f"""
    {_preheader(preheader_text)}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
      Amanhã seu trial vira abóbora 🎃
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {user_name}, sem pressão — mas queria ser direto com você antes do trial fechar.
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      {progress_line}
    </p>
    <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 6px; font-weight: 600;">
      Suas três opções, lado a lado:
    </p>

    {_day13_comparison_table_html()}

    {_founders_cross_sell_block(seats_remaining)}

    <p style="text-align: center; margin: 4px 0 16px;">
      <a href="{FRONTEND_URL}/planos"
         style="display: inline-block; padding: 10px 22px; color: {SMARTLIC_GREEN}; text-decoration: none; border: 1px solid {SMARTLIC_GREEN}; border-radius: 6px; font-weight: 600; font-size: 14px;">
        Ou continuar com Pro mensal →
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 8px 0 0;">
      Sem cartão cadastrado, então ninguém vai cobrar nada amanhã. É só seu trial fechando.
    </p>

    {_founder_signature_html()}
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Amanhã seu trial vira abóbora 🎃 — sem pressão, mas...",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #5b — Day 13 (branch=card): First-charge-tomorrow notice (STORY-CONV-003c AC1)
#
# Distinct from render_trial_last_day_email (branch=legacy) because for users
# with a payment method on file (rollout_branch="card"), tomorrow the trial
# auto-converts: the charge happens without any user action. Legacy copy
# ("amanhã seu acesso expira — assine agora") is wrong for this cohort —
# access does NOT expire; it seamlessly continues. What this cohort needs is:
# (a) explicit compliance notice of charge amount/date (reduces chargebacks),
# (b) visible one-click cancel path via signed JWT link.
#
# Copy variant: "ROI-focused + urgência suave" (approved by product 2026-04-21).
# ============================================================================

def render_trial_last_day_card_email(
    user_name: str,
    stats: dict,
    charge_date_display: str,
    plan_name: str,
    amount_display: str,
    cancel_url: str,
    unsubscribe_url: str = "",
) -> str:
    """Render the D-1-before-auto-charge email for users on the card rollout branch.

    This is the CONV-003c AC1 compliance notice: tomorrow the trial will
    auto-convert to paid via the card on file. The user does NOT need to
    take any action to continue. The prominent CTA is a one-click cancel
    link (signed JWT, 48h validity) so users who want out can exit with a
    single click — essential to minimize chargebacks on the first billing
    cycle after trial.

    Args:
        user_name: User's display name (e.g. "Ana").
        stats: Dict with trial-usage counters. Reads ``opportunities_found``
            and ``total_value_estimated`` to build the ROI headline. Empty
            stats fall back to a neutral variant.
        charge_date_display: Human-readable charge date ("amanhã, 21/04",
            or "amanhã" if the caller prefers minimal date noise).
        plan_name: Plan label shown in the body (e.g. "SmartLic Pro").
        amount_display: Formatted amount string (e.g. "R$ 397/mês").
        cancel_url: Fully-qualified URL containing the signed cancel-trial
            JWT (from ``services.trial_cancel_token.generate_token``).
        unsubscribe_url: Conversion emails are NOT marketing, but the block
            is rendered if provided for rendering-consistency.
    """
    opps = stats.get("opportunities_found", 0)
    value = stats.get("total_value_estimated", 0.0)

    if value > 0 and opps > 0:
        headline = f"{opps} oportunidades em 14 dias — continue amanhã com SmartLic Pro"
        lead = (
            f"{user_name}, em 14 dias você acessou <strong>{opps} editais</strong> "
            f"com potencial de <strong>{_format_brl(value)}</strong> em contratos."
        )
        preheader_text = (
            f"{opps} oportunidades em 14 dias — amanhã vira SmartLic Pro ({amount_display})."
        )
    elif opps > 0:
        headline = f"{opps} oportunidades em 14 dias — continue amanhã com SmartLic Pro"
        lead = (
            f"{user_name}, em 14 dias você acessou <strong>{opps} editais</strong> "
            f"relevantes no SmartLic."
        )
        preheader_text = (
            f"{opps} oportunidades mapeadas — amanhã vira SmartLic Pro ({amount_display})."
        )
    else:
        headline = f"Amanhã seu trial vira {plan_name} — continue ou cancele em 1 clique"
        lead = (
            f"{user_name}, seu trial de 14 dias termina amanhã."
        )
        preheader_text = (
            f"Amanhã seu trial vira {plan_name} ({amount_display}). Cancele em 1 clique se preferir."
        )

    body = f"""
    {_preheader(preheader_text)}
    <h1 style="color: {SMARTLIC_GREEN}; font-size: 22px; margin: 0 0 16px;">
      {headline}
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      {lead}
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      <strong>Amanhã ({charge_date_display})</strong>, seu trial vira {plan_name}:
      <strong>{amount_display}</strong> cobrados automaticamente no cartão cadastrado.
      Continue crescendo — nada a fazer.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color: #f8faf8; border-radius: 8px; border: 1px solid #e8f5e9; margin: 16px 0 24px;">
      <tr>
        <td style="padding: 16px 20px;">
          <p style="color: #555; font-size: 14px; margin: 0; line-height: 1.6;">
            Prefere pausar? Sem custo, sem perguntas. Cancele antes da cobrança:
          </p>
        </td>
      </tr>
    </table>

    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{cancel_url}" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: #ffffff; color: #d32f2f; text-decoration: none; border: 2px solid #d32f2f; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Cancelar minha trial
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 16px 0 0;">
      Link válido por 48 horas. Ao cancelar, você mantém acesso até o final do trial
      sem cobrança.
    </p>
    <p style="color: #333; font-size: 15px; text-align: center; margin: 32px 0 0;">
      Vamos juntos,<br/>
      <strong>Equipe SmartLic</strong>
    </p>
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title=f"Amanhã sua trial vira {plan_name} — {amount_display}",
        body_html=body,
        # Conversion/compliance notice about an imminent charge is NOT
        # marketing: it must reach users who opted out of marketing emails.
        # The trial_email_sequence dispatcher classifies last_day as a
        # conversion email and bypasses the marketing opt-out accordingly.
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #6 — Day 16: Expirado (AC7 + AC14: coupon 20% off)
# ============================================================================

def render_trial_expired_email(
    user_name: str,
    stats: dict,
    unsubscribe_url: str = "",
    coupon_checkout_url: str = "",
) -> str:
    """EMAIL-TRIAL-006 (#1005) Day 16 (lapsed): "Errei algo? Resposta de 1 linha resolve"

    Founder pergunta diretamente o que faltou. PS mantém cupom TRIAL_COMEBACK_20.

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
        coupon_checkout_url: Checkout URL with TRIAL_COMEBACK_20 coupon applied.
    """
    opps = stats.get("opportunities_found", 0)
    pipeline = stats.get("pipeline_items_count", 0)

    cta_url = coupon_checkout_url if coupon_checkout_url else f"{FRONTEND_URL}/planos"

    progress_recap = ""
    if opps > 0 or pipeline > 0:
        progress_recap = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin: 14px 0 18px;">
      <tr>
        <td style="background-color: #f8faf8; border-left: 3px solid {SMARTLIC_GREEN}; padding: 12px 16px;">
          <p style="color: #555; font-size: 14px; margin: 0; line-height: 1.5;">
            Pra constar: você deixou {opps} oportunidade{'s' if opps != 1 else ''} mapeada{'s' if opps != 1 else ''}
            {f"e {pipeline} item{'ns' if pipeline != 1 else ''} no pipeline" if pipeline > 0 else ""}.
            Seus dados ficam salvos por 30 dias.
          </p>
        </td>
      </tr>
    </table>"""

    body = f"""
    {_preheader("Errei algo? Resposta direta de 1 linha resolve.")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 18px;">
      Errei algo?
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      {user_name}, seu trial fechou ontem.
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 14px;">
      Sem dramatização — é só que eu preferia entender o que rolou. Te ajudaria
      muito se você respondesse com 1 linha:
    </p>
    <p style="color: #333; font-size: 16px; line-height: 1.6; margin: 0 0 14px; padding-left: 16px; border-left: 3px solid #d1d5db;">
      <em>"Cancelei porque ___"</em>
    </p>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 18px;">
      Pode ser preço, pode ser que faltava feature X, pode ser que não era
      o momento. Qualquer resposta me ajuda a melhorar o produto.
    </p>
    {progress_recap}

    {_founder_signature_html()}

    <p style="color: #999; font-size: 13px; line-height: 1.6; margin: 28px 0 0; padding-top: 16px; border-top: 1px solid #f0f0f0;">
      P.S.: se quiser voltar, segura aí 20% off no primeiro mês do Pro com o cupom
      <strong>TRIAL_COMEBACK_20</strong> —
      <a href="{cta_url}" style="color: {SMARTLIC_GREEN}; text-decoration: underline; font-weight: 600;">aplicar agora</a>.
      Ou se preferir vitalício pra travar preço pra sempre, o
      <a href="{FRONTEND_URL}/fundadores" style="color: #f59e0b; text-decoration: underline; font-weight: 600;">Plano Fundadores R$ 997</a>
      ainda tá em pé.
    </p>

    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Errei algo? Resposta direta de 1 linha resolve",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #10 — Day 2: Feature Discovery — Pipeline (Zero-Churn P1 Frente 2B)
# ============================================================================

def render_trial_feature_pipeline_email(user_name: str, stats: dict, unsubscribe_url: str = "") -> str:
    """Day 2 — Feature discovery: Pipeline kanban for tracking opportunities.

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
    """
    body = f"""
    {_preheader("Organize suas oportunidades com o Pipeline drag-and-drop do SmartLic.")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
      Organize suas oportunidades no Pipeline
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Olá, {user_name}! Você sabia que o SmartLic tem um pipeline visual
      estilo kanban para acompanhar suas oportunidades de ponta a ponta?
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
      <tr>
        <td style="background-color: #e8f5e9; border-radius: 8px; padding: 16px; border-left: 4px solid {SMARTLIC_GREEN};">
          <p style="color: #1b5e20; font-size: 14px; margin: 0 0 12px; font-weight: 600;">
            O que você pode fazer no Pipeline:
          </p>
          <ul style="color: #555; font-size: 14px; margin: 0; padding-left: 20px;">
            <li style="padding: 4px 0;">Arraste oportunidades entre colunas (Lead → Análise → Proposta → Ganho)</li>
            <li style="padding: 4px 0;">Acompanhe prazos e valores de cada edital</li>
            <li style="padding: 4px 0;">Tenha uma visão consolidada de todo o seu funil B2G</li>
          </ul>
        </td>
      </tr>
    </table>

    {_stats_block(stats) if stats.get("searches_count", 0) > 0 else ''}

    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{FRONTEND_URL}/pipeline" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Abrir meu Pipeline
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 16px 0 0;">
      Dica: após uma busca, clique em "Adicionar ao Pipeline" em qualquer oportunidade.
    </p>
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Organize suas oportunidades no Pipeline — SmartLic",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #11 — Day 5: Feature Discovery — Excel Export (Zero-Churn P1 Frente 2B)
# ============================================================================

def render_trial_feature_excel_email(user_name: str, stats: dict, unsubscribe_url: str = "") -> str:
    """Day 5 — Feature discovery: Excel export for sharing with team.

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
    """
    body = f"""
    {_preheader("Exporte suas análises para Excel estilizado e compartilhe com a equipe.")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
      Exporte análises para Excel com 1 clique
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Olá, {user_name}! Precisa compartilhar oportunidades com sua equipe ou
      diretoria? O SmartLic gera relatórios Excel estilizados prontos para apresentação.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
      <tr>
        <td style="background-color: #e8f5e9; border-radius: 8px; padding: 16px; border-left: 4px solid {SMARTLIC_GREEN};">
          <p style="color: #1b5e20; font-size: 14px; margin: 0 0 12px; font-weight: 600;">
            O relatório Excel inclui:
          </p>
          <ul style="color: #555; font-size: 14px; margin: 0; padding-left: 20px;">
            <li style="padding: 4px 0;">Lista completa de oportunidades com classificação IA</li>
            <li style="padding: 4px 0;">Score de viabilidade e análise por fator</li>
            <li style="padding: 4px 0;">Formatação profissional pronta para decisão</li>
          </ul>
        </td>
      </tr>
    </table>

    {_stats_block(stats) if stats.get("searches_count", 0) > 0 else ''}

    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{FRONTEND_URL}/buscar" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Exportar meu primeiro relatório
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 16px 0 0;">
      Dica: após uma busca, clique em "Exportar Excel" no topo dos resultados.
    </p>
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="Exporte análises para Excel — SmartLic",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ============================================================================
# Email #12 — Day 8: Feature Discovery — AI Classification (Zero-Churn P1 Frente 2B)
# ============================================================================

def render_trial_feature_ai_email(user_name: str, stats: dict, unsubscribe_url: str = "") -> str:
    """Day 8 — Feature discovery: AI classification across 15 sectors.

    Args:
        user_name: User's display name.
        stats: Dict with keys from TrialUsageStats.
        unsubscribe_url: URL for one-click unsubscribe.
    """
    body = f"""
    {_preheader("A IA do SmartLic classifica oportunidades em 15 setores e calcula viabilidade.")}
    <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
      IA classifica oportunidades para você
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Olá, {user_name}! Você está usando todo o poder da IA do SmartLic?
      Nossa inteligência artificial analisa cada edital e entrega apenas
      o que importa para o seu negócio.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
      <tr>
        <td style="background-color: #e8f5e9; border-radius: 8px; padding: 16px; border-left: 4px solid {SMARTLIC_GREEN};">
          <p style="color: #1b5e20; font-size: 14px; margin: 0 0 12px; font-weight: 600;">
            Como a IA trabalha para você:
          </p>
          <ul style="color: #555; font-size: 14px; margin: 0; padding-left: 20px;">
            <li style="padding: 4px 0;">Classificação automática em 15 setores especializados</li>
            <li style="padding: 4px 0;">Score de viabilidade com 4 fatores (modalidade, prazo, valor, geografia)</li>
            <li style="padding: 4px 0;">Economia de horas filtrando editais irrelevantes automaticamente</li>
          </ul>
        </td>
      </tr>
    </table>

    {_stats_block(stats) if stats.get("searches_count", 0) > 0 else ''}

    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{FRONTEND_URL}/buscar" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Ver classificação IA
      </a>
    </p>
    <p style="color: #888; font-size: 13px; text-align: center; margin: 16px 0 0;">
      Dica: na página de resultados, veja o badge de relevância e o score de viabilidade de cada edital.
    </p>
    {_unsubscribe_block(unsubscribe_url)}
    """

    return email_base(
        title="IA classifica oportunidades para você — SmartLic",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )
