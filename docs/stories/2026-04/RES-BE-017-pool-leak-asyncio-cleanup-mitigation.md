# RES-BE-017: Pool Leak — Mitigação `asyncio.wait_for` + `asyncio.to_thread` Cleanup Inline

**Priority:** P0
**Effort:** L (5 dias — investigação + spike + sweep + soak)
**Squad:** @architect + @dev + @qa
**Status:** Deferred-S3
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 2 (2026-05-07 → 2026-05-13) — não-bloqueador imediato pós RES-BE-015+016, mas previne classe inteira de event loop saturation
**Dependências bloqueadoras:** [RES-BE-015](RES-BE-015-budget-wrap-11-longtail-seo-routes.md) (sweep budget primeiro reduz superfície), [RES-BE-016](RES-BE-016-uvicorn-worker-timeout-fix.md) (worker kill garante recycling mesmo com leak)
**Issue tracker:** POOL-LEAK-001

---

## Contexto

Stage 8 (2026-04-30) revelou cadeia de event loop saturation:

1. Handler chama `await asyncio.wait_for(asyncio.to_thread(sync_supabase_query), timeout=10.0)`
2. Timeout 10s dispara → `wait_for` cancela ESPERA do coroutine
3. Thread Python **continua executando** `sync_supabase_query` (Python não pode cancelar threads externamente)
4. Query Supabase prossegue até `statement_timeout=15s` matar
5. `wait_for` cleanup chama `_call_check_cancel` no future → **bloqueia event loop INLINE até thread completar**
6. Event loop tick durations: 14-48s (saudável <10ms)
7. Outras requests via Railway proxy ficam queued >60s = 502 externo
8. Mais Googlebot waves chegam = mais cancelamentos pendentes = mais ticks longos = saturation cascade

Evidência empírica logada (Railway 2026-04-30 21:07:27 UTC):
```
[WARN] Executing <Task pending ...> took 14.944 seconds
[WARN] Executing <Task pending ...> took 31.350 seconds
[WARN] Executing <Task pending ...> took 48.747 seconds
   wait_for=<Future pending cb=[_chain_future.<locals>._call_check_cancel()]>
```

Auditoria forense `_reversa_sdd/incidents-2026-04-27-30.md §10.5-10.6` documenta cadeia completa. Memória `feedback_pool_leak_caller_timeout_vs_sql_timeout` (registrada Stage 6) confirma que tighten `statement_timeout=8s` Supabase service_role **piorou** o problema (cleanup mais frequente, mais ticks longos). FLOOR validado = 15s.

**RES-BE-015 reduz freqüência (budget=5s ao invés de 10s minimiza chance de cancel).** **RES-BE-016 garante worker recycling se travar.** Mas nenhuma das duas elimina a CLASSE de event loop saturation durante cleanup. Esta story trata a raiz arquitetural.

---

## Acceptance Criteria

### AC1: Investigação — provar root cause empiricamente

**Discriminator empírico antes de qualquer mudança (memória `feedback_advisor_critical_discernment`):**

- [ ] Reproduzir em staging: handler que chama `asyncio.wait_for(asyncio.to_thread(slow_sync_query), timeout=2.0)` com query Supabase que roda 10s
- [ ] Medir event loop tick durations via `loop.set_debug(True)` + `asyncio.events._format_handle`
- [ ] Confirmar ticks longos correlacionam com fase cleanup (post-cancel, pre-thread-completion)
- [ ] Output: `docs/sessions/2026-04/RES-BE-017-pool-leak-reproduction.md` com traces
- [ ] Se reprodução **falha** (ticks <100ms mesmo sob cancel) → root cause real é outro (refrão para AC4 spike alternativo)

### AC2: Spike — substituir `to_thread(sync_supabase)` por httpx async direto em 1 rota piloto

- [ ] Rota piloto: `routes/blog_stats.py::contratos_cidade_setor_handler` (Sentry P0 Stage 8 root cause)
- [ ] Substituir `asyncio.to_thread(supabase.table().select().execute())` por:
  ```python
  async with httpx.AsyncClient() as client:
      resp = await client.post(
          f"{SUPABASE_URL}/rest/v1/rpc/...",
          headers={...},
          json={...},
          timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
      )
  ```
