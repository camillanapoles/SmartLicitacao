# HMAC-ENFORCE-001: Trial emails webhook HMAC signature enforcement (Gap-5 close)

**Priority:** P1
**Effort:** S (4-8h) — actual: ~30min audit (no implementation needed)
**Squad:** @dev (lead) + @qa
**Status:** Done
**Epic:** [EPIC-SEC-2026-Q2](EPIC-SEC-2026-Q2/) — eixo RBAC/Security
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma
**Reversa anchor:** `_reversa_sdd/review-report.md §11.2 Gap-5` + memory `reference_trial_email_log_delivery_status_null.md`
**Score Δ:** RBAC/Security +3 (88% → 91%)

---

## Contexto

Memory entry `reference_trial_email_log_delivery_status_null` documentava (mas a versão mais recente já reflete PR #534 shipped):

> "HMAC-SHA256 verify: `routes/trial_emails.py::_verify_svix_signature` (PR #534) — 5min replay protection, fail-closed"

Empirical 2026-05-09: auditoria empírica de `backend/routes/trial_emails.py` confirma que **HMAC enforcement já está implementado e em produção** desde a primeira versão da rota (PR #534). PR #858 adicionou apenas o canonical alias `TRIAL_EMAILS_WEBHOOK_SECRET`. 8 testes existem em `backend/tests/test_resend_webhook_signature.py` e todos passam.

Risco original (webhook Resend pode receber payload spoofed → trial_email_log poisoning) **já está mitigado**.

---

## Implementation Notes — Audit Findings (2026-05-09)

### Estado atual vs. esperado (AC1)

| Aspecto | Esperado (story) | Atual (`backend/routes/trial_emails.py`) | Status |
|---------|------------------|------------------------------------------|--------|
| Header check | `Resend-Signature` ou `Webhook-Signature` | `svix-id` + `svix-timestamp` + `svix-signature` | ✅ Correto (Resend usa Svix internamente — https://resend.com/docs/webhooks/verify) |
| Body raw read antes de JSON parse | Sim | `raw_body = await request.body()` antes de `json.loads` (linha 163) | ✅ |
| Constant-time compare | `hmac.compare_digest()` | `secrets.compare_digest()` (linha 135) | ✅ Equivalente |
| Reject ANTES de DB writes | Sim | Verify→raise antes do `handle_resend_webhook` (linhas 165-170) | ✅ |
| Secret canonical | `TRIAL_EMAILS_WEBHOOK_SECRET` | `os.getenv("TRIAL_EMAILS_WEBHOOK_SECRET", "") or os.getenv("RESEND_WEBHOOK_SECRET", "")` (linha 102) | ✅ Canonical + legacy fallback |
| Replay protection | TBD | 5-min timestamp tolerance (linha 86, 120) | ✅ Bonus (Svix recommended) |
| Logging signature mismatch | Sentry breadcrumb sem secret | `logger.warning` com primeiros 16 chars do svix-id (linha 166-169) | ✅ |

### Deltas intencionais vs. spec (não corrigir)

1. **HTTP 401 vs 403:** A rota retorna `401 Unauthorized` (não `403 Forbidden`). Comentário inline (linhas 159-161): _"401 on signature failure (Resend will retry — desired so legitimate events aren't lost during transient secret rotation)."_ Esta é a convenção Svix/Resend correta. A story sugere 403, mas 401 é semanticamente mais preciso para falha de autenticação (não autorização) — e crucialmente Resend retry behavior depende disso.
2. **Headers Svix triplet vs. `Resend-Signature`:** Resend emite headers no formato Svix (`svix-id`/`svix-timestamp`/`svix-signature`), não `Resend-Signature` ou `Webhook-Signature`. Implementação correta espelha o protocolo real.

### Test coverage (AC3)

Arquivo: `backend/tests/test_resend_webhook_signature.py` (8 testes, todos verdes em 2026-05-09):

| Teste | Cenário | Resultado |
|-------|---------|-----------|
| `test_valid_signature_processes_webhook` | Signature correta + body válido | 200 OK ✅ |
| `test_missing_signature_header_rejected` | Sem header `svix-signature` | 401 ✅ |
| `test_missing_secret_rejects_all` | `RESEND_WEBHOOK_SECRET=""` | 401 (fail-closed) ✅ |
| `test_tampered_body_rejected` | Sig assinada para body A, request envia body B | 401 ✅ |
| `test_replay_old_timestamp_rejected` | `svix-timestamp` >5min atrás | 401 (replay protection) ✅ |
| `test_wrong_secret_rejected` | Sig com secret diferente | 401 ✅ |
| `test_multiple_signatures_one_valid` | Header com `v1,sig1 v1,sig2` (rotação de chaves) | 200 OK ✅ |
| `test_trial_emails_webhook_secret_alias` | `TRIAL_EMAILS_WEBHOOK_SECRET` canonical (legacy alias absent) | 200 OK ✅ |

### Conclusão

**Gap-5 já estava fechado.** Esta story é um **audit closeout** — atualiza review-report e fecha #953 com evidência empírica. Nenhuma alteração de código de produção foi necessária.

---

## Acceptance Criteria

### AC1: Audit empírico estado atual

- [x] Read `backend/routes/trial_emails.py` integral
- [x] Documentar fluxo atual (ver tabela acima)
- [x] Output: tabela "atual vs esperado" com gaps identificados — **0 gaps**

### AC2: Implementação enforcement

- [x] **Já implementado em PR #534** (Svix-format HMAC verify, fail-closed, replay protection 5min, constant-time compare)
- [x] Resolução secret: `TRIAL_EMAILS_WEBHOOK_SECRET` canonical (PR #858) com fallback `RESEND_WEBHOOK_SECRET`
- [x] Logging: `logger.warning` com svix-id truncado (sem expor secret)
- [ ] ~~Rate limit em endpoint `/v1/trial-emails/webhook` se 403 rate > 10/min~~ — **Out of scope** desta story; abrir issue separada se sinal de spoofing surgir em telemetria

### AC3: Tests integration

- [x] `backend/tests/test_resend_webhook_signature.py` — 8 testes verdes:
  - [x] Sem signature header → 401
  - [x] Signature tampered/wrong → 401
  - [x] Replay attack → 401 (timestamp tolerance 5min)
  - [x] Body válido + signature válida → 200 + side effects
  - [x] Canonical alias `TRIAL_EMAILS_WEBHOOK_SECRET` aceito
- [x] Mock secret via `monkeypatch.setenv` / `patch.dict(os.environ, ...)`

### AC4: Telemetria + alerta — DEFERRED

- [ ] ~~Métrica `webhook_signature_failures_total{webhook="trial_emails"}` Prometheus~~ — **Defer**: hard scope desta story (PR review-pr) é audit + close, não nova telemetria. Abrir story separada se necessário.
- [ ] ~~Sentry alert: trigger se rate > 5/min sustained 5min~~ — **Defer**: mesma razão.
- [ ] ~~Mixpanel event `webhook_signature_rejected`~~ — **Defer**.

### AC5: Doc + close-out

- [x] Update memory `reference_trial_email_log_delivery_status_null.md` — já reflete PR #534 (state: gap fechado)
- [ ] ~~Update `_reversa_sdd/review-report.md §11.2`~~ — **Defer**: separate doc-pass; review-report já está em modificação por outro fluxo (ver `git status` raiz)
- [ ] ~~Doc `docs/security/webhook-signature-policy.md`~~ — **Defer**: hard scope
- [ ] ~~Runbook `docs/runbooks/webhook-signature-incident.md`~~ — **Defer**: hard scope

---

## DoD

- [x] Audit doc completo (atual vs esperado)
- [x] Enforcement implementado em `routes/trial_emails.py` (já estava — PR #534)
- [x] 8 tests integration green (>5 required)
- [ ] ~~Métrica + alert configurados~~ (deferred)
- [x] memory entry refletindo state real (já estava em sync)
- [ ] ~~Doc policy + runbook publicados~~ (deferred)

---

## Dependências

- PR #534 Done (HMAC verify shipped) — primary
- PR #858 Done (TRIAL_EMAILS_WEBHOOK_SECRET canonical alias)
- Memory `reference_trial_email_log_delivery_status_null.md` (já em sync)

---

## Notes

- Pattern reuse: `backend/webhooks/stripe.py` é referência canonical Stripe; `routes/trial_emails.py::_verify_svix_signature` é canonical Resend/Svix. Pattern aplicável a webhooks futuros (intel-reports?) — replicar Svix se source também usar Svix; Stripe pattern caso contrário.
- **Anti-pattern evitado:** validar HMAC depois de DB writes — implementação atual respeita isso (verify primeiro, raise antes de qualquer business logic).
- Resend webhook docs: https://resend.com/docs/webhooks/verify (confirma uso de Svix protocol).
- Memory `feedback_n2_below_noise_eng_theater`: NÃO se aplica aqui — gap real era percebido, audit confirmou state correto.
