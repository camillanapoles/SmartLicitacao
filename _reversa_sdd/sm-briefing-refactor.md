# SM Refactor Briefing — Monetização / Percepção de Valor / Operação em Escala

> **Origem:** Reversa orchestrator 2026-04-28 · sucessor de `sm-briefing.md` (gap-driven 2026-04-27)
> **Audiência:** `@sm` (River) — ler ANTES de criar batch novo. `@po` (Pax) — validar via `*validate-story-draft` após criação.
> **Diretiva inegociável:** invocar `Skill(skill: "sm")` antes de qualquer `.story.md`. Após batch criado, `Skill(skill: "po")`.

---

## 1. Contexto + premissas

**Estado SmartLic v0.5 (2026-04-28):**
- Pre-revenue, runway-critical (memory `feedback_n2_below_noise_eng_theater` — n=2 signups 30d, GSC 126 clicks 28d).
- 187 endpoints, 71 routers, 18 módulos auditados Reversa, 964 stories backlog em 17+ epics.
- Estabilidade prod recém-recuperada: incidents 2026-04-23 (Railway rootDir), 2026-04-27 (Stage 1+2 Disk IO cascade), 2026-04-28 (sitemap-4 wedge). PRs #529, #535, #536 fixaram sintomas.

**Escopo deste briefing (confirmado pelo user 2026-04-28):**
- ✅ Refatoração de módulos críticos (god-files, antipatterns, débito de migração).
- ✅ Foundationals destravadores dos 3 eixos (HMAC verify, statement_timeout, idempotency unification — features pequenas alto-ROI).
- ❌ Invenção de features MON-/GV-/PVX- (já cobertas em 67+37+162 stories existentes; reconciliar, não duplicar).
- ❌ Re-execução de agentes Reversa (state=`completo`).

**Critério de ROI** (em ordem decrescente para sequencing):
1. **Estabilidade prod** (evita outage; protege n=2 → n=30 ramp)
2. **Conversão runway** (destrava trial→paid; HMAC, idempotency, paywall correto)
3. **Escalabilidade próxima** (suporta 10x sem reescrita; budget waterfall, dual-cron consolidation)
4. **Qualidade longo prazo** (god-class split, strategy patterns)

**Diretivas user:** briefing único 3 eixos · detalhe médio 10-15 linhas/candidato · AC esboço + dependências.

---

## 2. Síntese executiva — módulo × eixo × pressão × story-coverage

| Módulo / arquivo | LOC | Eixo dominante | Cross-axis | Pressão refator | Story coverage existente |
|------------------|-----|----------------|------------|------------------|--------------------------|
| `backend/admin.py` | 1132 | 1 monetização | 3 escala | ALTA (god) | RES-BE-008 ✓ refresh |
| `backend/pipeline/stages/execute.py` | 1240 | 2 percepção | 3 escala | ALTA (god, blast radius) | RES-BE-005 (parcial) |
| `backend/routes/contratos_publicos.py` | 801 | 2 percepção | — | MÉDIA (god route) | ❌ gap |
| `backend/ingestion/contracts_crawler.py` | 772 | 3 escala | 2 SEO inbound | MÉDIA | ❌ gap |
| `backend/ingestion/crawler.py` | 692 | 3 escala | — | MÉDIA (base abstrata) | ❌ gap |
| `backend/llm_arbiter/classification.py` | 648 | 2 percepção | 1 cost | MÉDIA | ❌ gap |
| `backend/llm.py` | 638 | 2 percepção | — | MÉDIA | ❌ gap |
| `backend/quota/plan_enforcement.py` | 537 | 1 monetização | — | MÉDIA | ❌ gap |
| `backend/datalake_query.py` | 536 | 3 escala | 2 SEO inbound | BAIXA | ❌ gap |
| `backend/routes/analytics.py` | 547 | 1 monetização | 2 percepção | MÉDIA | ❌ gap |
| `routes/sitemap_*.py` (4 files) | 1151 | 3 escala | 2 SEO | MÉDIA (consolidate) | parcial PR #535 |
| `routes/*_publicos.py` (6 files) | 2581 | 2 percepção | 3 antipattern | MÉDIA-ALTA | parcial PR #535 |
| `webhooks/handlers/*.py` (5 files) | 1900 | 1 monetização | — | MÉDIA (idempot.) | story-debt-0-webhook-audit |
| `quota/*` (6 files) | 1810 | 1 monetização | — | MÉDIA (boundaries) | DEBT-201 (filter) ≠ |
| `backend/cron/` (legacy) | 1063 | 3 escala | — | ALTA (dual path) | ❌ gap |
| `backend/jobs/cron/` (modern) | 1684 | 3 escala | — | BAIXA (target) | ❌ gap |
| **Antipattern** `.execute()` em 24 routes async | — | 3 escala | 1+2 (paywall, busca) | **CRÍTICA** (root cause incidents) | parcial PR #535 (6 sitemap) |
| `service_role` `statement_timeout=NULL` | — | 3 escala | — | **CRÍTICA** | SEN-BE-001b ✓ |
| HMAC verify Resend webhook | — | 1 monetização | — | ALTA (security) | MON-FN-001 ✓ |
| Stripe ↔ `plan_billing_periods` bi-sync | — | 1 monetização | — | MÉDIA | DEBT-017+SHIP-004+STORY-360 (parcial); BILL-SYNC-001 sm-briefing.md sec.2.2 |

**Legenda pressão:** CRÍTICA (incident-driver ativo) > ALTA (god/blast) > MÉDIA (débito acumulado) > BAIXA (qualidade).

---

## 3. EIXO MONETIZAÇÃO

### 3.1 Módulos críticos

- **`backend/services/billing.py`** (110 LOC, fino) + **`backend/quota/`** (1810 LOC across 6 files — facade `__init__.py` 113 LOC; `plan_enforcement.py` 537 LOC; `quota_core.py` 376 LOC; `session_tracker.py` 335 LOC; `quota_atomic.py` 271 LOC; `plan_auth.py` 178 LOC).
- **`backend/webhooks/stripe.py`** (253 LOC dispatcher) + **`backend/webhooks/handlers/`** (5 files ~1900 LOC: subscription.py 572, invoice.py 507, checkout.py 351, founding.py + _shared.py).
- **`backend/routes/{billing,founding,subscriptions,conta,trial_extension}.py`** (1310 LOC total).
- **`backend/admin.py`** (1132 LOC, 24 funcs — god-class concentra user CRUD + cache + reconciliation + SLA + trial metrics + at-risk).
- **`backend/jobs/cron/{billing,trial_emails,trial_risk_detection,new_bids_notifier}.py`** (~1100 LOC).

### 3.2 Candidatos detalhados

#### REF-MON-001 — Decompor `admin.py` por domínio
**Eixo:** 1 (cross 3) · **Pressão:** ALTA · **Esforço:** L (5-7d) · **Confidence:** 🟢

