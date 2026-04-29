# SM Briefing — Gaps SmartLic Pós-Auditoria Reversa

> **Origem:** Reversa Reviewer 2026-04-27 (`review-report.md`)
> **Audiência:** @sm (River) para criação/refresh de stories
> **Diretiva:** SEMPRE invocar `Skill(skill: "sm")` antes de criar `.story.md`. Após batch criado, handoff para @po (`*validate-story-draft`).

---

## 1. Reconciliação com stories existentes (625 .story.md em `docs/stories/`)

| Gap (review-report.md) | Story existente | Status | Ação @sm |
|------------------------|-----------------|--------|----------|
| **Gap-5** HMAC Resend webhook | `2026-04/MON-FN-001-resend-webhook-hmac.md` | Ready P0 Sprint 1 | Nenhuma — story existente já cobre AC. Confirme @dev pickup. |
| **Gap-10** service_role `statement_timeout=NULL` | `SEN-BE-001-db-statement-timeout-57014.story.md` | Ready P0 | **Refresh:** confirmar que AC inclui `ALTER ROLE service_role SET statement_timeout='60s'` migration. Se ausente, criar SEN-BE-001b companion. |
| **Gap-1** Org RBAC granular | `2026-04/GV-014-consultoria-client-readonly.md` | Ready conditional Sprint 3 | **Companion novo:** GV-014 trata read-only consultoria mas NÃO enforce enum `owner/member/viewer` em 8 endpoints `routes/organizations.py`. Criar story `RBAC-ORG-001-enforce-org-role-dependency`. |
| **Gap-4** MFA policy | `STORY-317-mfa-totp.md` | MEDIUM Sprint 3 | **Refresh:** falta policy doc (when MFA é enforced — admin/master/consultoria/N-attempts). Bloquear até user responder questões. |
| **Gap-2** Founding canonical | `2026-04/EPIC-REVENUE-2026-Q2/STORY-BIZ-001-founding-customer-stripe-coupon.story.md` | Done | **Companion novo:** doc only — ADR fixar cap/deadline/lifetime pricing. Story `BIZ-FOUND-002-canonical-policy-adr`. |
| **Gap-3** Partner program | `STORY-323-revenue-share-tracking.md` | P1 HIGH Sprint 2 | **Read-full + assess:** se 323 cobre commission %/payout/attribution, sem ação. Caso contrário, companion `PART-001-attribution-rules-spec`. |
| **Gap-6** `estimated_hours_saved = N×2.5h` magic constant | nenhuma | — | **NOVA P2:** instrument time-on-task /buscar→export, n≥30, mover constant para `app_config` table, admin endpoint update. |
| **Gap-8** `cnae_mapping.py` hardcoded | nenhuma | — | **NOVA P2:** migrate para tabela `cnae_setor_mapping`, audit trail, admin endpoint, seed migration mapping atual. |
| **Gap-9** Stripe `plan_billing_periods` sync | `DEBT-017` + `SHIP-004` + `STORY-360` | parcial | **Verify-only:** se webhook handler `product.updated`/`price.updated` não existe em `webhooks/stripe.py`, criar `BILL-SYNC-001`. |
| **Inc-1/4/7** counts inconsistentes (15/20 setores, 49/187 endpoints) | — | **resolvido** | Sem ação — CLAUDE.md + architecture-detail.md atualizados pelo user 2026-04-27. |
| **Inc-3** naming collision `pipeline/` | nenhuma | — | **chore opcional P3:** disambig note em CLAUDE.md + module docstrings. Low ROI; defer salvo confusão real. |

---

## 2. Stories candidatas a criar (3 novas + 2-3 companions condicionais)

### 2.1. P2-NEW — `BIZ-METRIC-001-empirical-hours-saved-calibration`
**Source:** review-report.md Gap-6
**Why:** `analytics/summary` retorna `estimated_hours_saved = total_searches * 2.5h` hardcoded; constante sem base empírica documentada.
**Scope:**
- Instrument `frontend/app/buscar/` start→export time-on-task via Mixpanel
- Coletar n≥30 sessions reais
- Recalibrar constant; documentar metodologia em `docs/methodology/hours-saved-calibration.md`
- Mover constant `analytics.py` → `app_config` table (versionável runtime)
- Admin endpoint `PATCH /v1/admin/config/hours_saved_constant`
**Confidence:** 🟡 (constant atual pode estar correta — só medição confirma)
**Effort:** M (3-4 dias) — depende ramping volume tráfego /buscar

### 2.2. P2-NEW — `DATA-CNAE-001-migrate-cnae-mapping-to-db`
**Source:** review-report.md Gap-8
**Why:** `utils/cnae_mapping.py` hardcoded; cobertura desconhecida; updates exigem deploy.
**Scope:**
- Migration: tabela `cnae_setor_mapping (cnae_code, setor_id, confidence, updated_at, updated_by)`
- Seed: import current `cnae_mapping.py` content
- Refactor `utils/cnae_mapping.py` → query DB com cache LRU 1h
- Admin endpoint `POST /v1/admin/cnae-mapping` (CRUD)
- Tests regression: snapshot mapping atual, garantir 100% match pós-migração
- CHANGELOG documenta CNAEs em "diversos"
**Confidence:** 🟢
**Effort:** M (2-3 dias)

