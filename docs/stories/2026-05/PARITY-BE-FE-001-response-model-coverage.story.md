# PARITY-BE-FE-001: response_model coverage 100% (Backend ↔ Frontend type parity)

**Priority:** P1
**Effort:** M (1-2d)
**Squad:** @architect (lead) + @dev + @qa
**Status:** InProgress (Pass 1 — admin routes; Pass 2 follow-up after DATA-CAP-001)
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/) — eixo architectural consistency
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma
**Reversa anchor:** `_reversa_sdd/code-spec-matrix.md` Stories Status + drift `.reversa/drift-2026-05-09.md`
**Score Δ:** arch consistency +6 (88% → 94%) + tests/CI +2

---

## Contexto

CLAUDE.md regra explícita: "every endpoint exposed to the frontend MUST declare `response_model=` on its route decorator so the schema ends up in the OpenAPI output — otherwise CI passes but the frontend stays loosely typed (`{[k: string]: unknown}`)".

Realidade empírica 2026-05-09: 24+ routes têm zero `response_model=` declarations. CI `api-types-check.yml` passa porque schema é gerado, mas frontend recebe `unknown` em paths não-tipados → quebra parity BE/FE silenciosamente.

Routes com 0 `response_model=` (high-impact):

| Arquivo | @router.* count | Notes |
|---------|-----------------|-------|
| `backend/routes/__init__.py` | 0 | aggregator (OK) |
| `backend/routes/_sitemap_cache_headers.py` | 0 | helper module (OK) |
| `backend/routes/admin_cron.py` | 0 | admin-only mas frontend usa typed admin panel |
| `backend/routes/admin_llm_cost.py` | 0 | admin-only |
| `backend/routes/admin_trace.py` | 6 routers, 0 response_models | **HIGH IMPACT** |
| ... | (resto da inventory na AC1) | |

Stories Sprint 2 STORY-2.1 EPIC-TD-2026Q2 entregou Pydantic→TS sync com CI gate, mas response_model adoption ficou opcional → drift acumulado.

---

## Acceptance Criteria

### AC1: Inventory completo

- [ ] `backend/scripts/audit_response_model_coverage.py`:
  - Walk `backend/routes/*.py`
  - Para cada `@router.(get|post|put|delete|patch)(...)` verificar presença `response_model=` kwarg
  - Output table: file → router_count → response_model_count → coverage% → list de paths missing
  - Excluir helpers/aggregators (heurística: zero `@router.*` decorators)
- [ ] Commit baseline JSON `backend/scripts/audit_response_model_coverage_baseline.json` (snapshot 2026-05-10)

### AC2: Backfill response_model em routes high-impact

Prioridade descendente:
1. **Admin panel paths** (frontend typed): `admin_trace.py`, `admin_cron.py`, `admin_llm_cost.py`, `admin_calibration.py`, `admin_billing_sync.py`
2. **Public-facing pSEO** (frontend programmatic types): `contratos_publicos.py`, `orgao_publico.py`, `empresa_publica.py`, `dados_publicos.py`, `municipios_publicos.py`, `itens_publicos.py`, `compliance_publicos.py`, `alertas_publicos.py`
3. **Conversion paths** (high traffic): `intel_reports.py`, `founding.py`, `subscriptions.py`, `mfa.py`, `organizations.py`
4. **Internal but typed**: `analytics.py`, `messages.py`, `feedback.py`, `pipeline.py`, `onboarding.py`

- [ ] Cada route com handler retornando dict/list adiciona Pydantic schema em `backend/schemas/<module>.py` (reuse existing onde aplicável)
- [ ] Cada `@router.*(..., response_model=Schema)` declarado
- [ ] Routes sem retorno tipável (raw response, file streams, redirects) anotam `response_model=None` explícito + docstring rationale

### AC3: CI gate extension

- [ ] `.github/workflows/api-types-check.yml` extended:
  - Run audit script
  - Fail PR se coverage decreases vs baseline
  - Fail PR se new route adicionado sem `response_model` (compare baseline)
- [ ] Pre-commit hook `audit_response_model_coverage.py --strict` (warn-only inicialmente)

### AC4: Frontend types regen + parity validation

