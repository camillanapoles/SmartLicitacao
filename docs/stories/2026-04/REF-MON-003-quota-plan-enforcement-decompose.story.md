# REF-MON-003: Decompose `quota/plan_enforcement.py` (537L → 3 sub-módulos)

**Priority:** P2
**Effort:** M (3-4 dias)
**Squad:** @architect + @dev
**Status:** Ready
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/)
**Sprint:** Sprint 3
**Dependências bloqueadoras:** Nenhuma

---

## Contexto

`backend/quota/plan_enforcement.py` 537L concentra:

1. `check_quota` multi-layer fallback (layered: user_subscriptions → cache → profiles.plan_type → defaults)
2. `require_active_plan` FastAPI dependency
3. Cache 2-tier (`_plan_status_cache`)
4. Legacy plan mapping (`master→sala_guerra`, `premium→maquina`, `basic→consultor_agil`, `free→free_trial`)

Boundaries vagas: capabilities lookup misturado com auth gates. `quota_core.py` 376L já isola `PLAN_CAPABILITIES`; bem-isolado pode receber mais.

---

## Acceptance Criteria

### AC1: Estrutura alvo

- [ ] `backend/quota/plan_enforcement.py` reduz para ~200L (orquestrador `check_quota` + dependency `require_active_plan`)
- [ ] `backend/quota/legacy_mapping.py` (novo, ~80L): `_legacy_plan_mapping` dict + `map_legacy(name) → canonical_id`
- [ ] `backend/quota/fallback_chain.py` (novo, ~250L): `_UNKNOWN_PLAN_DEFAULTS` + cada layer fallback como função puras testáveis isoladamente

### AC2: Mover `_plan_status_cache` 2-tier

- [ ] Cache primary já em `quota_core.py:_plan_status_cache`/`_plan_capabilities_cache` — verify NÃO duplica em plan_enforcement
- [ ] `plan_enforcement.py` consome via `quota_core.get_cached_plan_status(user_id)`
- [ ] Sem cache local em plan_enforcement

### AC3: Façade preservation

- [ ] `quota/__init__.py` continua re-exporting `check_quota`, `require_active_plan`, etc. (zero breaking change)
- [ ] Importadores externos não mudam

### AC4: Tests redistributed

- [ ] `test_quota_legacy_mapping.py` (novo): unit tests `map_legacy` para cada legacy name
- [ ] `test_quota_fallback_chain.py` (novo): cada layer testado isoladamente
- [ ] `test_quota_check_quota.py` (refactor existing): integration end-to-end
- [ ] Cobertura ≥85% por sub-módulo

### AC5: Documentação

- [ ] Docstring em cada sub-módulo
- [ ] `docs/architecture/quota-decomposition.md` mostra mapping LCC pré/pós

---

## Scope

**IN:** decompose 537L → 3 sub-módulos + tests redistributed + docs
**OUT:** Mudar comportamento `check_quota` (zero functional change) · Adicionar novos plans

---

## Definition of Done

- [ ] 3 sub-módulos criados
- [ ] Façade preserved
- [ ] Tests passam + cobertura ≥85%
- [ ] Suite passa
- [ ] @po validation GO

---

## Dev Notes

- `quota/quota_core.py:376L`, `quota_atomic.py:271L`, `session_tracker.py:335L`, `plan_auth.py:178L` — siblings já bem-isolados
- Pattern referência: `quota/` já fez split TD-007 (1660L → 6 sub-módulos); replicar
- Constitution Article VI: imports absolutos (`from quota.legacy_mapping import map_legacy`)

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Multi-layer fallback comportamento muda subtle | Cobertura test integration end-to-end (AC4) cobrirá |
| Cache duplication accidental | AC2 explicit: sem cache local em plan_enforcement |

**Rollback:** revert PR; quota/__init__.py re-export inalterado.

---

## Dependencies

**Entrada:** Nenhuma
**Saída:** facilita future stories de pricing experimentation

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Decompose explícito 537L → 3 sub-módulos. |
| 2 | Complete description | ✓ | 4 responsabilidades acopladas listadas. |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com cobertura ≥85% por sub-módulo. |
| 4 | Well-defined scope | ✓ | OUT exclude functional changes em check_quota. |
| 5 | Dependencies mapped | ✓ | Nenhuma external. |
| 6 | Complexity estimate | ✓ | M (3-4d) coerente. |
| 7 | Business value | ✓ | Boundaries claros + future pricing experimentation. |
| 8 | Risks documented | ✓ | Cobertura test integration end-to-end mitigates. |
| 9 | Criteria of Done | ✓ | 5 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 decomposition pattern. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-MON-003. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
