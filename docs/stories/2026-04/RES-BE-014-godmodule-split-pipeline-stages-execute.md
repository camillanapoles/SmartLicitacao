# RES-BE-014: God-Module Split — `pipeline/stages/execute.py` (1240L, 3 funções gigantes)

**Priority:** P1
**Effort:** L (5-7 dias)
**Squad:** @architect + @dev (architect lidera)
**Status:** Ready
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 4 (2026-05-27 → 2026-06-02) — paralelizável com [RES-BE-005](RES-BE-005-godmodule-split-pipeline.md), [RES-BE-007](RES-BE-007-godmodule-split-blogstats.md)
**Dependências bloqueadoras:** [RES-BE-001](RES-BE-001-audit-execute-without-budget.md), [RES-BE-009](RES-BE-009-test-suite-triage.md) (suite saudável necessária para detectar regressões)

---

## Contexto

`backend/pipeline/stages/execute.py` tem **1240 linhas** distribuídas em apenas **3 funções públicas** (Reversa explore agent 2026-04-28). Ratio LOC/função ~413 indica funções gigantes — code smell agudo: cada função encapsula múltiplas responsabilidades de orquestração da search pipeline state machine (11 estados, `models/search_state.SearchState`).

Este módulo é **blast-radius máximo** do produto: orquestra a totalidade do flow `POST /buscar` → SSE progress → result store. Cada bug aqui afeta 100% das buscas e portanto Time-to-Value (TTV <5min — GTM-004) e percepção de valor B2G (US-001 Reversa user-stories.md). Memory `project_backend_outage_2026_04_27` mostra como impacto sistêmico em search pipeline cascateia para conversão (paywall_hit + trial_started silenciados).

Distinção crítica vs stories vizinhas:
- ❌ **Não é** `routes/search.py` decomp ([DEBT-115](../story-DEBT-115-search-route-decomposition.md) — Done; cobriu HTTP layer 2177→748 LOC).
- ❌ **Não é** `routes/search/__init__.py` package ([STORY-3.1](EPIC-TD-2026Q2/STORY-3.1-search-py-decomposition.md) — InReview; cobriu route handlers).
- ❌ **Não é** `filter/pipeline.py` decomp ([RES-BE-005](RES-BE-005-godmodule-split-pipeline.md) — Ready Sprint 4; cobre keyword/scoring/exclusions).
- ✅ **É** `pipeline/stages/execute.py` 1240L — orquestrador da state machine 11-states.

Esta story split em sub-módulos coesos por **fase do estado** + facade para zero-impact externo. Effort L pelo blast radius + necessidade de QA loop pesado (cobertura state-machine ≥85%, sem regressão funcional).

Padrão referência: split bem-sucedido em `quota/` (TD-007: ex-`quota.py` 1660L → 6 sub-módulos com façade) + `cache/` (manager, swr, admin, local_file, redis, supabase).

---

## Acceptance Criteria

### AC1: Mapeamento das 3 funções gigantes

- [ ] **@architect Phase 0 obrigatório:** Read integral `backend/pipeline/stages/execute.py`. Identificar nomes + boundary das 3 funções públicas. Hipótese (a validar):
  - `dispatch(request, ctx) → state` — entry point, valida input, transition CREATED→DISPATCHED
  - `_run_phase(state, ctx) → state` — phase runner per source (PNCP, PCP v2, ComprasGov), state transitions DISPATCHED→FETCHING→FETCHED→FILTERING→FILTERED
  - `_finalize(state, results, ctx) → SearchResult` — consolidação, dedup, score/rank, state transitions FILTERED→CONSOLIDATED→COMPLETED
- [ ] Mapeamento entregue em `docs/architecture/pipeline-execute-decomposition.md` ANTES de qualquer commit de extração.

### AC2: Estrutura alvo (sub-módulos por fase)