**Why:** `backend/admin.py` 1132 LOC, 24 funções públicas (CLAUDE.md confirma); concentra User CRUD (256-644) + Cache (677-797) + Reconciliation (798-856) + Trial metrics (857-1132). Mudanças em qualquer área forçam re-leitura de tudo. RES-BE-008 já criada para esta finalidade — **refresh recomendado, não duplicar**.

**Scope/AC esboço:**
- Split em `backend/admin/users.py`, `backend/admin/billing.py`, `backend/admin/cache.py`, `backend/admin/trial_ops.py`
- Manter `admin.py` como façade re-export (padrão DEBT-302/305/107 já consolidado em quota/, schemas/, jobs/, startup/)
- Mover endpoints `/v1/admin/*` em sub-routers; preservar URLs (zero breaking change)
- Tests: `test_admin_*.py` continuam passando sem alteração imports (façade)

**Dependências:** RES-BE-008 (refresh AC se ainda Draft) · LOC counts (Reversa code-spec-matrix.md)

**Existing overlap:** `RES-BE-008-godmodule-split-admin` → @sm: ler story atual, validar AC inclui sub-router split + façade, atualizar se necessário. NÃO criar nova.

---

#### REF-MON-002 — Stripe webhook idempotency unification
**Eixo:** 1 · **Pressão:** MÉDIA · **Esforço:** M (3-5d) · **Confidence:** 🟢

**Why:** `webhooks/handlers/subscription.py` 572 LOC + `invoice.py` 507 LOC + `checkout.py` 351 LOC + `founding.py` repetem 4 patterns: (1) sig validation, (2) `INSERT ON CONFLICT DO NOTHING` em `stripe_webhook_events`, (3) `invalidate_plan_status_cache(user_id)`, (4) `_activate_plan` flow. `webhooks/stripe.py` (253 LOC) é dispatcher fino — base correta para extrair shared infra. Memory `reference_pr_validation_sections` confirma idempotency é validada em `events_processed`.

**Scope/AC esboço:**
- Criar `backend/webhooks/handlers/_base.py` com `WebhookHandler` ABC: `event_type`, `process(payload, sb)`, `idempotency_key(payload)`
- Migrar 4 handlers para herança ABC (deduplicate sig+idempot+cache-invalidate)
- Decorator `@webhook_handler(event_type="...")` registra em router automaticamente
- Tests: cada handler precisa idempotency test (replay event 2x → 1 efeito)

**Dependências:** stripe_webhook_events table existente · `_shared.resolve_user_id` mantido

**Existing overlap:** `story-debt-0-webhook-audit` (raiz) — ler primeiro. Pode cobrir parcial; complementar se gap.

---

#### REF-MON-003 — Decompor `quota/plan_enforcement.py`
**Eixo:** 1 · **Pressão:** MÉDIA · **Esforço:** M (3-4d) · **Confidence:** 🟢

**Why:** `backend/quota/plan_enforcement.py` 537 LOC concentra `check_quota` multi-layer fallback + `require_active_plan` + cache 2-tier + legacy plan mapping (`get_plan_from_profile`). Boundaries vagas: capabilities lookup misturado com auth gates. quota_core.py 376 já isola `PLAN_CAPABILITIES`; pode receber mais.

**Scope/AC esboço:**
- Extrair `_legacy_plan_mapping` (master→sala_guerra etc.) para `quota/legacy_mapping.py`
- Extrair `_UNKNOWN_PLAN_DEFAULTS` + fallback layering para `quota/fallback_chain.py`
- `plan_enforcement.py` fica só com `check_quota` orchestrator + `require_active_plan` dependency
- Tests: zero regression em `test_quota_*.py`; cobertura nova para legacy mapping isolado

**Dependências:** nenhuma · sem migration · sem schema change

**Existing overlap:** ❌ novo · candidato `EPIC-TD-2026Q2/`

---

#### FOUND-MON-001 — HMAC verify Resend webhook
**Eixo:** 1 · **Pressão:** ALTA (security gap) · **Esforço:** S (1-2d) · **Confidence:** 🟢

**Why:** Memory `reference_trial_email_log_delivery_status_null` confirma: `POST /v1/trial-emails/webhook` aceita sem verify HMAC. CLAUDE.md Security Notes: "HMAC verify on `/trial-emails/webhook` is currently a gap (security TODO)". Sem verify, atacante pode falsificar bounce/complaint events e drenar trial deliverability.

**Scope/AC esboço:**
- Adicionar `RESEND_WEBHOOK_SECRET` env var (Railway bidiq-backend)
- Validar `Resend-Signature` header via HMAC-SHA256
- Retornar 401 se invalid; preservar idempotency em `trial_email_log`
- Tests: assinatura válida (200) + inválida (401) + missing (401) + replay (200, idempotente)

**Dependências:** secret rotation Resend Dashboard · railway env var · nenhuma migration

**Existing overlap:** ✅ `2026-04/MON-FN-001-resend-webhook-hmac.md` — sm-briefing.md original já marcou Ready P0 Sprint 1. **@sm: confirmar @dev pickup, não criar nova.**

---

#### FOUND-MON-002 — Stripe ↔ `plan_billing_periods` bi-directional sync
**Eixo:** 1 · **Pressão:** MÉDIA · **Esforço:** M (3-4d) · **Confidence:** 🟡 (depende auditoria atual)

**Why:** CLAUDE.md: "Source of truth: `plan_billing_periods` table (synced from Stripe)". Mas mecânica de sync não-documentada. Stripe Dashboard tem 9 produtos; alteração de preço lá deve refletir em DB + frontend `usePlan` cache. Gap: handler `product.updated` / `price.updated` em `webhooks/stripe.py`.

**Scope/AC esboço:**
- Audit `webhooks/handlers/` por handlers `product.*` e `price.*`. Se ausentes, criar
- Handler `_handle_product_updated(payload)` → upsert `plan_billing_periods`
- Handler `_handle_price_updated(payload)` → idem + invalidate `_plan_capabilities_cache`
- Cron `jobs/cron/billing.py` adicionar `sync_stripe_pricing` 1×/dia como safety net
- Frontend `useStripeBillingPeriods` com `revalidate` apropriado

**Dependências:** Stripe Dashboard webhook config (adicionar product.updated, price.updated)

**Existing overlap:** ⚠️ ler `DEBT-017`, `SHIP-004`, `STORY-360` antes. sm-briefing.md original sec.2.2.4: criar `BILL-SYNC-001` se gap. **@sm: validar antes de duplicar.**

---

#### REF-MON-004 — `analytics.py` decompose conversion vs usage tracking
**Eixo:** 1 (cross 2 percepção) · **Pressão:** MÉDIA · **Esforço:** M (3-4d) · **Confidence:** 🟢

