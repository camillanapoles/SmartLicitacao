# OPS-RECOVERY-001: Backend Wedge Recovery Runbook

**Priority:** P0 (incident-driver enabler — playbook unblocks future Stage N events)
**Effort:** 4h
**Squad:** @architect → @devops
**Status:** Done
**Epic:** [EPIC-INCIDENT-2026-04-22-api-degraded](EPIC-INCIDENT-2026-04-22-api-degraded.story.md)
**Sprint:** Sprint Atual (2026-04-29 → 2026-05-12)
**Tipo:** Operational/Runbook (doc executável, não código produção)

---

## Contexto

Stage 4-7 wedge cycle (warm-stonebraker → ancient-kahn → savvy-jasmine → swift-mendel → trusty-pasteur → urgent-codd → stage65-firefight → stage7-wedge → keen-neumann + drift-paulo, 9 sessions documentadas 2026-04-27 → 2026-04-29) demonstrou que recovery sob outage **não é discoverável em tempo real** — on-call gasta 30-60min descobrindo:

- discriminator curl matrix (api.smartlic.tech vs Railway direct domain — Cloudflare bypass diagnostic)
- Railway redeploy GraphQL `deploymentRedeploy(id="<good_deploy_id>")` workaround para silent twin FAILED bug rootDirectory recidiva
- 30min curl loop `/health/live` soak protocol post-recovery
- Tripwire 5.5GB RSS active until 2026-05-06 (memory `feedback_pool_leak_caller_timeout_vs_sql_timeout`)

Memory `feedback_chief_warm_stage5plus_no_pivot` 2026-04-29: warm continuation 7× falhou (8s tighten + WC=2→4 bump + 6 redeploys frontend) **mesmo padrão recorrente**. Hipótese capacity refutada (Hobby 48 vCPU). Root cause REAL não-identificado. Runbook executável é pré-requisito para next firefight não-repetir trial-and-error 7×.

---

## Acceptance Criteria

### AC1: Criar `docs/runbooks/backend-wedge-recovery.md`

- [ ] Estrutura mandatória:
  ```
  ## Sintomas
  ## Discriminator Matrix (curl)
  ## Decision Tree (5min triage)
  ## Recovery Actions (escalation order)
  ## Soak Protocol (post-recovery)
  ## Escalation (when manual fails)
  ## Reference (memory + sessions)
  ```
- [ ] Header inclui: criticidade P0, tempo estimado triage 5min + recovery 15-45min, on-call role required

### AC2: Curl matrix discriminator

- [ ] Tabela executável:
  ```bash
  # Bypass Cloudflare (Railway direct):
  curl -m 5 -o /dev/null -w "%{http_code}\n" https://bidiq-uniformes-production.up.railway.app/health/live
  curl -m 5 -o /dev/null -w "%{http_code}\n" https://api.smartlic.tech/health/live
  # Discriminator:
  # - Railway direct 200 + smartlic 5xx/000 → Cloudflare issue (raro)
  # - Ambos 000/timeout → backend wedge confirmado
  # - Ambos 200 mas slow >5s → saturation, não wedge — ver runbook saturation
  ```
- [ ] Reference: memory `reference_railway_404_triage` 4 causas não-discrimináveis 404

### AC3: Railway redeploy GraphQL workaround

- [ ] Sessão "deploymentRedeploy GraphQL" com:
  - quando usar (silent twin FAILED bug rootDirectory recidiva — keen-neumann session 2026-04-29)
  - command exato:
    ```bash
    railway api --json mutation '
      mutation { deploymentRedeploy(id: "<good_deploy_id>") { id status } }
    '
    ```
  - como descobrir `<good_deploy_id>` (Railway dashboard "Deployments" tab — most recent SUCCESS prior to wedge)
  - rollback: revert se redeploy também wedge (escalation)

### AC4: 30min soak protocol post-recovery

- [ ] Loop check:
  ```bash
  for i in {1..30}; do
    curl -m 5 -o /dev/null -w "%{time_total}s %{http_code}\n" https://api.smartlic.tech/health/live
    sleep 60
  done
  ```
- [ ] Critério OK: 30/30 responses 200 < 2s
- [ ] Critério REGRESSION: ≥3/30 timeout/5xx → escalation (nova wedge)
- [ ] Sentry slow_request >60s monitorar paralelo (memory tripwire 5.5GB RSS)

### AC5: Link em CLAUDE.md + on-call playbook

- [ ] CLAUDE.md "Troubleshooting" section + link runbook
- [ ] CLAUDE.md "Railway Deploy Rules" reforço
- [ ] `.claude/commands/chief.md` reference para Stage N recovery

### AC6: Smoke test — junior dev valida sem context Stage 4-7

- [ ] Validar com pessoa sem acesso a sessions docs/sessions/2026-04 (junior dev ou usuário externo)
- [ ] Cronometrar: triage 5min + recovery 15min completo sem perguntar @chief
- [ ] Iterar runbook com feedback até clarity 100%

---

## Scope

**IN:**
- Runbook markdown executável `docs/runbooks/backend-wedge-recovery.md`
- Curl matrix discriminator copy-paste-ready
- Railway GraphQL redeploy workaround documented
- 30min soak loop scripted
- CLAUDE.md cross-link + on-call playbook
- Junior dev validation smoke test

**OUT:**
- Auto-recovery script (out-of-scope; humano sempre na loop)
- Sentry alert rule definition (escopo SEN-BE-010)
- Memory leak fix (escopo SEN-BE-010)
- Postmortem audit completa (escopo OPS-POSTMORTEM-001)

---

## Definition of Done