- [ ] Criar pacote `backend/pipeline/stages/execute/` (atualmente arquivo único — virar package):
  ```
  backend/pipeline/stages/execute/
  ├── __init__.py        # façade re-export (zero breaking change)
  ├── _dispatcher.py     # entry point + input validation + initial state (~250L)
  ├── _phase_runner.py   # phase-per-source runner + state transitions (~400L)
  ├── _finalize.py       # consolidation, dedup, score/rank, finalize (~350L)
  ├── _state_helpers.py  # shared state machine utilities (transition guards, retry counters) (~150L)
  └── _types.py          # ExecutionContext, PhaseResult dataclasses (~90L)
  ```
- [ ] Total LOC consolidado ≤ 1240L (ganho coesão, sem bloat).

### AC3: Façade `execute/__init__.py` re-exportador

- [ ] `__init__.py` re-exporta API pública preservada:
  ```python
  """Pipeline execute stage facade. Sub-modules under backend/pipeline/stages/execute/."""
  from ._dispatcher import dispatch
  from ._phase_runner import run_phase
  from ._finalize import finalize
  from ._types import ExecutionContext, PhaseResult

  __all__ = ["dispatch", "run_phase", "finalize", "ExecutionContext", "PhaseResult"]
  ```
- [ ] Importadores existentes (`backend/search_pipeline.py`, `backend/jobs/queue/search.py`, `backend/routes/search/post_handler.py`) **não mudam** uma linha.
- [ ] Symbol resolution: `from pipeline.stages.execute import dispatch` continua funcionando (façade preserva).

### AC4: State machine invariants preservados

- [ ] `models/search_state.VALID_TRANSITIONS` continua sendo single source of truth — sub-módulos não duplicam lógica de transition.
- [ ] Cada sub-módulo só transita estados ALLOWED em sua fase:
  - `_dispatcher.py`: CREATED → DISPATCHED, ERROR
  - `_phase_runner.py`: DISPATCHED → FETCHING → FETCHED → FILTERING → FILTERED, ERROR, PARTIAL
  - `_finalize.py`: FILTERED → CONSOLIDATED → COMPLETED, ERROR
- [ ] Test invariante: `backend/tests/test_pipeline_execute_state_invariants.py` (novo) — para cada fase, assert que transições são subset de VALID_TRANSITIONS para aquela fase.

### AC5: PRs sequenciais (chunked rollout)

- [ ] **PR 1 (extract):** criar package + sub-módulos vazios com docstrings + `__all__ = []`. Executar `mv` semântico de função por função, rodando suite full após cada move. `__init__.py` torna-se façade. **Suite deve passar SEM alterações.**
- [ ] **PR 2 (opcional, pós-PR1):** Migrar consumidores internos críticos (`search_pipeline.py` orchestrator) para imports diretos sub-módulo (`from pipeline.stages.execute._phase_runner import run_phase`) — facilita futura remoção do façade.
- [ ] **PR 3 (futuro, fora do escopo):** Marcar `pipeline.stages.execute` (módulo top) como deprecated; emitir DeprecationWarning.
- [ ] Esta story cobre PR 1 obrigatoriamente; PR 2 opcional se tempo permitir.

### AC6: Cobertura testes ≥85% por sub-módulo

- [ ] Novos testes em `backend/tests/pipeline/test_execute_<submodule>.py`:
  - `test_execute_dispatcher.py` — input validation, initial state, edge cases (BuscaRequest malformado, missing setores)
  - `test_execute_phase_runner.py` — 3 sources runner, state transitions, partial failure, timeout per source, circuit breaker mock
  - `test_execute_finalize.py` — dedup 5-layer, score, rank, fallback summary
  - `test_execute_state_helpers.py` — transition guards, retry counter
- [ ] Tests existentes `backend/tests/test_pipeline_*.py` + `test_search_*.py` continuam passando sem modificação.
- [ ] Cobertura medida via `pytest --cov=backend/pipeline/stages/execute --cov-report=term-missing` ≥85% em linhas tocadas.
- [ ] Edge cases adicionais: ≥3 testes novos por sub-módulo cobrindo branches não-cobertos pré-split.

### AC7: Performance — sem regressão >10%

