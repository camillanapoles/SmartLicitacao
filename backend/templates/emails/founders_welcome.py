"""Founders Welcome Email — STORY-791.

Sent after a founding checkout completes (dispatched by the webhook handler).
Tom: pessoal, de Tiago. Sem footer corporativo pesado.

from: tiago.sasaki@confenge.com.br
reply-to: tiago.sasaki@gmail.com
"""

from templates.emails.base import email_base, SMARTLIC_GREEN, FRONTEND_URL

FOUNDERS_WELCOME_SUBJECT = "Bem-vindo ao Plano Fundadores SmartLic \U0001f91d"

# Personal sender constants (reused by email_service).
FOUNDERS_FROM = "Tiago do SmartLic <tiago.sasaki@confenge.com.br>"
FOUNDERS_REPLY_TO = "tiago.sasaki@gmail.com"


def render_founders_welcome_email(user_name: str) -> str:
    """Render the founders welcome email (HTML).

    Args:
        user_name: Display name from profiles.full_name or first part of email.

    Returns:
        Full HTML email body wrapped by email_base (no heavy corporate footer).
    """
    body = f"""
    <div style="display:none;font-size:1px;color:#f4f4f4;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">
      Obrigado por ser Fundador do SmartLic — veja o que esta incluido no seu plano.
    </div>

    <p style="color: #555; font-size: 17px; line-height: 1.7; margin: 0 0 20px;">
      Ola, <strong>{user_name}</strong>!
    </p>

    <p style="color: #555; font-size: 16px; line-height: 1.7; margin: 0 0 20px;">
      E o Tiago. Obrigado por confiar no SmartLic desde o inicio. Voce acaba de
      garantir seu lugar como Fundador — e isso significa muito para mim.
    </p>

    <p style="color: #555; font-size: 16px; line-height: 1.7; margin: 0 0 8px;">
      Aqui esta o que esta incluido no seu plano:
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color: #e8f5e9; border-radius: 8px; margin: 0 0 24px;">
      <tr>
        <td style="padding: 20px 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding: 10px 0; color: #1b5e20; font-size: 15px; border-bottom: 1px solid rgba(0,0,0,0.07);">
                <span style="margin-right: 10px;">&#x2705;</span>
                <strong>Acesso vitalicio ao SmartLic Pro</strong> — sem mensalidade, para sempre
              </td>
            </tr>
            <tr>
              <td style="padding: 10px 0; color: #1b5e20; font-size: 15px; border-bottom: 1px solid rgba(0,0,0,0.07);">
                <span style="margin-right: 10px;">&#x2705;</span>
                <strong>50% de desconto vitalicio na Consultoria</strong> — quando quiser contratar
              </td>
            </tr>
            <tr>
              <td style="padding: 10px 0; color: #1b5e20; font-size: 15px; border-bottom: 1px solid rgba(0,0,0,0.07);">
                <span style="margin-right: 10px;">&#x2705;</span>
                <strong>Suporte direto comigo</strong> — responda este email ou use /mensagens
              </td>
            </tr>
            <tr>
              <td style="padding: 10px 0; color: #1b5e20; font-size: 15px;">
                <span style="margin-right: 10px;">&#x2705;</span>
                <strong>Acesso antecipado a novas funcionalidades</strong> — voce ve primeiro
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <p style="color: #555; font-size: 16px; line-height: 1.7; margin: 0 0 20px;">
      <strong>Para resgatar o 50% de desconto na Consultoria:</strong> quando quiser contratar,
      responda este email com o assunto "Consultoria Fundador". Eu vou gerar um link
      de pagamento com o desconto aplicado direto para voce.
    </p>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color: #fff8e1; border-left: 4px solid #f9a825; border-radius: 6px; margin: 0 0 24px;">
      <tr>
        <td style="padding: 16px 20px;">
          <p style="color: #333; font-size: 15px; line-height: 1.6; margin: 0 0 8px;">
            <strong>Garantia de 60 dias &mdash; incondicional.</strong>
          </p>
          <p style="color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 8px;">
            Voce tem 60 dias pra usar a vontade. Se nao fizer sentido, devolvo R$997 cheios.
          </p>
          <p style="color: #555; font-size: 14px; line-height: 1.6; margin: 0;">
            Sem letra miuda: e so responder este email (ou escrever para
            <a href="mailto:tiago@smartlic.tech" style="color: {SMARTLIC_GREEN};">tiago@smartlic.tech</a>)
            com o assunto <strong>"reembolso"</strong>. Retorno em ate 5 dias uteis.
          </p>
        </td>
      </tr>
    </table>

    <p style="text-align: center; margin: 28px 0 24px;">
      <a href="{FRONTEND_URL}/buscar"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN};
                color: #ffffff; text-decoration: none; border-radius: 8px;
                font-weight: 600; font-size: 16px;">
        Fazer minha primeira busca &rarr;
      </a>
    </p>

    <p style="color: #555; font-size: 15px; line-height: 1.7; margin: 0 0 12px;">
      Ficaria muito feliz em saber o que voce achou nos primeiros dias de uso.
      <strong>Responda este email com suas impressoes</strong> — leio todos pessoalmente.
    </p>

    <p style="color: #555; font-size: 15px; line-height: 1.7; margin: 0;">
      Um abraco,<br>
      <strong>Tiago</strong><br>
      <span style="color: #888; font-size: 13px;">Fundador, SmartLic</span>
    </p>
    """

    return email_base(
        title=FOUNDERS_WELCOME_SUBJECT,
        body_html=body,
        is_transactional=True,
    )


def render_founders_welcome_plain(user_name: str) -> str:
    """Render the founders welcome email as plain text fallback.

    Args:
        user_name: Display name from profiles.full_name or email prefix.

    Returns:
        Plain-text email body string.
    """
    return f"""Ola, {user_name}!

E o Tiago. Obrigado por confiar no SmartLic desde o inicio. Voce acaba de
garantir seu lugar como Fundador — e isso significa muito para mim.

Aqui esta o que esta incluido no seu plano:

- Acesso vitalicio ao SmartLic Pro (sem mensalidade, para sempre)
- 50% de desconto vitalicio na Consultoria (quando quiser contratar)
- Suporte direto comigo (responda este email ou use /mensagens)
- Acesso antecipado a novas funcionalidades

Para resgatar o 50% de desconto na Consultoria: quando quiser contratar,
responda este email com o assunto "Consultoria Fundador". Eu gero um link
de pagamento com o desconto aplicado direto para voce.

Garantia de 60 dias - incondicional.
Voce tem 60 dias pra usar a vontade. Se nao fizer sentido, devolvo R$997 cheios.
Sem letra miuda: responda este email (ou escreva para tiago@smartlic.tech)
com o assunto "reembolso". Retorno em ate 5 dias uteis.

Faca sua primeira busca agora: {FRONTEND_URL}/buscar

Ficaria muito feliz em saber o que voce achou nos primeiros dias de uso.
Responda este email com suas impressoes — leio todos pessoalmente.

Um abraco,
Tiago
Fundador, SmartLic
"""
