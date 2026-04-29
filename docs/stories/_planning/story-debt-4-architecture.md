# STORY-DEBT-4: Backend Module Decomposition

**Epic:** EPIC-DEBT-2026
**Batch:** 4
**Prioridade:** P2
**Estimativa:** 32h
**Agente:** @dev (implementacao) + @architect (review de estrutura) + @qa (validacao)

## Descricao

Decompor os 4 maiores monolitos do backend que excedem 1500 LOC: `filter/core.py` (3871), `schemas.py` (2121), `job_queue.py` (2152) + `cron_jobs.py` (2218). Adicionalmente, reorganizar os 68 top-level `.py` files em packages logicos.

**Estrategia:** Facade preservation pattern -- criar nova estrutura de packages, mover codigo para submodulos, manter re-exports via `__init__.py` para que TODOS os imports existentes continuem funcionando sem modificacao. Cada file move = commit separado + full test suite run.

**Debt IDs:** DEBT-301, DEBT-304, DEBT-302, DEBT-305

## Acceptance Criteria

### filter/core.py Decomposition (DEBT-301, 8h)
- [ ] AC1: `filter/core.py` (3871 LOC) decomposto em submodulos: `filter/keyword_matching.py`, `filter/density_scoring.py`, `filter/uf_filter.py`, `filter/value_filter.py`, `filter/status_validation.py` (ou estrutura similar baseada em analise do codigo)
- [ ] AC2: `filter/__init__.py` re-exporta todas as funcoes publicas -- `from filter import classificar_resultado` continua funcionando
- [ ] AC3: `python -c "from filter import classificar_resultado, calcular_densidade"` executa sem erro
- [ ] AC4: Todos 14 test files de filter (3704 LOC) passam sem modificacao de imports
- [ ] AC5: `pytest --cov=filter --cov-report=term-missing` mostra cobertura >80% em cada submodulo

### Backend Packaging (DEBT-304, 12h)
- [ ] AC6: Top-level `.py` files reorganizados em packages: `filtering/` (11 files), `search/` (4 files), `pncp/` (3 files), e outros conforme analise
- [ ] AC7: Cada package tem `__init__.py` com re-exports para backward compatibility
- [ ] AC8: `python -c "from <package> import <key_function>"` sucesso para cada package criado
- [ ] AC9: OpenAPI schema snapshot test (`openapi_schema.diff.json`) mostra zero diff -- API publica inalterada

### schemas.py Decomposition (DEBT-302, 6h)
- [ ] AC10: `schemas.py` (2121 LOC) dividido por dominio: `schemas/search.py`, `schemas/billing.py`, `schemas/pipeline.py`, `schemas/user.py`, `schemas/analytics.py` (ou similar)
- [ ] AC11: `schemas/__init__.py` re-exporta todos os modelos -- `from schemas import BuscaRequest, BuscaResponse` continua funcionando
- [ ] AC12: Todas 49 routes importam corretamente apos decomposicao

### job_queue.py + cron_jobs.py Decomposition (DEBT-305, 6h)
- [ ] AC13: `job_queue.py` (2152 LOC) decomposto por dominio de job: `jobs/llm_jobs.py`, `jobs/excel_jobs.py`, `jobs/cache_jobs.py` (ou similar)
- [ ] AC14: `cron_jobs.py` (2218 LOC) decomposto: `crons/cache_warmup.py`, `crons/cleanup.py`, `crons/health_check.py` (ou similar)
- [ ] AC15: ARQ job discovery continua funcionando -- worker encontra e executa todos os jobs registrados

## Tasks

### Phase 1: filter/core.py (DEBT-301)
- [ ] T1: Analisar `filter/core.py` -- mapear funcoes, dependencias internas, exports publicos. Verificar coverage baseline (`pytest --cov=filter`). (1h)
- [ ] T2: Criar submodulos e mover funcoes, um submodulo por commit. Build + test apos cada move. (5h)
- [ ] T3: Atualizar `filter/__init__.py` com re-exports. Verificar imports dos 14 test files. (1h)
- [ ] T4: Verificar coverage >80% por submodulo. (1h)