- [ ] Benchmark micro: `backend/tests/perf/test_pipeline_execute_bench.py` (criar)
  - Cenário: payload realista (BuscaRequest 5 setores, 5 UFs, 30d window) com mock fixtures de bids.
  - Métrica: tempo total `dispatch` → `_finalize` end-to-end.
  - Pre-split baseline registrado em `docs/perf/pipeline-execute-baseline-2026-04-28.md` (registrar ANTES da split).
  - Pós-split: latência mediana <110% baseline (até 10% overhead aceitável por imports adicionais).
- [ ] Profile com `cProfile` se overhead >10%; tentar imports lazy ou `__slots__` em dataclasses se necessário.

### AC8: Documentação arquitetural

- [ ] Cada sub-módulo tem docstring de módulo (3-5 linhas explicando responsabilidade + boundary).
- [ ] `backend/pipeline/stages/execute/__init__.py` tem comentário-mapa: "this package replaces the 1240L execute.py god-file (3 functions)".
- [ ] `docs/architecture/pipeline-execute-decomposition.md` (criado em AC1, atualizado pós-split) inclui:
  - Diagrama mermaid das 11 states + fase responsável
  - Tabela símbolo→sub-módulo
  - Decisão de design: por que phase-based split (não single-feature)
- [ ] `.claude/rules/architecture-detail.md` linha "Search Pipeline" — atualizar referência única `backend/pipeline/stages/execute.py` para listagem de 5 sub-módulos.
- [ ] CLAUDE.md (auto-load) seção "Layer 2: Search Pipeline" atualizar referência se mencionar `execute.py` direto.

### AC9: Gate final — Suite + cobertura + perf

- [ ] Suite total backend passa sem regressão (5131+ tests passing, 0 failures — baseline atual).
- [ ] Suite tempo total CI mantido <8min (alvo após RES-BE-009).
- [ ] Cobertura por sub-módulo ≥85%.
- [ ] Sem novos warnings em pytest (DeprecationWarning, ImportWarning).
- [ ] State machine invariants test (AC4) PASS.
- [ ] Benchmark perf (AC7) PASS.

---

## Scope

**IN:**
- Split `execute.py` em 4 sub-módulos coesos + 1 types module
- Façade `__init__.py` re-exportador (zero impact externo)
- Mapeamento prévio em `docs/architecture/pipeline-execute-decomposition.md`
- Testes ≥85% cobertura por sub-módulo
- Test invariante state machine
- Benchmark perf pre/post

**OUT:**
- Refator de lógica interna (e.g. otimizar dedup algorithm) — apenas re-organizar
- Remoção do façade (PR 3, futuro)
- Migrar consumidores externos (PR 2 — opcional nesta story)
- Adicionar novos estados na state machine — proibido (single source of truth `models/search_state.py`)
- Renaming de funções públicas (`dispatch`, `run_phase`, `finalize`) — proibido nesta story (zero-impact externo)
- Mudanças em `pipeline/budget.py`, `pipeline/cache_manager.py`, `pipeline/tracing.py`, `pipeline/worker.py` (siblings) — fora escopo

---

## Definition of Done

- [ ] 5 sub-módulos criados com responsabilidades claras (`_dispatcher`, `_phase_runner`, `_finalize`, `_state_helpers`, `_types`)
- [ ] Façade `__init__.py` slim (~30L) re-exportando API pública preservada
- [ ] `docs/architecture/pipeline-execute-decomposition.md` criado (Phase 0 + atualizado pós-split)
- [ ] Cobertura testes ≥85% por sub-módulo
- [ ] Suite backend passa sem regressão (0 failures)
- [ ] Test invariante state machine PASS
- [ ] Benchmark perf: latência mediana <110% baseline
- [ ] `.claude/rules/architecture-detail.md` atualizado
- [ ] CLAUDE.md atualizado (referência ao novo package)
- [ ] CodeRabbit review clean (CRITICAL=0, HIGH=0)
- [ ] PR review por @architect (Aria) — review obrigatório de design — e @qa (Quinn) com verdict PASS
- [ ] QA loop max 2 iterações (effort grande, esperado feedback)

---

## Dev Notes

### Paths absolutos

