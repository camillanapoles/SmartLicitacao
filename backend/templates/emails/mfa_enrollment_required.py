"""
MFA enrollment required email template — MFA-EXT-001 AC3.

Two variants:

* ``consultoria`` — Plano Consultoria mandatory MFA (14d grace window).
* ``bruteforce`` — 3 consecutive password failures detected; MFA mandatory
  for 7 days (banner + email reinforce).

Sent by:
* Backfill on the first cron tick after the consultoria plan upgrade
  (variant=consultoria), and
* `POST /v1/auth/login-attempt` immediately after the 3rd consecutive
  password failure (variant=bruteforce, transition 2 -> 3 only).
"""

from typing import Literal

from templates.emails.base import email_base, SMARTLIC_GREEN, FRONTEND_URL


VariantT = Literal["consultoria", "bruteforce"]


def render_mfa_enrollment_required_email(
    user_name: str,
    variant: VariantT,
    grace_days: int = 14,
    setup_url: str = "",
) -> str:
    """Render the MFA enrollment required email.

    Args:
        user_name: Display name.
        variant: ``consultoria`` (plan upgrade) or ``bruteforce`` (3 fails).
        grace_days: Days remaining to enroll (positive integer).
        setup_url: Override CTA URL (default: ``/conta/seguranca``).

    Returns:
        Rendered HTML string.
    """
    if not setup_url:
        setup_url = f"{FRONTEND_URL}/conta/seguranca"

    if variant == "consultoria":
        title = "MFA obrigatorio no Plano Consultoria"
        headline = f"Configure MFA em ate {grace_days} dias"
        intro = (
            "Como assinante do Plano Consultoria, sua conta requer "
            "autenticacao em dois fatores (MFA) para atender aos padroes "
            "de seguranca corporativos."
        )
        why = (
            "MFA adiciona uma segunda camada alem da senha — um codigo "
            "rotativo gerado pelo seu celular. Mesmo se a senha vazar, a "
            "conta permanece protegida."
        )
        urgency = (
            f"Voce tem ate {grace_days} dias para configurar. Apos esse "
            "prazo, o acesso a recursos protegidos sera bloqueado ate o "
            "MFA ser ativado."
        )
    else:  # bruteforce
        title = "Atividade suspeita detectada — Configure MFA"
        headline = "Multiplas tentativas de senha detectadas"
        intro = (
            "Detectamos 3 tentativas consecutivas de senha invalidas na "
            "sua conta. Como medida preventiva, ativamos a obrigatoriedade "
            "de MFA pelos proximos 7 dias."
        )
        why = (
            "Se foi voce que esqueceu a senha, sem problemas — basta "
            "configurar MFA agora para continuar usando a plataforma. Se "
            "nao foi voce, tambem recomendamos configurar MFA "
            "imediatamente para proteger seus dados."
        )
        urgency = (
            f"O bloqueio dura {grace_days} dias ou ate voce ativar MFA — "
            "o que vier primeiro."
        )

    body = f"""
    <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
      Ola, {user_name}
    </h1>
    <h2 style="color: {SMARTLIC_GREEN}; font-size: 18px; margin: 0 0 16px;">
      {headline}
    </h2>
    <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 16px;">
      {intro}
    </p>
    <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 16px;">
      {why}
    </p>
    <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">
      <strong>{urgency}</strong>
    </p>

    <p style="text-align: center; margin: 24px 0;">
      <a href="{setup_url}"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
        Configurar MFA agora
      </a>
    </p>

    <p style="color: #888; font-size: 13px; margin: 24px 0 0; line-height: 1.5;">
      Tempo estimado: 2 minutos. Voce vai precisar de um app autenticador
      (Google Authenticator, Authy, 1Password) instalado no celular.
    </p>
    <p style="color: #888; font-size: 13px; margin: 12px 0 0; line-height: 1.5;">
      Duvidas? Responda este email — nossa equipe ajuda diretamente.
    </p>
    """

    return email_base(
        title=title,
        body_html=body,
        is_transactional=True,
    )
