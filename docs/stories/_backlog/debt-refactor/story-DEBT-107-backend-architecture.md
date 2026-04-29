# Story DEBT-107: Backend Architecture — main.py Decomposition & httpx Migration

## Metadata
- **Story ID:** DEBT-107
- **Epic:** EPIC-DEBT
- **Batch:** C (Optimization)
- **Sprint:** 4-6 (Semanas 7-10)
- **Estimativa:** 48h
- **Prioridade:** P2
- **Agent:** @architect + @dev

## Descricao

Como arquiteto de software, quero completar a decomposicao do main.py monolitico, migrar completamente de `requests` para `httpx`, e implementar merge-enrichment de dados entre fontes, para que o backend tenha uma arquitetura modular, dependencias modernas, e dados de busca enriquecidos.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| SYS-006 | Monolith main.py decomposition — Sentry, lifespan, state extraidos mas incompleto | HIGH | 16h |
| SYS-008 | `requests` library still needed for sync PNCPClient fallback; fully migrate to httpx | HIGH | 16h |
| SYS-007 | DB long-term optimization — 18 items including index bloat and N+1 queries (DEBT-017) | HIGH | 16h |

## Acceptance Criteria

- [x] AC1: main.py reduzido para <100 LOC — apenas app factory + route registration (79 LOC)
- [x] AC2: Sentry config em `backend/startup/sentry.py`
- [x] AC3: Lifespan logic em `backend/startup/lifespan.py`
- [x] AC4: App state initialization em `backend/startup/state.py`
- [x] AC5: Middleware setup em `backend/startup/middleware_setup.py`
- [x] AC6: `requests` removido do requirements.txt
- [x] AC7: Sync PNCPClient fallback usa `httpx.Client` (wrapped em `asyncio.to_thread()`)
- [x] AC8: Todas as chamadas HTTP no codebase usam httpx (0 `import requests` results)
- [x] AC9: SYS-027 (chardet pin) automaticamente resolvido pela remocao de requests
- [x] AC10: N+1 queries em analytics ja resolvidos (STORY-202 DB-M07 RPC — single query)
- [x] AC11: Zero import errors apos decomposicao (`from main import app` OK)

## Testes Requeridos

- **SYS-006:** `python -c "from main import app"` — funciona sem erros
- **SYS-006:** `uvicorn main:app` — startup sem warnings
- **SYS-006:** Full test suite — 0 failures (imports nao quebram)
- **SYS-008:** `pip install -r requirements.txt` sem `requests`
- **SYS-008:** grep codebase por `import requests` — 0 results
- **SYS-008:** PNCPClient sync fallback test com httpx mock
- **SYS-007:** Analytics query performance — verificar N+1 eliminados via explain analyze
- Full suite: `python scripts/run_tests_safe.py` — 0 failures

## Notas Tecnicas

- **SYS-006 (main.py Decomposition):**
  - Ja extraido: Sentry, lifespan, state (3 modules)
  - Faltam: middleware setup, CORS config, exception handlers, route registration
  - Pattern: app factory (`create_app()`) em main.py
  - Cuidado com circular imports — usar lazy imports onde necessario

- **SYS-008 (httpx Migration):**
  - `requests` usado apenas em sync PNCPClient fallback
  - httpx e API-compatible: `httpx.get()` similar a `requests.get()`
  - Sync httpx client: `httpx.Client()` substitui `requests.Session()`
  - Remover `requests`, `chardet<6` (SYS-027) do requirements.txt
  - Verificar que `urllib3` tambem pode ser removido se nao usado diretamente

- **SYS-007 (DB Optimization):**
  - N+1 em analytics: batch queries com JOINs
  - Index bloat: verificar com `pg_stat_user_indexes`
  - 18 items do DEBT-017 — priorizar os que impactam performance

## Dependencias

- **Depende de:** Nenhuma
- **Bloqueia:** DEBT-110 (SYS-008 httpx migration enables SYS-027 chardet pin removal)

## Definition of Done

- [x] main.py < 100 LOC (79 LOC)
- [x] Zero `import requests` no codebase
- [x] `requests` removido de requirements.txt
- [x] N+1 queries eliminados em analytics (STORY-202 DB-M07 RPC)
- [x] Full test suite passando (pre-existing failures only)
- [ ] Code review aprovado
- [x] Documentacao atualizada