- `/mnt/d/pncp-poc/backend/pipeline/stages/execute.py` (1240L → arquivo deletado, package criado)
- `/mnt/d/pncp-poc/backend/pipeline/stages/execute/__init__.py` (novo, façade ~30L)
- `/mnt/d/pncp-poc/backend/pipeline/stages/execute/_dispatcher.py` (novo, ~250L)
- `/mnt/d/pncp-poc/backend/pipeline/stages/execute/_phase_runner.py` (novo, ~400L)
- `/mnt/d/pncp-poc/backend/pipeline/stages/execute/_finalize.py` (novo, ~350L)
- `/mnt/d/pncp-poc/backend/pipeline/stages/execute/_state_helpers.py` (novo, ~150L)
- `/mnt/d/pncp-poc/backend/pipeline/stages/execute/_types.py` (novo, ~90L)
- `/mnt/d/pncp-poc/backend/tests/pipeline/test_execute_dispatcher.py` (novo)
- `/mnt/d/pncp-poc/backend/tests/pipeline/test_execute_phase_runner.py` (novo)
- `/mnt/d/pncp-poc/backend/tests/pipeline/test_execute_finalize.py` (novo)
- `/mnt/d/pncp-poc/backend/tests/pipeline/test_execute_state_helpers.py` (novo)
- `/mnt/d/pncp-poc/backend/tests/pipeline/test_execute_state_invariants.py` (novo, AC4)
- `/mnt/d/pncp-poc/backend/tests/perf/test_pipeline_execute_bench.py` (novo)
- `/mnt/d/pncp-poc/docs/architecture/pipeline-execute-decomposition.md` (novo)
- `/mnt/d/pncp-poc/docs/perf/pipeline-execute-baseline-2026-04-28.md` (novo, registro pre-split)

### Padrão referência

- Split bem-sucedido similar: `backend/cache/` (6 sub-módulos com façade), `backend/quota/` (TD-007: 1660L → 6 sub-módulos), `backend/routes/search/` (DEBT-115 Done, 2177L → 4 sub-módulos)
- `backend/pipeline/budget.py`, `cache_manager.py`, `helpers.py`, `tracing.py`, `worker.py`, `stages/generate.py`, `stages/filter_stage.py` já são módulos siblings — verificar se algum overlap com extração proposta (provavelmente não; mas TODO @architect: validar Phase 0)

### Process — ordem sugerida

1. **Phase 0:** Read `execute.py` integral; mapear 3 funções → linhas + responsabilidade. Decisão arquitetural via `decision-recorder.js` se as 3 hipotéticas não confirmarem.
2. **Branch:** `refactor/RES-BE-014-execute-stages-split`
3. **PR 1 commit 1:** criar package + sub-módulos vazios com docstrings + `__all__ = []`
4. **PR 1 commit 2..N:** mover símbolos um a um (uma função por commit), rodando `pytest backend/tests/test_pipeline_*.py backend/tests/test_search_*.py` após cada move
5. **PR 1 commit penúltimo:** criar test invariante AC4 + benchmark AC7
6. **PR 1 commit final:** deletar `execute.py` original (foi virou package); finalizar `__init__.py` façade
7. CodeRabbit pass + QA gate

### Frameworks de teste

- pytest 8.x + pytest-asyncio (state machine async)
- File location: `backend/tests/pipeline/test_execute_<submodule>.py`
- Marks: `@pytest.mark.timeout(30)` em testes de phase runner (3 sources mock pode demorar)
- Fixtures: reusar `conftest.py` para `BuscaRequest` builder + `pncp_raw_bids` mock data
- State invariant test: parameterize `@pytest.mark.parametrize("phase", ["dispatcher", "phase_runner", "finalize"])` + cada fase testa subset de VALID_TRANSITIONS

### Convenções