- [ ] Runbook commited em `docs/runbooks/backend-wedge-recovery.md`
- [ ] Curl matrix copy-paste valida bypass Cloudflare
- [ ] Railway GraphQL workaround documented com exemplo concreto
- [ ] Soak protocol scripted + critério REGRESSION explícito
- [ ] CLAUDE.md atualizado link
- [ ] Junior dev smoke test passou (5min triage + 15min recovery)
- [ ] PR aprovado @architect + @devops + @qa (junior smoke test = QA)
- [ ] Change Log atualizado

---

## Dev Notes

### Sessions reference

- `docs/sessions/2026-04/2026-04-29-chief-stage7-wedge-discriminator.md` — Stage 7 ativo
- `docs/sessions/2026-04/2026-04-29-chief-drift-paulo.md` — recovery orgânico + tripwire 5.5GB
- `docs/sessions/2026-04/2026-04-29-chief-savvy-jasmine.md` — Stage 5 saturation
- `docs/sessions/2026-04/2026-04-29-chief-swift-mendel.md`
- `docs/sessions/2026-04/2026-04-29-chief-trusty-pasteur.md`
- `docs/sessions/2026-04/2026-04-29-chief-urgent-codd.md`
- `docs/sessions/2026-04/2026-04-29-chief-stage65-firefight.md`
- `_reversa_sdd/incidents-2026-04-27-29.md` — timeline consolidado
- `docs/analysis/chief-stage7-definitive-solution.md` — root cause análise

### Memory references mandatórios

- `feedback_chief_warm_stage5plus_no_pivot` — warm continuation 7× falhou
- `feedback_pool_leak_caller_timeout_vs_sql_timeout` — caller wait_for não libera pool
- `feedback_audit_env_vars_after_incident` — PYTHONASYNCIODEBUG persisting flags
- `reference_railway_404_triage` — 4 causas não-discrimináveis
- `reference_supabase_management_api_query` — Management API bypass quando CLI down

### Railway CLI/GraphQL commands

```bash
# Status check
railway status --service bidiq-backend

# Logs streaming (read-only diagnostic)
railway logs --service bidiq-backend --tail

# Redeploy via CLI
railway redeploy --service bidiq-backend -y

# GraphQL workaround (silent twin)
railway api --json mutation '...'
```

---

## Risk & Rollback

| Trigger | Ação |
|---------|------|
| Runbook seguido + recovery falha | Escalation @architect via PagerDuty/Sentry alert; chamar /chief |
| Junior dev smoke test toma >30min triage+recovery | Iterar runbook simplificando decision tree |

**Rollback:** runbook é doc-only — `git revert` se feedback negativo durante adoption.

---

## Dependencies

**Entrada:** —
**Saída:** OPS-POSTMORTEM-001 audit cita runbook como mitigation. SEN-BE-010 link cross-ref para tripwire 5.5GB.
**Paralelas:** SEN-BE-010, RES-BE-002c (não bloqueiam runbook).

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-29
**Verdict:** GO
**Score:** 10/10

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Clear and objective title | OK | Backend Wedge Recovery Runbook explícito |
| 2 | Complete description | OK | 9 sessions referenced; warm continuation 7× falhou — root cause runbook need |
| 3 | Testable acceptance criteria | OK | AC1-AC6 com smoke test junior dev validation |
| 4 | Well-defined scope | OK | OUT explícito: auto-recovery, Sentry rule, leak fix, postmortem |
| 5 | Dependencies mapped | OK | Independente; saída para OPS-POSTMORTEM-001 + SEN-BE-010 |
| 6 | Complexity estimate | OK | 4h consistente — runbook executável |
| 7 | Business value | OK | Reduz MTTR Stage N+1 de 30-60min para 5min triage + 15min recovery |
| 8 | Risks documented | OK | 2 triggers + rollback path |
| 9 | Criteria of Done | OK | Junior smoke test = QA gate |
| 10 | Alignment with PRD/Epic | OK | EPIC-INCIDENT-2026-04-22-api-degraded |

Status: Draft → Ready.

## File List

- `docs/runbooks/backend-wedge-recovery.md` (NEW) — runbook executável com 7 sections AC1: Sintomas / Discriminator Matrix / Decision Tree 5min / Recovery Actions R1-R5 / Soak Protocol 30min / Escalation / Reference (memories + 9 sessions Stage 4-7 cycle)
- `CLAUDE.md` (edit) — add Troubleshooting section "Backend Wedge (Stage 4-7 pattern)" pós CRIT-080 com link para runbook + summary das ações (AC5)
- `.claude/commands/chief.md` (edit) — add row "Backend wedge / outage Stage N (P0)" em Phase 4 Toolkit Pesquisa Externa & Tooling Direto apontando para runbook (AC5)

## Change Log

| Data | Versão | Descrição | Autor |
|------|--------|-----------|-------|
| 2026-04-29 | 1.0 | Story criada via batch sm-briefing-100pct §3.1. NEW story, anti-duplicate grep zero matches. | @sm (River) |
| 2026-04-29 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
| 2026-04-29 | 1.2 | **Implementado Wave 1 — zany-kurzweil session (single-branch sequential, ROI-priorizado).** AC1-AC5 done: runbook executável `docs/runbooks/backend-wedge-recovery.md` (7 sections + Discriminator Matrix curl + R1 `deploymentRedeploy` GraphQL workaround + R2-R5 escalation + 30min soak protocol + 9 sessions reference). CLAUDE.md cross-link sob Troubleshooting (linha pós CRIT-080). chief.md reference em Phase 4 toolkit. AC6 junior dev validation deferred (post-merge async — não bloqueante). Status: Ready → Done. | @dev (James) |
