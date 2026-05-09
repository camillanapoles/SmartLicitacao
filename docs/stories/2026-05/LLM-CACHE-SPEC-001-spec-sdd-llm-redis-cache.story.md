# LLM-CACHE-SPEC-001: Spec SDD para LLM Response Cache (PR #160)

**Priority:** P2
**Effort:** XS (2-4h)
**Squad:** @architect (lead) + @dev
**Status:** InReview
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/) — eixo doc coverage
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma (PR #160 já merged 2026-05-08)
**Reversa anchor:** `_reversa_sdd/review-report.md §10.2` + `code-spec-matrix.md` LLM-CACHE-001/002/003

---

## Contexto

PR #160 (`perf(backend): cache Redis para respostas LLM por licitacao_id+tipo`) foi shipped 2026-05-08 22:10 sem spec SDD formal em `_reversa_sdd/specs/`. Cache transparente Redis (TTL 7d, SHA-256 key, graceful fallback) em `gerar_resumo()` — wrapper `get_or_generate_resumo_cached` substitui call sites em `pipeline/stages/generate.py` e `jobs/queue/jobs.py`.

Doc coverage atual 89%; spec SDD para este módulo elimina lacuna documentação reliability-critical (custo OpenAI direto + p95 latência summarization).

---

## Acceptance Criteria

### AC1: Spec SDD em `_reversa_sdd/specs/`

- [x] Criar `_reversa_sdd/specs/14-llm-response-cache.spec.md` seguindo template specs/01-05 (renomeado de `06-` → `14-` para evitar colisão com `06-jobs-cron.spec.md` existente; extensão `.spec.md` preservada para conformidade com glob convention)
- [x] Seções: Propósito · Inputs/Outputs · Cache key derivation (SHA-256 sorted bid IDs + params) · TTL policy (7d) · Fallback semantics (Redis down → call OpenAI normalmente) · Test coverage (`test_llm_cache.py` 279 LOC) · Wrapper API contract (`get_or_generate_resumo_cached`)

### AC2: OpenAPI cross-ref

- [x] Atualizar `_reversa_sdd/openapi-summary.md` com nota: cache layer transparente — não exposto via API; afeta latência de `/v1/buscar` (background ARQ via `llm_summary_job`) e do estágio inline `pipeline/stages/generate.py`. Nova subseção "Cache layers" antes de "## CI Gate".

### AC3: Code-Spec matrix update

- [x] `_reversa_sdd/code-spec-matrix.md` — entry adicionada na "Spec coverage" table como `14b | llm-response-cache | ✅ written`. Nota: marcador "Stories Status — 2026-05-08 EOD §LLM-CACHE" mencionado pela story original não existe no arquivo no commit base (origin/main 059c65632) — append usado em vez de replace.

---

## Files

| Arquivo | Ação |
|---------|------|
| `_reversa_sdd/specs/06-llm-response-cache.md` | Create |
| `_reversa_sdd/openapi-summary.md` | Edit (1 nota) |
| `_reversa_sdd/code-spec-matrix.md` | Edit (1 linha) |

---

## Definition of Done

- [x] Spec criada cobrindo PR #160 sem invenção (fonte: `backend/llm.py` + `test_llm_cache.py`); cada claim ancorado com `path:linha`
- [x] Confiança 🟢 CONFIRMADO em todas seções (código existe em `main` commit 059c65632)
- [x] Validate `wc -l` post-write — **185 LOC** em `_reversa_sdd/specs/14-llm-response-cache.spec.md` (>= 50 baseline anti-vapor)

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
| 1 | Clear and objective title | ✓ | Spec SDD para LLM Response Cache (PR #160) — escopo único explícito |
| 2 | Complete description | ✓ | Contexto cita PR + módulo + lacuna doc; fonte código identificada |
| 3 | Testable acceptance criteria | ✓ | 3 ACs deliverable-based (file create/edit) |
| 4 | Well-defined scope | ✓ | Doc-only; código existe e shipped (PR #160 merged) |
| 5 | Dependencies mapped | ✓ | "Nenhuma — PR #160 já merged" |
| 6 | Complexity estimate | ✓ | XS (2-4h) realista para spec doc |
| 7 | Business value | ✓ | Doc coverage 89% → 91% (closes gap composite 100%) |
| 8 | Risks documented | ✓ | Anti-vapor `wc -l` validate explícito (memory: feedback_handoff_stale_30h) |
| 9 | Criteria of Done | ✓ | 3 itens DoD claros |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 + Reversa anchor §10.2 |

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-08 | 1.0 | Story criada (SM) | @sm |
| 2026-05-09 | 1.1 | PO validation GO 10/10 — Draft → Ready | @po |
| 2026-05-09 | 1.2 | Spec entregue + status Ready → InReview (autonomous YOLO) | @dev/@architect |

---

## File List

| Arquivo | Ação | LOC |
|---------|------|-----|
| `_reversa_sdd/specs/14-llm-response-cache.spec.md` | Create (renomeado de `06-` p/ evitar colisão) | 185 |
| `_reversa_sdd/openapi-summary.md` | Edit (subseção "Cache layers" antes de "## CI Gate") | +5 |
| `_reversa_sdd/code-spec-matrix.md` | Edit (1 linha em "Spec coverage" table) | +1 |
| `docs/stories/2026-05/LLM-CACHE-SPEC-001-spec-sdd-llm-redis-cache.story.md` | Edit (status, checkboxes ACs/DoD, change log, File List) | — |

**Source-of-truth código (não modificado, apenas referenciado):**
- `backend/llm.py:803-909` (constante TTL + helpers + wrapper)
- `backend/tests/test_llm_cache.py` (279 LOC, 9 testes)
- `backend/pipeline/stages/generate.py:273` + `backend/jobs/queue/jobs.py:428` (call sites)
- `backend/metrics.py:1225-1233` (counters Prometheus)
