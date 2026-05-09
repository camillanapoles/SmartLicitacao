# TEST-ERR-RECOVERY-2026-001: Error Recovery Test Coverage (replacement #236)

**Priority:** P2
**Effort:** S (4-8h)
**Squad:** @qa (lead) + @dev
**Status:** InProgress
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/) — eixo test/CI gates
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma
**Substitui:** Issue #236 TD-TEST-025 (Error Handling and Recovery Tests Missing — stale 2026-02-04, escopo monolítico, fechado 2026-05-08 com rationale)
**Reversa anchor:** `_reversa_sdd/review-report.md §10.4` test/CI 86% (+14 to 100%)

---

## Contexto

#236 propunha "comprehensive error handling and recovery tests" — escopo amplo. Substituição focada em **3 paths de recovery críticos identificados pelos incidentes 2026-04**:

1. **Pipeline backend wedge recovery** (CRIT-084 + POOL-LEAK-001) — workers travados, recovery via timeout
2. **SSE reconnection** (STORY-2.4 EPIC-TD) — frontend perde conexão mid-search, retry sem perder state
3. **Cache fallback paths** — Redis down → Supabase L2; OpenAI down → graceful degradation; Stripe webhook delivery falha → retry idempotency

Memory `feedback_chief_pivot_2strikes` + `feedback_pool_leak_caller_timeout_vs_sql_timeout`: incidents recorrentes onde recovery path nunca foi testado explicitamente.

---

## Acceptance Criteria

### AC1: Backend recovery tests

- [x] `backend/tests/recovery/test_pipeline_timeout_recovery.py` — simula route hang (mock asyncio.sleep>budget), confirma 503 + worker reciclado
- [x] `backend/tests/recovery/test_pool_exhaustion_recovery.py` — simula pool exhaust, confirma queries subsequentes recuperam
- [x] `backend/tests/recovery/test_redis_down_fallback.py` — Redis indisponível, confirma L2 Supabase + cache rebuild

### AC2: Frontend recovery tests

- [x] `frontend/__tests__/recovery/sse-reconnect.test.tsx` — mock EventSource close, confirma retry + state preserve
- [x] `frontend/__tests__/recovery/api-retry.test.tsx` — 503 backend, confirma exponential backoff + max retry + UI feedback

### AC3: Integration tests

- [x] `backend/tests/integration/test_stripe_webhook_retry.py` — webhook delivery falha 1x, retry success com idempotency key
- [x] `backend/tests/integration/test_openai_fallback.py` — OpenAI 503, confirma sem crash + fallback resumo placeholder ou retry

### AC4: Documentação

- [x] `docs/testing/recovery-coverage.md` — paths cobertos + paths deferred + rationale

---

## Files

| Arquivo | Ação |
|---------|------|
| `backend/tests/recovery/*.py` | Create (3 files) |
| `frontend/__tests__/recovery/*.test.tsx` | Create (2 files) |
| `backend/tests/integration/test_stripe_webhook_retry.py` | Create |
| `backend/tests/integration/test_openai_fallback.py` | Create |
| `docs/testing/recovery-coverage.md` | Create |

---

## Definition of Done

- [x] 7 test files green (16 backend + 8 frontend = 24 tests)
- [x] Cada recovery path tem mínimo 1 test happy + 1 edge
- [x] Doc publicada (`docs/testing/recovery-coverage.md`)
- [x] `review-report.md §10.4` test/CI +4pts target — score 84% → 88%

## File List

**Created:**
- `backend/tests/recovery/__init__.py`
- `backend/tests/recovery/test_pipeline_timeout_recovery.py` (3 tests)
- `backend/tests/recovery/test_pool_exhaustion_recovery.py` (3 tests)
- `backend/tests/recovery/test_redis_down_fallback.py` (3 tests)
- `backend/tests/integration/test_stripe_webhook_retry.py` (3 tests)
- `backend/tests/integration/test_openai_fallback.py` (4 tests)
- `frontend/__tests__/recovery/sse-reconnect.test.tsx` (3 tests)
- `frontend/__tests__/recovery/api-retry.test.tsx` (5 tests)
- `docs/testing/recovery-coverage.md`

**Modified:**
- `_reversa_sdd/review-report.md` (§10 refresh — test/CI +4pts)

## Test Results

```
backend:  16 passed in 12.99s (recovery + integration)
frontend:   8 passed in 21.06s (recovery)
```

---

## PO Validation

**Validated by:** @po (Sarah)
**Date:** 2026-05-09
**Verdict:** GO
**Score:** 10/10
**Status transition:** Draft → Ready

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Error Recovery Test Coverage (substitui #236) |
| 2 | Complete description | ✓ | 3 paths críticos identificados via incidents 2026-04 (não especulativo) |
| 3 | Testable acceptance criteria | ✓ | AC1 backend 3 tests, AC2 frontend 2 tests, AC3 integration 2 tests, AC4 doc |
| 4 | Well-defined scope | ✓ | 3 paths cap (não comprehensive) — extension via TEST-ERR-002+ |
| 5 | Dependencies mapped | ✓ | Nenhuma + cross-ref #856 RES-BE-017 (POOL-LEAK pattern test) |
| 6 | Complexity estimate | ✓ | S (4-8h) realista para 7 test files |
| 7 | Business value | ✓ | Test/CI +4 (gap composite 100%); cobertura recovery paths recorrentes em incidents |
| 8 | Risks documented | ✓ | Memory `feedback_chief_pivot_2strikes` + `feedback_pool_leak_caller_timeout_vs_sql_timeout` cross-ref |
| 9 | Criteria of Done | ✓ | 3 itens DoD (7 files, happy+edge, doc) |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 test/CI + Reversa anchor §10.4 |

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-08 | 1.0 | Story criada (SM, substitui #236 stale) | @sm |
| 2026-05-09 | 1.1 | PO validation GO 10/10 — Draft → Ready | @po |
| 2026-05-09 | 1.2 | Implementation complete — 24 tests green (16 backend + 8 frontend), doc published, review-report bumped — Ready → InProgress | @qa+@dev |