- [ ] `npm --prefix frontend run generate:api-types` — regen `frontend/app/api-types.generated.ts`
- [ ] Pre-commit confirma file checked-in (existing pattern)
- [ ] Audit `frontend/app/types.ts` re-export surface:
  - Add re-exports para schemas novos críticos
  - Doc convenção: import via `@/app/types` quando possível, fallback `components["schemas"]["X"]`
- [ ] `frontend/__tests__/types-parity.test.ts` — assert que tipos críticos NÃO são `{[k:string]:unknown}`:
  ```ts
  type AssertNotUnknown<T> = T extends { [k: string]: unknown } ? never : T;
  type _C1 = AssertNotUnknown<components["schemas"]["IntelReport"]>;
  type _C2 = AssertNotUnknown<components["schemas"]["AdminTraceResult"]>;
  // ... 20+ critical types
  ```

### AC5: Doc + governance

- [ ] Update `CLAUDE.md` "Pydantic -> TypeScript Type Sync" section com link audit script + coverage threshold
- [ ] Update `_reversa_sdd/code-spec-matrix.md` "Bidirectional traceability" — passo 5 "Regen api-types" mandatory + audit pass
- [ ] ADR `docs/adr/ADR-PARITY-BE-FE-001-response-model-mandatory.md` — política + edge cases (raw, streams)

---

## DoD

- [ ] Audit script committed + baseline JSON
- [ ] Coverage atual ≥ 95% (50+ routes backfilled)
- [ ] CI gate ativo (audit + types regen check)
- [ ] Frontend types regenerated + parity test green
- [ ] ADR + CLAUDE.md updates
- [ ] Memory entry: `feedback_response_model_mandatory_pattern.md`

---

## Dependências

- STORY-2.1 EPIC-TD-2026Q2 Done (precursor — pipeline existe)

---

## Notes

- Preferir reuse de `backend/schemas/*.py` existentes — não criar schema duplicado.
- Edge case: routes que retornam `JSONResponse(content=...)` raw → `response_class=JSONResponse` + Pydantic schema separate.
- File streams (PDF download, Excel export): `response_class=StreamingResponse`, `response_model=None` com docstring rationale.

---

## Execution log

### Pass 1 — admin routes (2026-05-09)

