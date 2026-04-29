# ADR: Founding Plan Canonical Policy

**Status:** Accepted
**Date:** 2026-04-28
**Decisão:** User (Tiago Sasaki) via AskUserQuestion `/sm crie todas stories` session
**Story:** [BIZ-FOUND-002](../stories/2026-04/BIZ-FOUND-002-founding-canonical-policy.story.md)

---

## Context

`STORY-BIZ-001` (Done) implementou Stripe coupon + abandonment tracking via `checkout.session.expired`. Mas **não fixou** policy canonical: cap de seats, deadline absoluto, lifetime price guarantee. Sem cap, signups acima do break-even consomem unit economics negativos. SmartLic v0.5 pre-revenue (n=2 30d, memory `feedback_n2_below_noise_eng_theater`).

## Decision

| Parâmetro | Valor canonical | Rationale |
|-----------|------------------|-----------|
| **Seat cap** | **50 seats** | Conservador para n=2 baseline. R$197/mês × 50 = R$9.850 MRR cap teórico. Permite oferta exclusiva + escassez real sem comprometer unit econ. |
| **Deadline absoluto** | **2026-05-30** | 32 dias a partir 2026-04-28. Pressão conversion realista; alinhado state.json sm_handoff prior decision. |
| **Lifetime price guarantee** | **R$197/mês permanente enquanto subscription ativa** | Forte retention magnet. Founding member paga R$197 indefinidamente até cancel. Stripe subscription imutável vs price updates futuros. |
| **Pós-cap reached behavior** | **HTTP 410 GONE + redirect /pricing** | Cap = scarcity hard. Zero overflow. UX preserve via redirect. |
| **Pós-deadline behavior** | **Mantém R$397/mês** (preço normal) | Soft transition. Sem 410 — usuários após deadline pagam Pro normal. Reduz friction marketing pós-deadline. |

## Consequences

### Positivas
- Unit economics protegidos: max R$9.850/mês founding revenue cap.
- Marketing campaign deadline-driven: 32d clear pressure window.
- Lifetime guarantee = retention story para outreach (founding members nunca pagam mais).
- Dual behavior cap×deadline: cap hard limit, deadline soft (recovers signups pós-deadline).

### Negativas
- Lifetime guarantee = company commitment indefinido. Subscription imutável vs Stripe price updates futuros (ADR commitment).
- 50 seats pode esgotar rápido se outreach scale; reduz signal escassez se cap reached antes de deadline.
- Pós-deadline R$397 transition pode confundir leads expostos a R$197 marketing.

### Implementação (BIZ-FOUND-002)

- `founding_caps` table: `seat_limit=50, current_seats=0, deadline_at='2026-05-30 23:59:59 BRT', lifetime_price_cents=19700`
- Race-free increment: `INSERT ON CONFLICT DO UPDATE WHERE current_seats < seat_limit`
- Admin endpoint `/v1/admin/founding-status` retorna `{seat_limit, current_seats, remaining, days_until_deadline}`
- Email reminder cron 7d antes deadline (`founding_deadline_reminder` template)
- Frontend counter `<FoundingCounter />` em landing pages

## Monitoring

- Sentry alert `remaining<=10` (P1 follow-up — implementação separada)
- Mixpanel event `founding_signup` per signup
- Cron `founding_deadline_warning` 1×/dia 7d→0d countdown

## Revision

Esta ADR é canonical até user explicit revision. Founding subscriptions criadas sob esta ADR são imutáveis (lifetime guarantee preservada mesmo se ADR mudar futuro).