### 2.3. P1-COMPANION (CONDICIONAL) — `RBAC-ORG-001-enforce-org-role-dependency`
**Source:** review-report.md Gap-1 + US-012
**Pré-condição:** user confirma que enum atual é `owner|member|viewer` (ou listar variantes). Caso contrário, story-stub primeiro.
**Why:** 8 endpoints `routes/organizations.py` não enforce roles; trial LGPD + multi-tenant rachado.
**Scope:**
- FastAPI dependency `require_org_role(min_role: OrgRole)` em `dependencies/org_auth.py`
- Apply: invite=owner, accept=invitee, update=owner, delete=owner, list_members=member+, leave=self
- Tests cada combinação role × endpoint (3 roles × 8 endpoints = 24 cases)
- Migration ALTER (se enum diferente atualmente)
**Confidence:** 🟡 (depende confirmação enum)
**Effort:** S (1-2 dias)

### 2.4. P2-COMPANION (CONDICIONAL) — `BIZ-FOUND-002-founding-canonical-policy-adr`
**Source:** review-report.md Gap-2
**Why:** STORY-BIZ-001 (Done) implementou Stripe coupon mas não fixou cap/deadline/lifetime pricing canonical.
**Scope (após user definir N+pricing+deadline):**
- ADR `docs/adr/founding-plan-canonical.md` registrando regras
- Implementar cap enforcement em `POST /v1/founding/checkout` (rejeitar 410 após N seats)
- Add `founding_caps` table com `seat_limit`, `current_seats`, `deadline_at`
- Admin dashboard mostra current seats / limit
**Confidence:** 🔴 (requer user input)
**Effort:** S (1 dia pós-input)

### 2.5. P3-CHORE — `DOC-001-disambig-pipeline-naming`
**Source:** review-report.md Inc-3
**Why:** 3 paths chamados "pipeline" causam confusão em onboarding novo dev:
- `backend/pipeline/` (search sub-pkg: stages, budget, cache_manager)
- `routes/pipeline.py` (kanban CRUD)
- `frontend/app/pipeline/` (UI kanban)
**Scope:**
- Note em CLAUDE.md seção Architecture
- Module-level docstrings nos 3 paths
- README inline em `backend/pipeline/__init__.py`
**Confidence:** 🟢
**Effort:** XS (30min) — defer salvo dor real

---

## 3. Refreshes recomendados (não-criação, validação de scope)

| Story | Verificar se AC inclui |
|-------|-------------------------|
| `SEN-BE-001-db-statement-timeout-57014` | `ALTER ROLE service_role SET statement_timeout='60s'` migration + paired `.down.sql`. Se ausente, criar SEN-BE-001b. |
| `STORY-317-mfa-totp` | Policy doc explícita (quando MFA enforced). Bloquear @dev pickup até user responder: opt-in / smartlic_consultoria mandatory / admin-master mandatory / N-attempts trigger. |
| `STORY-323-revenue-share-tracking` | Commission %, payout cycle, attribution model (last-click vs first-touch). Se ausente, criar `PART-001-attribution-rules`. |
| `DEBT-017` + `SHIP-004` + `STORY-360` | Webhook handler `product.updated`/`price.updated` em `webhooks/stripe.py`. Se ausente, criar `BILL-SYNC-001`. |

---

## 4. Diretivas para @sm em sessão de criação

1. **Ler ANTES de criar:** `_reversa_sdd/{review-report,user-stories,code-spec-matrix,architecture}.md` + esta seção 2.X.
2. **Memory checks obrigatórios:**
   - `feedback_story_discovery_grep_before_implement` — sempre `grep -rli` antes (já feito aqui, mas refazer per story).
   - `feedback_inventory_double_verify` — para escopo, 2 métodos (ls + grep).
3. **Template:** `{epicNum}.{storyNum}.story.md` em `docs/stories/2026-04/EPIC-XXX/` ou root para chores.
4. **Header obrigatório:** Priority (P0/P1/P2/P3), Source link (review-report.md#gap-N), Status=Draft, Confidence flag.
5. **Pré-flight cada story:** check se sobrepõe story existente; se sim, refresh em vez de duplicar.
6. **Após batch:** invocar `Skill(skill: "po")` com `*validate-story-draft` antes de @dev pickup.
7. **NEVER:** criar story de implementação para gap com `🔴 NEEDS USER VALIDATION` — criar story-stub (questões + bloqueio explícito).

---

## 5. Confidence final desta análise

🟢 **80%** — overlap exhaustivamente checado via grep multi-pattern + ls. Riscos residuais:
- Stories antigas com naming não-canônico podem cobrir gaps sem match grep (ex.: gap "MFA policy" pode estar em STORY-XYZ unrelated). Reduzir via `@po *validate-story-draft` — PO faz cross-reference epic context.
- 4 gaps de validação (`founding`, `partner`, `MFA policy`, `RBAC enum`) bloqueados em user input. Não criar stories implementação enquanto questões abertas.

---

## 6. Próximo passo concreto

User decide:
1. **Criar batch P2 NEW (Gap-6 + Gap-8) agora** — 2 stories independent, sem bloqueio
2. **Refreshes primeiro** (validate SEN-BE-001 + STORY-317 + STORY-323 + STORY-360 escopo) — 0 novas stories, só audit
3. **Aguardar respostas user** para gaps `🔴` (founding cap, partner rules, MFA policy, org RBAC enum) — depois batch tudo

Recomendação @sm: **opção 2 → 1 → 3** (audit barato primeiro evita duplicação).