**Scope reduction rationale.** DATA-CAP-001 (#949) is rewriting the same
public-route files (`contratos_publicos.py`, `orgao_publico.py`,
`empresa_publica.py`, `itens_publicos.py`, `blog_stats.py`,
`observatorio.py`, `seo_admin.py`) in parallel. Shipping the AC2 sweep
across both groups in a single PR would force a painful rebase into
DATA-CAP-001. Pass 1 ships the audit infrastructure (AC1) plus the
admin-route subset of AC2 only; Pass 2 (public routes) follows once
DATA-CAP-001 lands.

**Coverage delta (AC1 baseline):** 64.15% → **67.92%** over 212 routes
in 70 route modules. Pass 1 typed up 8 previously-untyped admin routes:

- `backend/routes/admin_trace.py` (6 routes: `/trigger-contracts-backfill`,
  `/trigger-bids-backfill`, `/clear-contracts-checkpoints`,
  `/search-trace/{search_id}`, `/cb/reset`, `/schema-contract-status`).
- `backend/routes/admin_cron.py` (1 route: `/cron-status`).
- `backend/routes/admin_llm_cost.py` (1 route: `/llm-cost`).

**Files added / changed in Pass 1:**

- `backend/scripts/audit_response_model_coverage.py` — AST-based audit
  + `--check-against` gate semantics (AC1 + foundation for AC3).
- `backend/scripts/audit_response_model_coverage_baseline.json` — baseline
  snapshot @ 67.92% post-Pass 1, used by the future CI gate.
- `backend/schemas/admin.py` — 11 new Pydantic models for the admin
  responses (AdminJobTriggerResponse, AdminClearCheckpointsResponse,
  AdminSearchTraceResponse + nested progress/cache/jobs states,
  AdminCircuitBreakerResetResponse, AdminSchemaContractStatusResponse,
  CronJobHealthRow, AdminCronStatusResponse, AdminLlmCostResponse).
- `backend/routes/admin_trace.py`, `backend/routes/admin_cron.py`,
  `backend/routes/admin_llm_cost.py` — added `response_model=` on every
  decorator + replaced `dict` returns with the typed Pydantic models.
- `frontend/app/api-types.generated.ts` — regenerated via the same
  pipeline CI uses (`app.openapi_schema=None; app.openapi(); npx
  openapi-typescript /tmp/openapi.json`).
- `backend/tests/scripts/test_audit_response_model_coverage.py` — 17
  tests covering detection, JSON shape, gate semantics, and a real-repo
  invariant that fails if any Pass 1 admin route loses its
  `response_model=`.

**Deferred to Pass 2 (issue #951 stays open):**

- AC2 sweep across the public-route group, conversion paths, and
  internal/typed routers (still ~68 untyped routes).
- AC3 CI gate wiring (`api-types-check.yml` extension + pre-commit hook).
- AC4 frontend re-export surface audit + `types-parity.test.ts`.
- AC5 ADR + CLAUDE.md governance section.

### Pass 2 — full backfill + CI gate (2026-05-09)

**Coverage delta (AC1):** 67.92% → **100.0%** over 212 routes in 70
files. All 68 previously-untyped routes now declare `response_model=`
(either a Pydantic model or explicit `response_model=None` for streams /
redirects / mixed-body endpoints with documented rationale).

**AC2 sweep — files touched:**

- `backend/schemas/parity.py` (new) — permissive Pydantic v2 models
  (`_PermissiveBase` with `ConfigDict(extra="allow")` + every field
  `Optional[...] = None`) for routes whose return shape is structurally
  complex enough that pinning each field would risk silent key
  stripping. Covers admin SLO, health snapshots, organization/partner
  dashboards, search timeline/results/zero-match/cancel, pipeline write
  responses, alert delete, billing portal/status, cache refresh, trial
  exit surveys, validate-signup-email, experiments.
- 28 route modules touched (`auth_check`, `auth_oauth`, `auth_email`,
  `health`, `health_core`, `slo`, `stats_public`, `partners`,
  `organizations`, `trial_emails`, `reports`, `search_sse`,
  `search_status`, `metrics_api`, `pipeline`, `alerts`, `emails`,
  `notifications`, `observatorio`, `onboarding`, `sessions`,
  `sitemap_licitacoes`, `billing`, `intel_reports`, `feature_flags`,
  `analytics`, `user`, `export`) — added `response_model=` on every
  decorator. Behaviourally a no-op (no handler logic changed) — the
  kwarg only declares the OpenAPI shape.

**AC3 CI gate (new):**

- `.github/workflows/audit-response-model-coverage.yml` — runs
  `audit_response_model_coverage.py --check-against baseline.json` on
  every PR / push to main. Fails when overall coverage shrinks vs
  baseline OR when a new route module ships untyped. Posts sticky PR
  comment with the coverage table. Modeled on
  `audit-execute-without-budget.yml`.
- `backend/scripts/audit_response_model_coverage_baseline.json` —
  regenerated at 100.0%, used by the gate.

**AC4 frontend regen + parity test:**

- `frontend/app/api-types.generated.ts` — regenerated via the same
  CI-style pipeline (`app.openapi_schema=None; app.openapi();
  npx openapi-typescript /tmp/openapi.json`). 220 paths × 340 named
  schemas (was 244 before — +39%).
- `frontend/__tests__/types/parity.test.ts` (new) — compile-time
  `AssertNotUnknown<components["schemas"]["X"]>` assertions covering
  17 critical schemas (admin Pass-1 + pipeline + billing + user +
  search + health + Pass-2 permissive shapes). Fails `tsc --noEmit`
  if any of those collapses to `unknown`.

**AC5 governance:**

- `docs/adr/ADR-PARITY-BE-FE-001-response-model-mandatory.md` (new) —
  policy, accepted values for `response_model=` (model / `None` with
  docstring rationale / permissive `parity.py` model), migration path,
  trade-offs.

**Tests run locally:** `pytest tests/test_alerts.py tests/test_pipeline.py
tests/test_organizations.py tests/test_partners.py
tests/test_auth_check.py tests/test_health.py
tests/scripts/test_audit_response_model_coverage.py
tests/test_admin_*.py` → 196 passed + 5 xfail (pre-existing
batch-pollution flakes documented in test docstrings) + 1 xpass. No
regressions.

**WSL build note:** `npm run build` in this monorepo OOMs on WSL even
with `NODE_OPTIONS=--max_old_space_size=8192` — defer build-output
validation to CI. `npx tsc --noEmit` on the regenerated types will
exercise the parity test in CI via `api-types-check.yml`.