### Phase 2: schemas.py (DEBT-302)
- [ ] T5: Mapear schemas por dominio (search, billing, pipeline, user, analytics, common). (0.5h)
- [ ] T6: Criar `schemas/` package e mover modelos por dominio. (4h)
- [ ] T7: Verificar 49 routes importam corretamente. Run OpenAPI snapshot test. (1.5h)

### Phase 3: job_queue.py + cron_jobs.py (DEBT-305)
- [ ] T8: Mapear jobs e crons por categoria. (0.5h)
- [ ] T9: Criar `jobs/` e `crons/` packages. Mover codigo. (4h)
- [ ] T10: Verificar ARQ discovery e cron registration. (1.5h)

### Phase 4: Backend Packaging (DEBT-304)
- [ ] T11: Mapear 68 top-level files para packages propostos. (1h)
- [ ] T12: Criar packages incrementalmente -- mover 1 grupo de cada vez (filtering primeiro, depois search, depois pncp). (8h)
- [ ] T13: Verificar OpenAPI schema, test suite, imports. (3h)

## Testes Requeridos

- **CRITICAL per-step:** Full test suite (`python scripts/run_tests_safe.py --parallel 4`) apos CADA file move. 7656 tests, 0 new failures.
- **filter:** `pytest --cov=filter --cov-report=term-missing` >80%. `from filter import classificar_resultado` sucesso.
- **schemas:** All 49 routes import correctly. OpenAPI snapshot unchanged.
- **jobs/crons:** ARQ worker startup succeeds. Mock job execution works.
- **packaging:** `python -c "from <package> import <key_function>"` for each new package.
- **OpenAPI:** `openapi_schema.diff.json` shows zero changes to public API.

## Definition of Done

- [ ] All ACs checked
- [ ] No file in backend/ exceeds 1000 LOC (excluding test files and generated code)
- [ ] All imports via `__init__.py` facades work
- [ ] OpenAPI schema unchanged
- [ ] Tests pass (7656 backend, 5733 frontend)
- [ ] No regressions
- [ ] Code reviewed (architect sign-off on package structure)

## File List

### filter/ decomposition
- `backend/filter/core.py` (decompose)
- `backend/filter/keyword_matching.py` (new)
- `backend/filter/density_scoring.py` (new)
- `backend/filter/uf_filter.py` (new)
- `backend/filter/value_filter.py` (new)
- `backend/filter/status_validation.py` (new)
- `backend/filter/__init__.py` (update re-exports)

### schemas/ decomposition
- `backend/schemas.py` (decompose)
- `backend/schemas/__init__.py` (new, with re-exports)
- `backend/schemas/search.py` (new)
- `backend/schemas/billing.py` (new)
- `backend/schemas/pipeline.py` (new)
- `backend/schemas/user.py` (new)
- `backend/schemas/analytics.py` (new)

### jobs/ + crons/ decomposition
- `backend/job_queue.py` (decompose)
- `backend/cron_jobs.py` (decompose)
- `backend/jobs/__init__.py` (new)
- `backend/crons/__init__.py` (new)

### Backend packaging
- Various top-level `.py` files moved into packages
- New `__init__.py` files for each package

## Notas

- **MAIOR RISCO do epic inteiro.** 32h de refactoring em codigo com 7656 testes. Um import quebrado pode causar cascata de falhas.
- **Regra de ouro:** Commit apos cada file move. `git stash` antes de cada operacao. Nunca mover mais de 1 file sem rodar testes.
- **Facade pattern e OBRIGATORIO:** Nenhum import externo pode quebrar. `from filter import X` DEVE funcionar apos decomposicao. Usuarios do modulo nao precisam saber da estrutura interna.
- **filter/core.py e o mais arriscado:** 3871 LOC + 14 test files (3704 LOC de testes). Verificar coverage >80% ANTES de comecar para ter baseline de seguranca.
- **DEBT-304 (packaging) depende dos outros 3:** Primeiro decompor filter, schemas, jobs/crons. Depois reorganizar top-level files em packages. A ordem importa porque packaging muda paths de import.
- **OpenAPI snapshot:** O teste `openapi_schema.diff.json` ja existe no repo. Qualquer mudanca na API publica causa falha no snapshot -- isso e a safety net.
- **Error handling patterns em job_queue/cron_jobs:** QA flagou como gap no review. Documentar patterns encontrados durante decomposicao.
