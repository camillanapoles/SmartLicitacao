# DEBT-118: Backend Cleanup — Re-exports, Config, Dead Files, Filter Facade

**Prioridade:** POST-GTM
**Estimativa:** 22h
**Fonte:** Brownfield Discovery — @architect (ARCH-002, ARCH-003, ARCH-004, SYS-030)
**Score Impact:** Maint 8→9
**Status:** COMPLETED (2026-03-10)

## Contexto
4 backend items de manutenibilidade: search_pipeline.py tem 17 noqa:F401 re-exports para backward compat de testes, pncp_client.py lê 14 env vars diretamente em vez de usar config/, 2 arquivos .bak mortos no repo, e filter.py facade com 2141 LOC.

## Acceptance Criteria

### Dead Files (0.5h)
- [x] AC1: Deletar config.py.bak
- [x] AC2: Deletar config_legacy.py.bak

### Config Migration (2h)
- [x] AC3: Mover 14 os.environ.get() de pncp_client.py para config/pncp.py
- [x] AC4: pncp_client.py importa todas configurações de config/pncp.py
- [x] AC5: Testes existentes de pncp_client passam sem alteração (ou com mock atualizado)

### Re-export Cleanup (4h)
- [x] AC6: Identificar todos os 17 noqa:F401 em search_pipeline.py
- [x] AC7: Atualizar tests para patchar módulos fonte (não via search_pipeline)
- [x] AC8: Remover re-exports desnecessários de search_pipeline.py
- [x] AC9: Todos os 5131+ backend tests passam

### Filter Facade (16h) — pode ser story separada
- [x] AC10: Documentar responsabilidade de cada filter_*.py sub-módulo
- [x] AC11: Mover lógica restante de filter.py para sub-módulos apropriados
- [x] AC12: filter.py reduzido para <500 LOC (puro orchestration/delegation) — 242 LOC (89% reduction)
- [x] AC13: Testes de filtro passam sem regressão

## File List
- [x] `backend/config.py.bak` (DELETE)
- [x] `backend/config_legacy.py.bak` (DELETE)
- [x] `backend/config/pncp.py` (EDIT — add 12 env vars + calculation comment)
- [x] `backend/config/__init__.py` (EDIT — add re-exports)
- [x] `backend/pncp_client.py` (EDIT — import from config, remove os.environ.get)
- [x] `backend/search_pipeline.py` (EDIT — remove 17 noqa:F401 re-exports)
- [x] `backend/filter.py` (EDIT — 2141→242 LOC, pure orchestration)
- [x] `backend/filter_basic.py` (NEW — 712 LOC, basic filters + keyword matching)
- [x] `backend/filter_llm.py` (NEW — 764 LOC, LLM zero-match + arbiter)
- [x] `backend/filter_recovery.py` (NEW — 297 LOC, synonym recovery)
- [x] `backend/filter_utils.py` (NEW — 64 LOC, shared helpers)
- [x] `backend/pipeline/stages/*.py` (EDIT — direct imports from source modules)
- [x] `backend/routes/search.py` (EDIT — updated imports)
- [x] `backend/routes/onboarding.py` (EDIT — updated imports)
- [x] `backend/job_queue.py` (EDIT — updated imports)
- [x] `backend/tests/test_timeout_chain.py` (EDIT — config source file references)
- [x] 30+ test files (EDIT — patch targets updated to source modules)