- Imports absolutos (Constitution Article VI): `from pipeline.stages.execute._phase_runner import run_phase` (não `from ._phase_runner import run_phase` em testes)
- Type hints obrigatórios em sub-módulos novos (continuação STORY-3.2)
- Logger por módulo: `logger = logging.getLogger(__name__)`
- `__all__` explícito em cada sub-módulo (incluindo `_` prefix indica internal — só `__init__.py` re-exporta sem `_`)
- OpenTelemetry tracing: cada sub-módulo preserva spans existentes; nenhum span novo (escopo isolado)
- Métricas Prometheus: nenhuma nova métrica (escopo isolado)

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Suite backend regride (testes failing após move) | Revert commit ofensivo dentro do PR; identificar símbolo com import circular ou state shared inesperado |
| Performance regride >10% em benchmark | Investigar imports lazy (`if TYPE_CHECKING`) ou `__slots__` em ExecutionContext; se irrecuperável, revert PR e abrir refator alternativo (e.g. split por feature em vez de fase) |
| State machine invariant fail (transição ALLOWED em fase errada) | BLOQUEIA merge — revisar boundary de fase; provável bug de extração (função movida para sub-módulo errado) |
| Consumidor externo quebra (e.g. import direto de função `_helper` privada) | Adicionar símbolo ao façade ou `__init__.py`; documentar antipattern em `docs/architecture/pipeline-execute-decomposition.md` "Don't" section |
| QA loop excede 5 iterações | Escalar para @aiox-master; possível split em 2 stories (dispatcher+phase_runner vs finalize+state_helpers) |
| Imports circulares em runtime | Refator: extrair classe/função compartilhada para `_types.py` (módulo neutro sem deps de outros sub-módulos) |
| Phase 0 mapping divergir de hipótese (e.g. 5 funções não 3, ou função monolítica única) | Atualizar AC1+AC2 via Change Log; @architect decide nova decomposição; @po re-valida AC antes de PR 1 |

**Rollback completo:** revert PR. Façade preserva API; consumidores externos não percebem rollback. State machine `models/search_state.py` não é tocado, então rollback é seguro.

---

## Dependencies

**Entrada:**
- [RES-BE-001](RES-BE-001-audit-execute-without-budget.md) — gate CI ativo (deve estar Done para detectar regressão de `.execute()` em refactor)
- [RES-BE-009](RES-BE-009-test-suite-triage.md) — suite saudável <8min CI necessário para QA loop iterativo
- [STORY-3.1](EPIC-TD-2026Q2/STORY-3.1-search-py-decomposition.md) — InReview; HTTP layer já decomposto, então este split tem boundary claro

**Saída:**
- Habilita futuro: stories de feature em search pipeline ficam mais fáceis de testar isoladamente (ex: novo source ComprasNet poderia adicionar `_phase_runner` config sem tocar finalize)
- Habilita observabilidade granular: spans OTel podem ser nomeados por sub-módulo (futuro escopo)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | God-module split com LOC + função count explícito (1240L, 3 funções). |
| 2 | Complete description | ✓ | Distinção crítica vs DEBT-115/STORY-3.1/RES-BE-005 documentada (3 god-modules diferentes). |
| 3 | Testable acceptance criteria | ✓ | 9 ACs incluindo benchmark perf <110% baseline + state machine invariants test. |
| 4 | Well-defined scope | ✓ | Scope IN/OUT explícito; OUT inclui zero functional change. |
| 5 | Dependencies mapped | ✓ | Entrada RES-BE-001+009; saída habilita future stories isoladas. |
| 6 | Complexity estimate | ✓ | L (5-7d) coerente vs RES-BE-005 (similar scope). |
| 7 | Business value | ✓ | Blast-radius máximo TTV/percepção valor; memory `project_backend_outage_2026_04_27` reforça impacto. |
| 8 | Risks documented | ✓ | 7 triggers + escalation @aiox-master se QA loop excede 5. |
| 9 | Criteria of Done | ✓ | 13 itens DoD incluindo @architect review obrigatório. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-RES-BE-2026-Q2 god-module split sequence (após 005/006/007/008). |

### Observations

- Phase 0 (AC1) mapping mandatório é Required Fix preventivo bem-resolvido — antes de PR 1, @architect valida hipótese das 3 funções via Read integral.
- State machine invariants test (AC4) é proteção extra contra bug de extração — recomendação @qa.
- Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via `/sm crie todas stories` — split god-module `pipeline/stages/execute.py` 1240L (3 funções). Origem: `_reversa_sdd/sm-briefing-refactor.md` REF-VAL-001. Renomeado para RES-BE-014 seguindo convenção EPIC-RES-BE. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