**Why:** `backend/routes/analytics.py` 547 LOC, 6 endpoints (`/summary`, `/searches-over-time`, `/top-dimensions`, `/trial-value`, `/new-opportunities`, `/track-cta`). Mistura analytics-pessoal-do-user (percepção valor) com tracking-conversão (monetização). Acoplamento dificulta evolução: `track-cta` precisa enviar Mixpanel server-side (memory `project_mixpanel_lib_silent_2026_04_27` confirma 7d silenciado por lib ausente até PR #536) mas é forçado a respeitar contrato user-facing.

**Scope/AC esboço:**
- Split: `routes/analytics_user.py` (user dashboard endpoints) + `routes/analytics_conversion.py` (CTA tracking, trial-value funnel)
- `analytics_conversion.py` tem dependency Mixpanel server-side (lib instalada via #536)
- BIZ-METRIC-001 (sm-briefing.md sec.2.1) dependency: `estimated_hours_saved` constant deve sair de `analytics_user.py` para `app_config` table
- Tests existentes redistribuídos por target

**Dependências:** ✅ Mixpanel lib instalada (PR #536) · BIZ-METRIC-001 (já Ready)

**Existing overlap:** parte cobre `BIZ-METRIC-001-empirical-hours-saved-survey` — refresh AC se necessário

---

#### REF-MON-005 — `routes/{founding,subscriptions,trial_extension,conta}.py` consolidação billing-flows
**Eixo:** 1 · **Pressão:** BAIXA · **Esforço:** S (2-3d) · **Confidence:** 🟢

**Why:** 4 routers fragmentam billing-flows: `founding.py` 239 LOC, `subscriptions.py` 324, `trial_extension.py` 75, `conta.py` 289. Total 927 LOC. Cada um tem padrão: validate plan capability → call services/billing.py → invalidate cache → audit. Boundaries naturais: founding (early-adopter), subscriptions (lifecycle), trial (extensão/cancel), conta (self-service). Razoável. **Refactor BAIXA — preserve current**.

**Scope/AC esboço:**
- Não fazer split (boundary natural OK).
- Apenas extrair `_billing_audit_helper` shared se >2 duplicações em `services/billing.py` ou `_shared.py`.
- ADR `docs/adr/billing-routes-boundary.md` documentando por que não-merge.

**Dependências:** nenhuma

**Existing overlap:** ❌ — chore P3, possível defer

---

#### FOUND-MON-003 — Founding plan canonical policy ADR + cap enforcement
**Eixo:** 1 · **Pressão:** ALTA (deadline 2026-05-30 per state.json) · **Esforço:** S (1d pós-input) · **Confidence:** 🔴 NEEDS USER INPUT

**Why:** review-report.md Gap-2 + sm-briefing.md sec.2.4. STORY-BIZ-001 (Done) implementou Stripe coupon mas sem ADR canonical (cap, deadline, lifetime). Memory state.json `BIZ-FOUND-002 deadline 2026-05-30 (33d)`. Risco: signups acima do cap consomem unit economics negativos.

**Scope/AC esboço (após user definir cap+pricing+deadline):**
- ADR `docs/adr/founding-plan-canonical.md`
- `founding_caps` table com `seat_limit`, `current_seats`, `deadline_at`
- `POST /v1/founding/checkout` rejeita 410 após `seat_limit`
- Admin dashboard `/v1/admin/founding-status` mostra current/limit
- Email automático aos founding members 7d antes deadline

**Dependências:** ⚠️ user input: cap (50? 100?), deadline (2026-05-30?), lifetime price guarantee

**Existing overlap:** ✅ `2026-04/BIZ-FOUND-002-founding-canonical-policy.story.md` — Ready GO 10/10 (state.json). **@sm: validar deadline.**

---

### 3.3 Mapa overlap com epics existentes (eixo monetização)

| Candidato | Epic destino sugerido | Stories existentes para ler antes |
|-----------|------------------------|-------------------------------------|
| REF-MON-001 admin split | EPIC-RES-BE-2026-Q2 | RES-BE-008 |
| REF-MON-002 webhook ABC | EPIC-TD-2026Q2 | story-debt-0-webhook-audit, DEBT-324 (single registration) |
| REF-MON-003 plan_enforcement | EPIC-TD-2026Q2 | DEBT-201, DEBT-323 (bounded LRU) |
| FOUND-MON-001 HMAC | EPIC-MON-FN-2026-Q2 | MON-FN-001 (já Ready) |
| FOUND-MON-002 bi-sync | EPIC-MON-SUBS-2026-04 | DEBT-017, SHIP-004, STORY-360, STORY-277 |
| REF-MON-004 analytics split | EPIC-MON-FN-2026-Q2 | BIZ-METRIC-001 |
| REF-MON-005 billing-flows | EPIC-TD-2026Q2 (P3 chore) | — |
| FOUND-MON-003 founding ADR | EPIC-REVENUE-2026-Q2 | BIZ-FOUND-002, STORY-BIZ-001 |

---

## 4. EIXO PERCEPÇÃO DE VALOR

### 4.1 Módulos críticos

- **`backend/pipeline/`** subpkg 3970 LOC (god-package): `stages/execute.py` 1240 LOC (3 funções gigantes) + `stages/generate.py` 580 + `stages/filter_stage.py` 418 + `cache_manager.py` 358 + `budget.py` + `helpers.py` + `tracing.py` + `worker.py`. Time-to-value depende deste pipeline executar <80s p95.
- **`backend/llm.py`** 638 LOC + **`backend/llm_arbiter/`** 1926 LOC (god-package): `classification.py` 648 + `prompt_builder.py` 378 + `batch_api.py` 276 + `zero_match.py` 289. Exec summaries + classification gating SLA precisão ≥85%, recall ≥70%.
- **`backend/viability.py`** 391 LOC — 4-fator scoring; valor percebido core (LOW/MEDIUM/HIGH no card).
- **`backend/routes/onboarding.py`** 194 LOC + frontend 3-step wizard — TTV <5min via first-analysis dispatch.
- **`backend/routes/pipeline.py`** 496 LOC (kanban CRUD) + `frontend/app/pipeline/`. Retenção surface.
- **`backend/routes/contratos_publicos.py`** 801 LOC (god-route) + outros `*_publicos.py` 6 files = 2581 LOC total. Drive SEO inbound (10k+ pages).

### 4.2 Candidatos detalhados

#### REF-VAL-001 — Decompor `pipeline/stages/execute.py`
**Eixo:** 2 (cross 3) · **Pressão:** ALTA · **Esforço:** L (5-7d) · **Confidence:** 🟢

**Why:** `backend/pipeline/stages/execute.py` 1240 LOC com **apenas 3 funções** (segundo Reversa explore) — sinal forte de funções gigantes (~400 LOC cada). É orchestrator do search pipeline (state machine 11 states); blast radius alto: bug aqui afeta 100% das buscas e portanto TTV percebido. RES-BE-005 cobre split mas relatório explore indica AC genérico — **decompor ainda em sub-módulos por estado**.

**Scope/AC esboço:**
- Identificar os 3 entry-points (provavelmente: `dispatch`, `_run_phase`, `_finalize`)
- Extrair: `pipeline/stages/dispatch.py`, `pipeline/stages/phase_runner.py`, `pipeline/stages/finalize.py`
- Cada novo file <300 LOC; preserve interfaces
- Tests `test_pipeline_*.py` + `test_search_*.py` continuam passando
- Adicionar `test_state_machine_invariants.py` se ainda não existir (state transitions tabela `models/search_state.VALID_TRANSITIONS`)

**Dependências:** state machine (`models/search_state.py`) · time budget (`pipeline/budget.py`)

**Existing overlap:** ✅ `RES-BE-005-godmodule-split-pipeline` + `STORY-3.1-search-py-decomposition` + `DEBT-115-search-route-decomposition`. **@sm: ler 3 e consolidar AC; possível duplicação. Recomendar single story ou explicit dependencies entre elas.**

---

#### REF-VAL-002 — Strategy pattern `llm_arbiter/classification.py`
**Eixo:** 2 (cross 1 LLM cost) · **Pressão:** MÉDIA · **Esforço:** M (3-5d) · **Confidence:** 🟢

**Why:** `backend/llm_arbiter/classification.py` 648 LOC concentra arbiter logic (keyword density tier branching → llm_standard / llm_conservative / llm_zero_match). Adicionar novo tier exige modificar arquivo central. Strategy pattern desacopla; permite A/B test prompts (memória reference_resend_personal_tone_send sugere experimentação ativa).

**Scope/AC esboço:**
- ABC `ClassificationStrategy` em `llm_arbiter/strategies/_base.py`
- Implementar 4 strategies: `keyword.py`, `llm_standard.py`, `llm_conservative.py`, `llm_zero_match.py`
- `classification.py` reduz para router/dispatcher selecionando strategy
- Benchmark precision/recall ≥85%/≥70% por sector mantido (15 samples/sector test)

**Dependências:** prompts ficam em `prompt_builder.py` (já isolado)

**Existing overlap:** ❌ novo · `EPIC-TD-2026Q2/`

---

#### REF-VAL-003 — `routes/contratos_publicos.py` split + base genérica `*_publicos`
**Eixo:** 2 (cross 3 antipattern) · **Pressão:** MÉDIA-ALTA · **Esforço:** L (5-7d) · **Confidence:** 🟢

**Why:** `backend/routes/contratos_publicos.py` 801 LOC, 11 funções — god-route. Os outros `*_publicos.py` (municipios 538, itens 522, compliance 289, dados 282, alertas 149) seguem padrão idêntico fetch→filter→serialize. Total 2581 LOC. Driver SEO orgânico inbound. Memory `project_sitemap_endpoints_wedge_2026_04_27` mostra: TODA classe de endpoints DB-bound estava com mesmo antipattern (sync `.execute()` em handler async sem budget+negative cache). PR #535 fixou 6 sitemap routers; *_publicos ainda residuais.

**Scope/AC esboço:**
- Criar `routes/_publicos_base.py` com `PublicEntityRouter` factory: `(entity_type, fetcher, filter_schema, serializer)` → APIRouter
- Migrar 5 routers menores como instances `PublicEntityRouter(...)` ; reduz total ~600 LOC
- `contratos_publicos.py` split em sub-routes (`/cnpj/{cnpj}`, `/setor/{setor}`, `/agg/...`)
- Aplicar budget + negative cache pattern padrão (memory `project_backend_outage_2026_04_27`)
- Tests `test_observatorio*.py`, `test_seo*.py` continuam passando

**Dependências:** ⚠️ depende REF-SCALE-002 (sync .execute() sweep — section 5) ou aplicar fix junto

**Existing overlap:** parcialmente `EPIC-SEO-PROG-2026-Q2/` (13 stories). @sm: ler para evitar overlap; se já há SEO-PROG focado em routers, refresh AC.

---

#### REF-VAL-004 — Onboarding+first-analysis dispatch refactor
**Eixo:** 2 · **Pressão:** BAIXA · **Esforço:** M (2-3d) · **Confidence:** 🟢

**Why:** `backend/routes/onboarding.py` 194 LOC + frontend 3-step wizard. CLAUDE.md confirma TTV <5min via first-analysis auto-dispatch (GTM-004). Não é god mas o flow tem split: routes/onboarding (CNAE→sector), `utils/cnae_mapping.py` hardcoded (Gap-8 review-report), dispatch via ARQ. Foundationals (DATA-CNAE-001) destravam evolução.

**Scope/AC esboço:**
- DATA-CNAE-001 (sm-briefing.md sec.2.2 Ready GO) precede: `cnae_setor_mapping` table + admin endpoint
- Após DATA-CNAE-001 done: refactor `routes/onboarding.py::first_analysis` para query DB + LRU cache 1h
- Move 3-step wizard state para `frontend/app/onboarding/state.ts` se ainda inline
- E2E Playwright: signup → onboarding 3 steps → /buscar com primeiro resultado <5min

**Dependências:** ✅ `DATA-CNAE-001-migrate-cnae-mapping-to-db` (já Ready)

**Existing overlap:** ❌ novo (companion após DATA-CNAE-001) · `EPIC-TD-2026Q2/` ou `EPIC-PVX-2026-Q3/`

---

#### REF-VAL-005 — `llm.py` 638 LOC decompose summary vs orchestration
**Eixo:** 2 · **Pressão:** MÉDIA · **Esforço:** M (3d) · **Confidence:** 🟢

**Why:** `backend/llm.py` 638 LOC, 6 funções — wrapper LLM monolítico para exec summaries (`gerar_resumo`, `gerar_resumo_fallback`). Bug recente (memory `project_mixpanel_lib_silent`) mostra: `llm.py` ARQ summary jobs depende de fallback path correto. Mistura: client init + fallback constants + prompt + schema (`ResumoLicitacoes`) + retry.

**Scope/AC esboço:**
- Extrair `llm/client.py` (init/retry/cost tracking)
- Extrair `llm/summaries.py` (gerar_resumo + fallback)
- Extrair `llm/prompts/resumo.py` (template + variants)
- Schema `ResumoLicitacoes` permanece em `schemas/search.py` (já lá)
- Tests `test_llm*.py` redistribuídos

**Dependências:** llm_arbiter/ é separado; nenhuma colisão

**Existing overlap:** ❌ novo · `EPIC-TD-2026Q2/`

---

#### REF-VAL-006 — Pipeline kanban dependency cleanup
**Eixo:** 2 · **Pressão:** BAIXA · **Esforço:** S (1-2d) · **Confidence:** 🟢

**Why:** `backend/routes/pipeline.py` 496 LOC, 8 endpoints. Já bem isolado (CRUD + alerts). Inc-3 review-report.md flagged 3 paths chamados "pipeline": `backend/pipeline/` (search subpkg), `routes/pipeline.py` (kanban), `frontend/app/pipeline/` (UI kanban) — confusão onboarding novo dev.

**Scope/AC esboço:**
- Module-level docstrings em 3 paths esclarecendo escopo
- Note em CLAUDE.md Architecture seção
- README inline `backend/pipeline/__init__.py`
- Esforço XS (30min) — defer salvo dor real

**Dependências:** nenhuma

**Existing overlap:** ❌ novo · sm-briefing.md sec.2.5 (DOC-001) já mencionou. **Recomenda-se DEFER a menos que haja relato concreto de confusão.**

---

### 4.3 Mapa overlap com epics existentes (eixo percepção de valor)

| Candidato | Epic destino sugerido | Stories existentes para ler antes |
|-----------|------------------------|-------------------------------------|
| REF-VAL-001 execute.py split | EPIC-RES-BE-2026-Q2 | RES-BE-005, STORY-3.1, DEBT-115 (consolidar antes!) |
| REF-VAL-002 LLM strategy | EPIC-TD-2026Q2 | DEBT-201 (filter-decomposition) |
| REF-VAL-003 *_publicos refactor | EPIC-SEO-PROG-2026-Q2 | EPIC-SEO-ORGANIC, EPIC-MON-SEO |
| REF-VAL-004 onboarding/CNAE-DB | EPIC-PVX-2026-Q3 | DATA-CNAE-001 |
| REF-VAL-005 llm.py split | EPIC-TD-2026Q2 | — |
| REF-VAL-006 pipeline naming docstrings | (chore) | — |

---

## 5. EIXO OPERAÇÃO EM ESCALA

### 5.1 Módulos críticos

- **Antipattern P0**: `.execute()` síncrono em handler async sem `asyncio.to_thread` em **24 routes** (`auth_signup, blog_stats, comparador, compliance_publicos, contratos_publicos, empresa_publica, features, founding, lead_capture, indice_municipal, municipios_publicos, itens_publicos, mfa, observatorio, plans, founding, orgao_publico, sitemap_cnpjs, referral, relatorio, seo_admin, sitemap_licitacoes, sitemap_licitacoes_do_dia, sitemap_orgaos, user`). 11 arquivos usam `to_thread` (parcial). Memory `project_backend_outage_2026_04_27` Stage 2: este antipattern + Googlebot wave saturou perfil-b2g + fornecedor profile.
- **`service_role` `statement_timeout=NULL`** — Memory `reference_supabase_service_role_no_timeout_default`: anon=3s, authenticated=8s, **service_role=NULL**. Backend usa SERVICE_ROLE_KEY → queries ilimitadas → pool exhaustion sob carga.
- **`backend/cron/`** (legacy 1063 LOC, loops asyncio antigos: `_loop`, `cache`, `billing`, `health`, `notifications`, `pncp_status`) **+** **`backend/jobs/cron/`** (modern ARQ 1684 LOC). Dual paths com sobreposição (billing.py em **ambos**!) — confusão + risco execução duplicada.
- **`backend/ingestion/`** 3458 LOC (god-package): `contracts_crawler.py` 772, `crawler.py` 692 (base abstrata pesada), `enricher.py` 460, `scheduler.py` 414, `loader.py` 316, `transformer.py`, `checkpoint.py`, `config.py`. Driver da Layer 1 (ETL `pncp_raw_bids` 1.5M rows + `pncp_supplier_contracts` 2M+ rows).
- **`backend/datalake_query.py`** 536 LOC — builder SQL complexo sem padrão; `search_datalake` RPC <100ms p95.
- **`backend/jobs/queue/`** 978 LOC (config/jobs/search/result_store/redis_pool/pool/worker/definitions). ARQ infra — bem estruturada.
- **`backend/routes/sitemap_*.py`** 4 files 1151 LOC com lógica fetch→filter→format_xml repetida.

### 5.2 Candidatos detalhados

#### FOUND-SCALE-001 — `service_role` `statement_timeout=60s`
**Eixo:** 3 · **Pressão:** **CRÍTICA** (incident-prevention) · **Esforço:** S (1d) · **Confidence:** 🟢

**Why:** Memory `reference_supabase_service_role_no_timeout_default` + review-report.md Gap-10. Backend usa SERVICE_ROLE_KEY → queries ilimitadas. Bloqueador para sobreviver Googlebot wave futura. **Já mitigado parcialmente em prod via dashboard (memory `reference_schema_drift_20260427015000`)** mas migration formal ausente no repo.

**Scope/AC esboço:**
- Migration `supabase/migrations/YYYYMMDDHHMMSS_service_role_statement_timeout.sql`:
  ```sql
  ALTER ROLE service_role SET statement_timeout = '60s';
  ```
- Paired `.down.sql` (STORY-6.2): `ALTER ROLE service_role SET statement_timeout = NULL;`
- Validate via `psql -c "SELECT rolname, rolconfig FROM pg_roles WHERE rolname='service_role';"`
- Schema drift reconciliation: arquivo formaliza estado de prod (memory)

**Dependências:** ✅ schema drift já aplicado em prod 2026-04-27 — esta story só formaliza no repo

**Existing overlap:** ✅ `SEN-BE-001b-service-role-statement-timeout.story.md` Ready GO 10/10 (state.json). **@dev pickup imediato; sem nova story.**

---

#### REF-SCALE-001 — Sync `.execute()` async-handler sweep (24 routes)
**Eixo:** 3 (cross 1+2) · **Pressão:** **CRÍTICA** · **Esforço:** L (5-8d, batched) · **Confidence:** 🟢

**Why:** Confirmed via `grep -lEr 'async def' backend/routes/ | xargs grep -l '\.execute()'` → **24 files**. Memory `project_backend_outage_2026_04_27` Stage 2 root cause + memory `feedback_supabase_disk_io_root_cause_pattern` (3 sintomas convergentes). PR #535 fixou 6 sitemap routers parcialmente. ~18 residuais. Cada um bloqueia event loop sob carga. Sob Googlebot crawl + Disk IO depleted = wedge total (sitemap-4=0 incident).

**Scope/AC esboço (executar em batches de 4-6 routers — pattern memory `feedback_cluster_sweep_pattern`):**
- Batch 1 (sitemap residuais): `sitemap_cnpjs.py`, `sitemap_licitacoes.py`, `sitemap_licitacoes_do_dia.py`, `sitemap_orgaos.py` — verificar se ainda há `.execute()` raw após PR #535
- Batch 2 (publicos críticos drive SEO inbound): `contratos_publicos.py` 801 LOC, `municipios_publicos.py` 538, `itens_publicos.py` 522, `compliance_publicos.py`, `dados_publicos.py`, `alertas_publicos.py`
- Batch 3 (auth+billing surface): `auth_signup.py`, `mfa.py`, `founding.py`, `plans.py`, `user.py`
- Batch 4 (analytics+ops): `blog_stats.py`, `comparador.py`, `empresa_publica.py`, `features.py`, `lead_capture.py`, `indice_municipal.py`, `observatorio.py`, `orgao_publico.py`, `referral.py`, `relatorio.py`, `seo_admin.py`
- Pattern fix: `result = client.table(...).execute()` → `result = await asyncio.to_thread(lambda: client.table(...).execute())` ou usar `await sb_execute(client.table(...))` se helper existe em `supabase_client.py`
- Adicionar regression test: lint rule `no-sync-execute-in-async` (custom ruff plugin) ou `grep` no CI
- Per-batch: deploy + soak 24h → próximo batch

**Dependências:** depois de FOUND-SCALE-001 (statement_timeout) — ordem importa: timeout protege contra runaway durante refactor; sem ele, bug em batch pode wedge prod

**Existing overlap:** parcialmente cobre `EPIC-RES-BE-2026-Q2/` (13 stories — checar quais). PR #535 já abriu antecedente. **@sm: criar epic-level + 4 sub-stories por batch.**

---

#### REF-SCALE-002 — Consolidar dual cron paths (`backend/cron/` legacy → `backend/jobs/cron/` ARQ)
**Eixo:** 3 · **Pressão:** ALTA (débito de migração) · **Esforço:** L (5-7d) · **Confidence:** 🟡 NEEDS USER VALIDATION

**Why:** `backend/cron/` 1063 LOC (loops asyncio antigos `cache`, `billing`, `health`, `notifications`, `pncp_status`, `_loop`) **+** `backend/jobs/cron/` 1684 LOC (ARQ moderno + `cron_monitor`, `pncp_canary`, `seo_snapshot`, `trial_emails`, `trial_risk_detection`, `new_bids_notifier`, `indice_municipal`, `llm_batch_poll`, `session_cleanup`, `scheduler`, `billing`, `notifications`). **Sobreposição: `billing.py` em ambos. `notifications.py` em ambos.** Risco: execução duplicada se ambos rodam. CLAUDE.md menciona "19 lifespan loops + 9 ARQ cron" sem clarificar overlap.

**Scope/AC esboço:**
- Audit cada arquivo de `backend/cron/`: identificar (1) ainda registrado em lifespan loop? (2) feature flag-gated? (3) deprecated?
- Migration plan: cada legacy → ARQ cron equivalente em jobs/cron/
- Remove backend/cron/ APENAS após validação 100% migrado
- ADR `docs/adr/cron-consolidation.md` registrando estratégia
- pg_cron jobs (purge-old-bids, cleanup-search-cache, cleanup-search-store) preservados (CLAUDE.md STORY-1.2)

**Dependências:** ⚠️ user input: existe ADR ou plan parcial? Há feature flag para legacy ON/OFF? Quais jobs são ATUALMENTE ativos via lifespan vs ARQ?

**Existing overlap:** parcial em `EPIC-RES-BE-2026-Q2/`? @sm: investigar. Possível story-stub-com-questões antes de criação plena.

---

#### REF-SCALE-003 — `ingestion/` god-package decomposition
**Eixo:** 3 (cross 2 SEO inbound) · **Pressão:** MÉDIA · **Esforço:** L (5-7d) · **Confidence:** 🟢

**Why:** `backend/ingestion/contracts_crawler.py` 772 + `crawler.py` 692 = 1464 LOC duplicação de pattern (provavelmente). Total ingestion/ 3458 LOC. Drives `pncp_raw_bids` 1.5M rows (400d) + `pncp_supplier_contracts` 2M+ rows. Crawler base abstrata pesada — adicionar nova fonte (PNCP v2 hipotético) é difícil.

**Scope/AC esboço:**
- Identificar duplicação real: diff funcional `contracts_crawler.py` vs `crawler.py` (provável: contracts faz crawl 3×/sem, bids 1×/dia + 3 incrementais)
- Extrair `BaseCrawler` ABC em `ingestion/_base/crawler.py` com `fetch_page`, `transform`, `upsert_batch`, `checkpoint_advance`
- Especialização: `BidsCrawler(BaseCrawler)`, `ContractsCrawler(BaseCrawler)`
- Tests `test_ingestion*.py` cobertura por classe
- Performance: zero regression em latency end-to-end ETL

**Dependências:** nenhuma

**Existing overlap:** ❌ novo · `EPIC-RES-BE-2026-Q2/` ou `EPIC-TD-2026Q2/`

---

#### REF-SCALE-004 — `routes/sitemap_*.py` consolidação via factory
**Eixo:** 3 (cross 2 SEO) · **Pressão:** MÉDIA · **Esforço:** M (3-5d) · **Confidence:** 🟢

**Why:** 4 sitemap routers (cnpjs 357, licitacoes 312, orgaos 298, licitacoes_do_dia 184) totalizando 1151 LOC com pattern fetch→filter→format_xml idêntico. PR #535 fixou antipattern mas não consolidou estrutura. Memory `project_sitemap_endpoints_wedge_2026_04_27` mostra: classe inteira tinha mesmo bug; classe inteira pode ser router-factory.

**Scope/AC esboço:**
- `routes/_sitemap_factory.py::create_sitemap_router(entity, fetcher, urlpattern, lastmod)` → APIRouter
- Converter 4 routers em invocations factory
- Tests `test_sitemap_*.py` consolidados em `test_sitemap_factory.py`
- ISR `revalidate=3600` preservado (memory `project_sitemap_serialize_isr_pattern`)
- Negative cache ativo (memory `feedback_build_hammers_backend_cascade`)

**Dependências:** REF-SCALE-001 batch 1 (sitemap async fix) se ainda residual

**Existing overlap:** parcialmente em `EPIC-SEO-PROG-2026-Q2/`. @sm: confirma overlap.

---

#### FOUND-SCALE-002 — Frontend Sentry SDK silent em build/ISR runtime
**Eixo:** 3 · **Pressão:** ALTA (observabilidade gap) · **Esforço:** M (2-4d) · **Confidence:** 🟡

**Why:** Memory `feedback_frontend_sentry_silent_buildtime` 2026-04-27: 0 events em 24h apesar de sitemap/4=0 confirmado. SDK init em build/ISR runtime suspect. Sem Sentry no SSG, não há detecção precoce de build hammer cascade (memory `feedback_build_hammers_backend_cascade`).

**Scope/AC esboço:**
- Investigar `frontend/sentry.{client,server,edge}.config.ts` e Sentry init em `next.config.js`
- Garantir Sentry SDK init pré-fetch em SSG (build-time) e ISR (runtime)
- Adicionar wrapper `safeFetch(url, options)` que captura SentryException antes de retornar fallback
- Smoke test: força fetch fail em sitemap-4 build → Sentry deve capturar

**Dependências:** Sentry credentials já configurados (memory `reference_sentry_credentials`)

**Existing overlap:** ❌ novo · `EPIC-RES-BE-2026-Q2/`

---

#### REF-SCALE-005 — `datalake_query.py` query builder pattern
**Eixo:** 3 · **Pressão:** BAIXA · **Esforço:** M (3d) · **Confidence:** 🟢

**Why:** `backend/datalake_query.py` 536 LOC builder SQL complexo. Funcionalmente OK (<100ms p95 confirma) mas evolução (adicionar filtro novo) requer modificar arquivo central. Pattern Builder tornaria extensível sem dor.

**Scope/AC esboço:**
- `DatalakeQueryBuilder` class em `datalake/query_builder.py` (.set_uf().set_value_range().set_keywords().build())
- `datalake/rpc_executor.py` chama `search_datalake` RPC
- Tests `test_datalake*.py` cobrem combinações
- Zero regression latency p95 <100ms

**Dependências:** ✅ search_datalake RPC já existe (data-master.md)

**Existing overlap:** ❌ novo · `EPIC-TD-2026Q2/`

---

#### REF-SCALE-006 — `jobs/cron/` boundary clarity (após dual-path consolidation)
**Eixo:** 3 · **Pressão:** BAIXA · **Esforço:** S (2d) · **Confidence:** 🟢

**Why:** `backend/jobs/cron/` 1684 LOC across 14 files já bem organizado por domain. Nada urgente. Pós-consolidação (REF-SCALE-002), revisar overlap entre `cron_monitor.py` (pg_cron health) e `pncp_canary.py` (PNCP breaking change) — ambos têm Sentry alerting; possível shared helper.

**Scope/AC esboço:**
- `jobs/cron/_alerting.py` shared: `sentry_dedup(fingerprint, ttl_redis)`, `sentry_threshold(reason, count, threshold)`
- Migrate `cron_monitor.py` + `pncp_canary.py` para use helper
- Sem mudança comportamental — refactor only

**Dependências:** ⚠️ post-REF-SCALE-002 (ordem)

**Existing overlap:** ❌ novo · P3

---

#### FOUND-SCALE-003 — Negative cache + budget pattern cross-cutting helper
**Eixo:** 3 · **Pressão:** MÉDIA · **Esforço:** M (3-4d) · **Confidence:** 🟢

**Why:** Memory `project_backend_outage_2026_04_27` + `feedback_build_hammers_backend_cascade` + `project_sitemap_endpoints_wedge_2026_04_27` apontam: pattern correto é `try/budget+to_thread+negative_cache_on_db_failure`. Hoje cada rota implementa ad-hoc. PR #529 fixou perfil-b2g + fornecedor; PR #535 fixou 6 sitemaps; mas ~18 routers residuais (REF-SCALE-001) precisam mesmo pattern.

**Scope/AC esboço:**
- Decorator `@with_budget_and_negative_cache(budget_s=10, negative_ttl_s=60)` em `backend/_helpers/resilience.py`
- Aplica `asyncio.timeout()` + cache negativo em Redis (key=route+params, value=503-marker)
- Decorator também integra `to_thread()` automático para `.execute()` calls
- Migrate 4-6 rotas críticas como POC
- Restante migra durante REF-SCALE-001 sweep

**Dependências:** Redis pool existente (`redis_pool.py`) · sintetiza pattern já comprovado em PR #529, #535

**Existing overlap:** parcial em `RES-BE-010-bulkheads`? @sm: ler antes de criar.

---

### 5.3 Mapa overlap com epics existentes (eixo escala)

| Candidato | Epic destino sugerido | Stories existentes para ler antes |
|-----------|------------------------|-------------------------------------|
| FOUND-SCALE-001 service_role timeout | EPIC-RES-BE-2026-Q2 | SEN-BE-001b (Ready) |
| REF-SCALE-001 .execute() sweep | EPIC-RES-BE-2026-Q2 (criar epic-level + 4 batches) | EPIC-INCIDENT-2026-04-22, RES-BE-010 bulkheads |
| REF-SCALE-002 dual cron consolidation | EPIC-RES-BE-2026-Q2 | (gap claro) |
| REF-SCALE-003 ingestion split | EPIC-TD-2026Q2 | DEBT-015, DEBT-07 |
| REF-SCALE-004 sitemap factory | EPIC-SEO-PROG-2026-Q2 | (parcial cobertura) |
| FOUND-SCALE-002 Sentry SSG/ISR | EPIC-RES-BE-2026-Q2 | (gap) |
| REF-SCALE-005 datalake query builder | EPIC-TD-2026Q2 | — |
| REF-SCALE-006 cron alerting helper | EPIC-TD-2026Q2 | (post-REF-SCALE-002) |
| FOUND-SCALE-003 resilience decorator | EPIC-RES-BE-2026-Q2 | RES-BE-010, EPIC-INCIDENT-* |

---

## 6. Cross-axis DAG + ordenação sugerida

```
                                 [FOUND-MON-003 founding ADR 🔴]
                                          (user input gate)
                                                 │
                                                 ▼
[FOUND-SCALE-001 service_role timeout 🟢] (SEN-BE-001b — pickup imediato)
                │
                ├──> [REF-SCALE-001 .execute() sweep CRÍTICA — batches 1..4]
                │           │
                │           ├─> Batch 1 sitemap residuais (24h soak)
                │           ├─> Batch 2 *_publicos critical SEO
                │           ├─> Batch 3 auth+billing surface
                │           └─> Batch 4 analytics+ops
                │                       │
                │                       ▼
                │              [FOUND-SCALE-003 resilience decorator]
                │                       │
                │                       ▼
                │              [REF-SCALE-004 sitemap factory]
                │              [REF-VAL-003 *_publicos refactor]
                │
                ├──> [REF-SCALE-002 dual cron consolidation 🟡 user input gate]
                │           │
                │           ▼
                │   [REF-SCALE-006 cron alerting helper]
                │
                └──> [FOUND-SCALE-002 Sentry SSG/ISR]

[FOUND-MON-001 HMAC verify 🟢] (MON-FN-001 — pickup imediato Sprint 1)
[FOUND-MON-002 Stripe bi-sync 🟡] (audit DEBT-017/SHIP-004/STORY-360 antes)

[REF-MON-001 admin split] (RES-BE-008 refresh)
[REF-MON-002 webhook ABC]
[REF-MON-003 plan_enforcement decompose]
[REF-MON-004 analytics split] ──┐
                                 │
                                 ▼
[REF-VAL-004 onboarding/CNAE-DB] ◄─── [DATA-CNAE-001 Ready]
[BIZ-METRIC-001 Ready] ─────────────────┘

[REF-VAL-001 execute.py split] (consolidar RES-BE-005 + STORY-3.1 + DEBT-115 antes!)
[REF-VAL-002 LLM strategy]
[REF-VAL-005 llm.py split]
[REF-VAL-006 pipeline naming docstrings] (defer P3)

[REF-MON-005 billing-flows] (defer P3)
[REF-SCALE-003 ingestion split]
[REF-SCALE-005 datalake query builder]
```

### Ordenação P0/P1/P2/P3 sugerida (SM/PO finalizam)

**Sprint atual (P0 — runway-protection):**
1. `FOUND-SCALE-001` service_role timeout (SEN-BE-001b — Ready, formalizar migration repo)
2. `FOUND-MON-001` HMAC verify (MON-FN-001 — Ready)
3. `REF-SCALE-001` Batch 1 sitemap residuais (verificar pós-#535)

**Sprint+1 (P0/P1 — incident-prevention):**
4. `REF-SCALE-001` Batch 2 *_publicos critical SEO inbound
5. `FOUND-SCALE-003` resilience decorator
6. `FOUND-SCALE-002` Sentry SSG/ISR investigation

**Sprint+2 (P1 — runway-conversion):**
7. `FOUND-MON-003` founding ADR (após user input — deadline 2026-05-30!)
8. `FOUND-MON-002` Stripe bi-sync (audit DEBT-017+SHIP-004+STORY-360 antes)
9. `REF-SCALE-001` Batch 3+4 (auth+billing+analytics+ops)
10. `REF-MON-001` admin split (RES-BE-008 refresh)

**Sprint+3 (P1/P2 — qualidade médio prazo):**
11. `REF-VAL-001` execute.py split (consolidar 3 stories antes!)
12. `REF-SCALE-002` dual cron consolidation (após user input strategy)
13. `REF-SCALE-004` sitemap factory + `REF-VAL-003` *_publicos
14. `REF-MON-002` webhook ABC + `REF-MON-003` plan_enforcement decompose

**Backlog (P2/P3):**
15. `REF-VAL-002` LLM strategy + `REF-VAL-005` llm.py split
16. `REF-VAL-004` onboarding/CNAE-DB
17. `REF-MON-004` analytics split
18. `REF-SCALE-003` ingestion split + `REF-SCALE-005` datalake query builder + `REF-SCALE-006` cron alerting helper
19. `REF-MON-005` billing-flows + `REF-VAL-006` pipeline naming (defer salvo dor)

---

## 7. Diretivas SM (operação batch creation)

**Pré-flight cada story (memory checks obrigatórios):**

1. **`feedback_story_discovery_grep_before_implement`** — sempre `grep -rli "<keyword>" docs/stories/` ANTES; stories multi-rota >7d frequentemente parcial-implementadas.
2. **`feedback_inventory_double_verify`** — escopo crítico: 2 métodos independentes (`ls` + `grep` + `find`).
3. **`feedback_audit_env_vars_after_incident`** — para FOUND-* tocando env vars: `railway variables --service bidiq-backend --kv | grep <VAR>`.
4. **`reference_pr_validation_sections`** — body PR final precisa ## Summary, ## Testing Plan, ## Closes.

**Convenção de naming:**

- Refatoração: `REF-{AXIS}-{NNN}-<slug>.story.md`
- Foundationals: `FOUND-{AXIS}-{NNN}-<slug>.story.md`
- AXIS = `MON` | `VAL` | `SCALE`
- Localização: `docs/stories/2026-04/{epic-folder}/`

**Epic placement:**

- Refactor escala/incident-driven → `EPIC-RES-BE-2026-Q2/`
- Refactor débito técnico → `EPIC-TD-2026Q2/`
- Foundationals monetização → `EPIC-MON-FN-2026-Q2/` ou `EPIC-MON-SUBS-2026-04/` ou `EPIC-REVENUE-2026-Q2/`
- Foundationals percepção (CNAE, hours-saved) → `EPIC-PVX-2026-Q3/`
- SEO programmatic → `EPIC-SEO-PROG-2026-Q2/`

**NÃO criar epic novo** — todas as stories deste briefing têm epic destino confirmado.

**Skill chain:**

```
Skill(skill: "sm") *create-next-story → review-report.md + sm-briefing-refactor.md sec.{N}
                                          ↓
                                  story.md draft (Status=Draft)
                                          ↓
                                  Skill(skill: "po") *validate-story-draft
                                          ↓
                                  GO → Status=Ready → @dev pickup
```

**Bloqueio explícito 🔴 NEEDS USER VALIDATION:**

- `FOUND-MON-003` founding ADR — cap, deadline, lifetime price guarantee
- `REF-SCALE-002` dual cron consolidation — strategy ADR (deprecate vs run-both vs feature-flag)

Para essas, criar **story-stub** (questões + bloqueio explícito + estimativa pós-input) — não implementação plena.

**Nunca:**

- Criar `.story.md` SEM invocar `Skill(skill: "sm")` antes (CLAUDE.md NEVER rule).
- Duplicar story existente — sempre check overlap section 3.3, 4.3, 5.3 deste briefing.
- Inventar candidato fora dos 18 deste briefing — escopo confirmado pelo user.

---

## 8. Confidence flags + lacunas pendentes user-validation

**Confidence overall:** 🟢 **85%**

**Discriminadores empíricos confirmados:**
- 24 routes async `.execute()` antipattern: `grep` validated.
- LOC counts confirmados via `wc -l` (Reversa explore agent 2).
- Existing stories backlog inventoried: 17+ epics, 15 refactor-explicit stories cited by name.
- Recent incidents: 3 memories (`project_backend_outage_2026_04_27`, `feedback_supabase_disk_io_root_cause_pattern`, `project_sitemap_endpoints_wedge_2026_04_27`) confirmam pattern.

**Lacunas para user validar antes de SM operacionalizar:**

| ID | Lacuna | Impacto |
|----|--------|---------|
| L-1 | `FOUND-MON-003` founding cap + deadline + lifetime price | bloqueia BIZ-FOUND-002 implementation; deadline 2026-05-30 |
| L-2 | `REF-SCALE-002` dual cron strategy: deprecate legacy / run-both / feature-flag? | bloqueia consolidation work |
| L-3 | `REF-VAL-001` consolidar RES-BE-005 + STORY-3.1 + DEBT-115 — qual é canonical? | possível duplicação; @sm validate |
| L-4 | `FOUND-MON-002` Stripe bi-sync — DEBT-017+SHIP-004+STORY-360 cobrem por completo? | possível BILL-SYNC-001 já desnecessária |
| L-5 | EPIC-REVENUE-2026-Q2 vs EPIC-MON-SUBS-2026-04 — ambas têm stories billing-related; qual epic destino? | placement ambíguo |

**Não-discriminadores (precisariam re-leitura mais profunda — defer):**
- 11 routers usam `to_thread`; quais dos 24 com `.execute()` overlap (parcial fix vs zero fix)? Per-batch grep durante REF-SCALE-001.
- `webhooks/handlers/*.py` LOC counts (3 com `?` em code-analysis).
- `cron/` legacy: cada arquivo é ainda registered em lifespan loop ou deprecated?

**Próximo passo concreto recomendado:**

@sm pickup ordem:
1. **Refresh** SEN-BE-001b + MON-FN-001 + DATA-CNAE-001 + BIZ-METRIC-001 + BIZ-FOUND-002 — confirmar AC + status atualizado.
2. **Audit** STORY-360, DEBT-017, SHIP-004, RES-BE-005, RES-BE-008, STORY-3.1, DEBT-115 — ler conteúdo + decidir refresh vs nova vs consolidação.
3. **Criar batch P0 Sprint atual** (3 stories): `REF-SCALE-001-batch1-sitemap-residuais`, formalize `SEN-BE-001b` migration repo, implement MON-FN-001.
4. **Bloquear** L-1, L-2 até user input — story-stub com questões.
5. **Handoff @po** após batch criado — `*validate-story-draft` cada uma.

---

**Ready para SM consumption.** Briefing exhaustivamente cross-referenced com `_reversa_sdd/{review-report,code-spec-matrix,user-stories,architecture,code-analysis,data-master,sm-briefing}.md` + 964 stories backlog + 30+ memory entries.