- [ ] Reusar lógica `backend/supabase_client.py::sb_execute` se já existe pattern; senão criar `sb_execute_async`
- [ ] Cancel via `asyncio.wait_for(client.post(...), timeout=5.0)` agora **realmente cancela** (httpx async respeita cancel)
- [ ] Reproduzir AC1 trigger no piloto — esperado: tick durations <100ms p99 mesmo sob cancel
- [ ] Métrica: `smartlic_route_pool_leak_ticks{route}` deve cair pra zero no piloto

### AC3: Sweep gradual após validação piloto

**Acionado apenas se AC2 PASS:**

- [ ] Mapear todos callsites `asyncio.to_thread(*supabase*)` em backend/routes — provável ~60+ ocorrências
- [ ] Priorizar pelas 11 rotas RES-BE-015 (Sentry P0+P1)
- [ ] Migrar batch-by-batch (~10 callsites/PR — não single PR multi-arquivo aqui pois mudança arquitetural maior)
- [ ] Cada batch tem soak 24h staging antes próximo
- [ ] Helper `backend/supabase_client.py::sb_execute_async` testado standalone

### AC4: Fallback — wrapper `_run_with_budget` com cleanup background (se AC2 FAIL)

**Acionado apenas se httpx async tem regressão (latência ou auth):**

- [ ] Modificar `backend/pipeline/budget.py::_run_with_budget`:
  ```python
  async def _run_with_budget(coro, *, budget, ...):
      task = asyncio.create_task(coro)
      try:
          return await asyncio.wait_for(task, timeout=budget)
      except asyncio.TimeoutError:
          # cleanup em background — não bloqueia event loop
          asyncio.create_task(_drain_cancelled_task(task), name="cleanup")
          return None
  
  async def _drain_cancelled_task(task):
      try:
          await asyncio.wait_for(task, timeout=20.0)
      except (asyncio.TimeoutError, asyncio.CancelledError):
          pass
  ```
- [ ] Limitação: thread Python continua rodando em paralelo até completar; pool ainda pode encher se taxa de cancel > taxa de completação
- [ ] Adicionar `ThreadPoolExecutor` size monitoring + alert se >80% capacity
- [ ] Aceita como mitigação parcial — RES-BE-018 (futura) trata pool sizing

### AC5: Reduzir budget < statement_timeout em todas rotas

**Acionado independente de AC2 ou AC4:**

- [ ] Audit: nenhum `_run_with_budget(..., budget=N)` onde N >= 15.0 (Supabase `statement_timeout` service_role)
- [ ] Memory `pool_leak_caller_timeout_vs_sql_timeout` documenta: budget < SQL timeout evita cleanup overhead
- [ ] Recommended budgets:
  - Quick lookups (single row): 2.0
  - Aggregations: 5.0
  - Full-text search: 8.0
  - Bulk fetches (sitemap-like): 10.0
- [ ] Nenhum endpoint > 12.0 (margin sob FLOOR=15s)

### AC6: Load test reprodutível event loop saturation

- [ ] `backend/tests/load/test_event_loop_saturation.py`: 50 handlers concorrentes que cancelam após 2s; querys Supabase rodam 10s
- [ ] Asserção: tick durations <100ms p99 durante teste
- [ ] Asserção: zero `slow_callback_duration` warnings em logs
- [ ] Run em CI staging weekly

### AC7: Soak 24-72h pós-merge AC2 ou AC4

- [ ] Sentry slow_request decay >50% adicional (sobre baseline RES-BE-015 já alcançado)
- [ ] `/health/live` p99 <1.5s (vs RES-BE-015 baseline <2s)
- [ ] Zero `Executing <Task pending> took >1s` em logs Railway sustentado 72h

---

## Out of Scope

- **ThreadPool sizing tuning** — RES-BE-018 (futura)
- **Replace Supabase Python SDK por SQLAlchemy async** — mudança massiva, fora escopo
- **Connection pool Postgres direto** — mudança arquitetural, fora escopo
- **WC bump** — Railway Pro post-soak

