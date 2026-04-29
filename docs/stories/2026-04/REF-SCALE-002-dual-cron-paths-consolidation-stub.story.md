# REF-SCALE-002: Dual Cron Paths Consolidation — STUB (BLOQUEADA NEEDS USER INPUT)

**Priority:** P1 (após user input)
**Effort:** L (5-7 dias) — estimativa pós-input
**Squad:** @architect + @dev + @data-engineer
**Status:** Ready
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** TBD (após user decision)
**Dependências bloqueadoras:** ADR strategy decision (USER)

---

## Contexto

Backend tem **2 paths de cron simultâneos**:

1. `backend/cron/` (legacy 1063 LOC, asyncio loops antigos): `_loop`, `cache`, `billing`, `health`, `notifications`, `pncp_status`
2. `backend/jobs/cron/` (modern ARQ 1684 LOC): `cron_monitor`, `pncp_canary`, `seo_snapshot`, `trial_emails`, `trial_risk_detection`, `new_bids_notifier`, `indice_municipal`, `llm_batch_poll`, `session_cleanup`, `scheduler`, `billing`, `notifications`

**Sobreposição confirmada:** `billing.py` em **ambos**. `notifications.py` em **ambos**. Risco execução duplicada se ambos rodam simultaneamente.

CLAUDE.md menciona "19 lifespan loops + 9 ARQ cron" sem clarificar overlap. Esta story bloqueada até user definir strategy.

---

## User Input — RESPONDIDO 2026-04-28

| # | Pergunta | Resposta |
|---|----------|----------|
| Q1 | Path canonical | **`jobs/cron/` ARQ-modern** (Redis distributed locks, structured worker, 14 files) |
| Q2 | ADR existente | Não — criado agora `docs/adr/cron-consolidation.md` |
| Q3 | Status legacy/modern (audit prelim 2026-04-28) | `cron/cache.py` 42L: **ATIVO** via cron_jobs façade · `cron/billing.py` 351L: **uncertain** (need confirm) · `cron/notifications.py` 357L: **ORPHAN provavelmente** (cron_jobs importa de jobs/cron/notifications) · `cron/_loop.py` 113L + `cron/health.py` 88L + `cron/pncp_status.py` 45L: **uncertain** |
| Q4 | Feature flag | **Não existe** (verificado em feature_flags.py + grep) |
| Q5 | Timeline | **Audit (1d) → deprecate-warn 30d → hard remove** (soft transition) |

Detalhes audit em ADR `docs/adr/cron-consolidation.md` (criado). Q3 audit completa será AC0 da implementação.

---

---

## Pre-conditions to validate (independente de user input — pode rodar agora)

- [ ] Audit cada arquivo de `backend/cron/`:
  - Status: ainda registrado em lifespan loop em `startup/lifespan.py`?
  - Feature flag-gated?
  - Logs prod last 7d: rodou efetivamente?
  - Output esperado vs `jobs/cron/` equivalent?
- [ ] Output em `docs/audit/dual-cron-status.md` (read-only audit)
- [ ] **Esta audit pode iniciar ANTES de user input** — informa Q3.

---

## Acceptance Criteria (pós-user input — esboço)

### AC1: ADR strategy

- [ ] `docs/adr/cron-consolidation.md` registra: canonical path (Q1), strategy timeline (Q5)

### AC2: Audit report

- [ ] `docs/audit/dual-cron-status.md` mapeia 12 arquivos com colunas: file, ACTIVE_lifespan, ACTIVE_arq, last_run_prod_log, equivalent_in_other_path, action

### AC3: Migration plan execution (depende Q1)

**Cenário Q1=(a) jobs/cron canonical:**
- [ ] Cada arquivo `cron/` migra equivalência para `jobs/cron/` (se não existe)
- [ ] Remove registration `startup/lifespan.py` para legacy loops
- [ ] After validation 7d soak: delete `cron/` legacy files
- [ ] pg_cron jobs (purge-old-bids, cleanup-search-cache) preservados (CLAUDE.md STORY-1.2)

