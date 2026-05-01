# Story DEBT-103: LLM & Search Resilience — Timeouts, Cache Bounds & UF Batching

## Metadata
- **Story ID:** DEBT-103
- **Epic:** EPIC-DEBT
- **Batch:** B (Foundation)
- **Sprint:** 2-3 (Semanas 3-6)
- **Estimativa:** 24h
- **Prioridade:** P1-P2
- **Agent:** @dev

## Descricao

Como engenheiro de confiabilidade, quero implementar protecoes contra thread starvation do OpenAI client, limitar o crescimento de memoria do LRU cache, adicionar contadores de timeout por future na classificacao LLM, implementar timeout por UF com modo degradado, habilitar batching faseado de UFs, e implementar merge-enrichment de duplicatas, para que o pipeline de busca seja resiliente a falhas de terceiros e eficiente em recursos.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| SYS-010 | OpenAI client timeout=15s (5x p99) — risco de thread starvation em LLM hangs | HIGH | 4h |
| SYS-012 | LRU cache unbounded — 5000 entry limit necessario para prevenir memory growth | HIGH | 4h |
| SYS-011 | Merge-enrichment from lower-priority duplicates nao implementado | HIGH | 8h |
| SYS-013 | Per-future timeout counter para LLM batch classification faltando | HIGH | 4h |
| SYS-014 | Per-UF timeout (30s) + degraded mode (15s) para timeout cascade prevention | HIGH | 4h |
| SYS-015 | Phased UF batching (size=5, delay=2s) para reduzir pressao na PNCP API | HIGH | 4h |

## Acceptance Criteria

- [x] AC1: OpenAI client timeout reduzido para 3-5s (alinhado com p99 observado)
- [x] AC2: Thread starvation test — 50 concurrent LLM calls nao bloqueiam event loop
- [x] AC3: LRU cache com limite de 5000 entries; eviction funciona corretamente
- [x] AC4: Metricas de cache hit/miss/eviction expostas via Prometheus
- [x] AC5: Dedup merge-enrichment: campos nao-vazios de fonte lower-priority enriquecem resultado
- [x] AC6: Per-future timeout counter: metricas por future individual (nao so batch total)
- [x] AC7: Per-UF timeout de 30s normal, 15s em modo degradado; cascata prevenida
- [x] AC8: UF batching: max 5 UFs simultaneas com 2s delay entre batches
- [x] AC9: Config variaveis para todos os valores: `OPENAI_TIMEOUT_S`, `LRU_MAX_SIZE`, `PNCP_BATCH_SIZE`, `PNCP_BATCH_DELAY_S`

## Testes Requeridos

- **SYS-010:** Simular OpenAI timeout > threshold; verificar que request falha gracefully sem bloquear
- **SYS-012:** Inserir 5001 entries; verificar que oldest entry foi evicted; verificar metricas
- **SYS-011:** Mock de 2 fontes com dados complementares; verificar merge correto por prioridade (PNCP>PCP>ComprasGov)
- **SYS-013:** Mock batch com 1 future timeout; verificar que counter individual incrementa
- **SYS-014:** Mock 1 UF com timeout > 30s; verificar degraded mode ativa em 15s
- **SYS-015:** Test com 15 UFs; verificar 3 batches de 5 com 2s delay
- Full suite: `python scripts/run_tests_safe.py` — 0 failures

## Notas Tecnicas

- **SYS-010:** Arquivo `backend/llm.py` ou `backend/llm_arbiter.py`. OpenAI SDK suporta `timeout` param.
- **SYS-012:** Arquivo `backend/cache.py` (InMemoryCache). Python `functools.lru_cache` ou custom bounded dict.
- **SYS-011:** Arquivo `backend/consolidation.py`. Priority: PNCP=1, PCP=2, ComprasGov=3. Merge non-null fields.
- **SYS-013:** Arquivo `backend/llm_arbiter.py`. Usar `asyncio.wait()` com per-future timeout tracking.
- **SYS-014:** Arquivo `backend/search_pipeline.py` ou `backend/pncp_client.py`. Per-UF asyncio.wait_for().
- **SYS-015:** Ja documentado em CLAUDE.md: PNCP_BATCH_SIZE=5, PNCP_BATCH_DELAY_S=2.0. Verificar se implementado.

## Dependencias

- **Depende de:** Nenhuma (pode ser parallelizado com DEBT-102)
- **Bloqueia:** Nenhuma diretamente

## Definition of Done

- [x] Codigo implementado (6 items)
- [x] Testes unitarios para cada item passando (36 tests in test_debt103_llm_search_resilience.py)
- [x] Metricas Prometheus expostas (cache, timeouts)
- [x] Config variaveis documentadas em `.env.example`
- [ ] Code review aprovado
- [ ] Deploy em staging com monitoramento
- [x] Documentacao atualizada