---

## Dependencies

- **Bloqueia:** classe inteira de event loop saturation; sem ele, cada cancel sob carga é potential P0
- **Bloqueado por:** RES-BE-015 (reduz superfície primeiro), RES-BE-016 (worker kill garante recycling se leak não resolvido)
- **Coordena com:** memória `crypto_fork_safe_pin` se mudança Gunicorn (RES-BE-016) for necessária

---

## Risks

| Risco | Mitigação |
|-------|-----------|
| httpx async para Supabase quebra auth (RLS service_role headers) | AC2 piloto valida; existe `sb_execute` precedente em `supabase_client.py` |
| Migração 60+ callsites é massiva — risco de regressão | AC3 batch gradual + soak per-batch |
| AC4 fallback ainda permite pool fill em taxa alta | AC4 documenta limitação; Sentry alert ThreadPool capacity |
| Reprodução AC1 não acontece em staging (carga real diferente) | Usar k6 ou locust para simular Googlebot fan-out exato |
| RES-BE-015 + RES-BE-016 já resolvem 90% — esta story baixa ROI | Validar Sentry pós-RES-BE-015+016 antes de iniciar AC1; pivot para defer se decay já >95% |

---

## Definition of Done

- [ ] AC1 reprodução documented com traces
- [ ] AC2 OU AC4 implementado conforme veredito spike
- [ ] AC3 sweep gradual (se AC2 PASS) — todos batches green
- [ ] AC5 budget audit clean (nenhum >12s)
- [ ] AC6 load test passing weekly em CI staging
- [ ] AC7 soak 72h métricas batem
- [ ] Memory `pool_leak_caller_timeout_vs_sql_timeout` atualizada com solution chosen
- [ ] Status: Draft → Ready (@po) → InProgress → InReview (@qa) → Done

---

## Change Log

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-04-30 | 1.0 | Story criada pelo @sm pós auditoria forense (incidents §10.5-10.6). Status: Draft. | @sm (River) |
| 2026-04-30 | 1.1 | PO validation: **GO (8/10) condicional**. Pontos fortes: AC1 reprodução empírica obrigatória, AC2 piloto antes sweep (memória `feedback_sweep_single_pr_required`), AC4 fallback documentado com limitação. **Condições para InProgress:** (1) AC3 sweep "60+ callsites" excede effort L=5d — split em RES-BE-018 (dedicada ao sweep gradual) ou re-estimar L→XL=8-10d; (2) AC1 reprodução pode falhar se carga staging diferente — adicionar fallback "se reprodução não converge em 4h, usar k6/locust com Googlebot UA simulation"; (3) Validar pré-Sprint 2: se RES-BE-015+016 atingem decay >95% Sentry slow_request, defer esta story para Sprint 3 (ROI baixo). Status: Draft → **Ready** (Sprint 2 conditional). | @po (Pax) |
| 2026-05-02 | 1.2 | **Status Ready → Deferred-S3.** Defer condition (PO validation §3) **triggered** com evidência empírica Sentry: query `confenge/smartlic-backend issues?query=slow_request age:-72h statsPeriod=14d` retorna **0 issues** (zero eventos slow_request nas últimas 72h). Baseline pré-sweep era 208 eventos/24h em 2026-04-30 (memory `project_sentry_tripwire_fired_2026_04_30`); decay observado = **100%** (>> 95% threshold). RES-BE-015 sweeps PR #600 (`--all-routes` 19 callsites) + PR #603 (residuais) + RES-BE-016 worker timeout middleware (PR #588 AC4) + RES-BE-018a (mfa.py PR #589) eliminaram a CLASSE inteira de event loop saturation observável em produção. Próxima reavaliação: se Sentry slow_request reaparecer >5/24h sustained, reabrir esta story imediatamente (move para Ready). Memory `feedback_sweep_single_pr_required` confirmada — single-PR sweep funcionou sem necessidade de mudança arquitetural httpx async. | @dev (Dex) |