**Cenário Q1=(b) cron/ legacy preserved:**
- [ ] Inverso: `jobs/cron/` migra para legacy paradigm (não recomendado — ARQ + Redis distributed locks são superiores)

**Cenário Q1=(c) coexist:**
- [ ] Feature flag `USE_LEGACY_CRON=false` (default modern) gate
- [ ] ADR documenta condição para flip

### AC4: pg_cron monitoring (CLAUDE.md STORY-1.1)

- [ ] `cron_job_health` view + `get_cron_health()` RPC continuam funcionando
- [ ] `cron_monitoring_job` ARQ cron continua reportando Sentry para failed/stale

### AC5: Tests

- [ ] Per-cron: test que verifica registration in canonical path APENAS (não duplicada)
- [ ] Smoke prod: pós-deploy, query Sentry/logs por execuções duplicadas

---

## Scope

**IN:** ADR + audit report + migration per Q1 chosen + tests + soak validation
**OUT:** New cron jobs (escopo separate) · pg_cron native rewrite (separate)

---

## Definition of Done (pós-user input)

- [ ] User Q1-Q5 respondidas em ADR
- [ ] Audit report criado
- [ ] Migration plan executado per Q1
- [ ] 7d soak window sem execução duplicada
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `backend/cron/` 1063 LOC inventory: 6 files
- `backend/jobs/cron/` 1684 LOC inventory: 14 files
- `backend/startup/lifespan.py` — registration legacy loops
- `backend/jobs/queue/config.py:WorkerSettings.functions` — registration ARQ
- Memory `reference_supabase_management_api_query` para queries Supabase ad-hoc durante audit

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Migration deleta cron crítico em prod | Pre-soak 7d + Sentry alarms; rollback via revert + re-register |
| pg_cron e jobs/cron e cron/ overlap em billing-related | ADR explicita ownership; one canonical |
| User input mudando strategy mid-flight | Re-validate ACs + Change Log entry |

**Rollback:** revert migration commits; legacy paths restaurados.

---

## Dependencies

**Entrada:** User Q1-Q5 · audit report (pode rodar antes)
**Saída:** habilita REF-SCALE-006 cron alerting helper (post-consolidation)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 9/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Dual cron consolidation explícito. |
| 2 | Complete description | ✓ | Q1-Q5 respondidos + audit prelim documentado. |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com per-cron registration test + 7d soak. |
| 4 | Well-defined scope | ✗ | Q3 audit final (per-file ATIVO/INATIVO) ainda pendente — AC0 da implementação cobrirá. Não-blocker para Ready. |
| 5 | Dependencies mapped | ✓ | ADR criado. |
| 6 | Complexity estimate | ✓ | L (5-7d). |
| 7 | Business value | ✓ | Memory `feedback_supabase_disk_io_root_cause_pattern` confirma 4×18 cron tasks startup saturation prevention. |
| 8 | Risks documented | ✓ | Pre-soak 7d + Sentry alarms. |
| 9 | Criteria of Done | ✓ | 6 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-RES-BE-2026-Q2. |

### Required Fix (não-blocker)

- [ ] AC0 (Phase 0) audit completo: confirma per-file Q3a-d ATIVO/INATIVO via psql logs prod last 7d ANTES de PR 1.

Status: Blocked → Ready (com Phase 0 audit gate).

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada como STUB — bloqueada user input Q1-Q5. Audit (AC pre-condition) pode iniciar imediato. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-SCALE-002. | @sm (River) |
| 2026-04-28 | 1.1 | User input Q1-Q5 respondidas: jobs/cron canonical, audit→deprecate-warn 30d→remove, sem feature flag, audit prelim mostra cron/cache ATIVO + cron/notifications provavelmente ORPHAN. ADR `docs/adr/cron-consolidation.md` criado. PO validation: GO (9/10) com Phase 0 audit Required Fix. Status: Blocked → Ready. | @po (Pax) |
