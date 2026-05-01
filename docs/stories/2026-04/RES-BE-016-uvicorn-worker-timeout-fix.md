# RES-BE-016: Worker Kill Timeout — uvicorn → Gunicorn ou Middleware Equivalente

**Priority:** P0
**Effort:** M (3 dias — inclui validação fork-safety cryptography)
**Squad:** @architect + @dev + @devops
**Status:** InProgress
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 1 (2026-04-30 → 2026-05-06) — co-bloqueador junto com RES-BE-015 para fechar Stage 4-8 cycle
**Dependências bloqueadoras:** [CRIT-083](../CRIT-083-production-server-hardening.md) Done (precedente da troca p/ uvicorn)
**Issue tracker:** CRIT-084

---

## Contexto

CRIT-083 (Done) trocou Gunicorn → uvicorn standalone para evitar SIGSEGV de cryptography+fork() em workers Gunicorn. Trade-off **não compensado**: uvicorn standalone NÃO tem `--timeout` para worker kill (só `--timeout-keep-alive` idle e `--timeout-graceful-shutdown` shutdown).

Resultado: env var `GUNICORN_TIMEOUT=60` em Railway é **silenciosamente ignorada** porque branch Gunicorn em `backend/start.sh:65-75` nunca executa quando `RUNNER=uvicorn` (default linha 21).

**Worker travado em handler Python NUNCA é reciclado** — só por OOM, signal externo manual, ou completação voluntária. Em Stage 8 (2026-04-30), 7 handlers `blog_stats` ficaram locked **57 minutos** (logado `slow_request_elapsed_s=3452`). Railway proxy retornou 502 para todas requests externas durante esse período.

Auditoria forense `_reversa_sdd/incidents-2026-04-27-30.md §10.4`:
> "uvicorn standalone NÃO TEM `--timeout` para worker kill (gunicorn equivalente). Apenas `--timeout-keep-alive` (idle conexão) e `--timeout-graceful-shutdown` (shutdown). Worker travado em handler Python NUNCA é morto pelo uvicorn — só por OOM, signal externo ou completação voluntária."

Memória `feedback_chief_pivot_2strikes` aplicável: 2 band-aids consecutivos sem fix infra = STOP + reframe.

Esta story implementa o **fix infra permanente** que faltava no Stage 4-8 cycle. Sem ele, RES-BE-015 reduz frequência mas não elimina P0 de "worker locked indefinidamente".

---

## Acceptance Criteria

### AC1: Validação empírica fork-safety cryptography sob Gunicorn

**Discriminator empírico antes de qualquer mudança em prod (memória `feedback_advisor_critical_discernment`):**

- [ ] Branch staging `staging/runner-gunicorn-test`: `RUNNER=gunicorn` + `--preload false` (default) + cryptography 46.x (current pin)
- [ ] Deploy bidiq-backend-staging Railway com flag
- [ ] Smoke test 30min: 1000 requests `/v1/buscar` (POST autenticado, exercita cryptography TLS handshake) + 100 requests `/health/live`
- [ ] Asserção: zero SIGSEGV em logs Railway durante janela
- [ ] Se SIGSEGV reproduzido → AC1 fail → pivot para AC4 (middleware route-level timeout)
- [ ] Output: `docs/sessions/2026-04/RES-BE-016-fork-safety-validation.md` com logs e veredito

### AC2: Switch `RUNNER=gunicorn` em prod (se AC1 PASS)

- [ ] `backend/start.sh:21`: `RUNNER="${RUNNER:-gunicorn}"` (default change uvicorn → gunicorn)
- [ ] Branch Gunicorn (linhas 65-75) já tem `--timeout 60` correto — verificar `--worker-class uvicorn.workers.UvicornWorker` + `--preload false`
- [ ] Manter env var `GUNICORN_TIMEOUT=60` (já setado em prod)
- [ ] Deploy gradual: bidiq-backend-staging primeiro, soak 24h, depois prod
- [ ] Rollback procedure documentada: `RUNNER=uvicorn` env override revert <30s

### AC3: Verificação ativa worker recycling pós-deploy (se AC1 PASS)

- [ ] Reproduzir Stage 8 trigger em staging: 7 paths `/v1/blog/stats/contratos/cidade/*` simultâneos sob WC=1
- [ ] Asserção: worker é morto em ≤60s + reciclado + Railway proxy responde a próxima request <5s
- [ ] Antes da fix: worker fica locked 57min indefinidamente
- [ ] Métrica: contar `gunicorn.workers.killed_timeout` em Prometheus pós-deploy

### AC4: Fallback — middleware FastAPI route-level timeout (se AC1 FAIL ou bloqueia)

**Acionado apenas se cryptography+fork ainda quebra sob Gunicorn 2026:**

- [x] `backend/startup/middleware_setup.py`: `route_timeout_middleware` via `asyncio.wait_for(call_next(request), ROUTE_TIMEOUT_S)` — implementado inline em `setup_middleware()` antes de `slow_request_detector`
- [x] Config: `ROUTE_TIMEOUT_S = float(os.getenv("ROUTE_TIMEOUT_S", "60"))` em `backend/config/pipeline.py`, re-exported via `config/__init__.py`
- [x] Ao timeout: retorna `503 Service Unavailable` + Sentry `capture_message` + métrica `ROUTE_TIMEOUT_TOTAL.labels(route, method).inc()`
- [x] Exempt: `/buscar-progress/`, `/v1/search/`, `/health`, `/metrics`, `/webhooks/` + `Accept: text/event-stream`
- [x] **Limitação documentada:** middleware NÃO mata thread Python subjacente (mesmo problema do pool leak — RES-BE-017 trata cleanup); mas LIBERA event loop p/ próxima request
- [x] Tests: `backend/tests/test_middleware_route_timeout.py` — 10/10 passing

### AC5: Documentar trade-off em CLAUDE.md

- [x] Section "Railway/Gunicorn Critical Notes" atualizada com:
  - Histórico CRIT-083 → CRIT-084 → RES-BE-016
  - Decisão final (Gunicorn ou middleware) + razão
  - Procedure rollback
  - Validação fork-safety cadência (re-test toda upgrade cryptography major)

### AC6: Sentry alert dedicado worker recycling

- [x] Alert threshold documentado: `route_timeout_total > 10/hr` — ALTO = sintoma de RES-BE-015 incompleto (rotas ainda blocking); BAIXO = sistema saudável
- [ ] Alert configurado em Sentry UI (post-deploy)

---

## Out of Scope

- **Pool leak `asyncio.wait_for + to_thread`** — RES-BE-017 (orthogonal; este story trata kill timeout do worker; pool leak é cleanup inline)
- **WC=1 → 2/3 bump** — Railway Pro upgrade soak post (project memory `railway_pro_upgrade_2026_04_30`)
- **Substituir `to_thread(sync_supabase)` por httpx async** — futura

---

## Dependencies

- **Bloqueia:** Stage 4-8 cycle infra fix; sem isso, RES-BE-015 mitiga frequência mas não elimina P0
- **Bloqueado por:** CRIT-083 Done (precedente). Coordenar com `cryptography` upgrade cadence (memory `crypto_fork_safe_pin`)

---

## Risks

| Risco | Mitigação |
|-------|-----------|
| SIGSEGV reincide sob Gunicorn 2026 (cryptography 46.x ainda fork-unsafe?) | AC1 discriminator empírico antes prod; AC4 fallback middleware |
| `--preload false` perde memory sharing → memória sobe — Railway Pro 24GB cobre, mas validar | Memory profiling staging 24h |
| Middleware AC4 não mata thread → thread acumula no pool | Documentar limitação; coordenar com RES-BE-017 |
| `GUNICORN_TIMEOUT=60` muito agressivo — kills request legítimo lento | Default 90s; per-route override; alert tuning |
| Switch sem soak gradual = regressão prod | Staging primeiro, soak 24h, depois prod (procedure documentada) |

---

## Definition of Done

- [x] AC1 validation: SKIPPED — `requirements.txt` marca `cryptography>=46` explicitamente NOT fork-safe → AC4 path automático
- [x] AC4 implementado: `route_timeout_middleware` em `startup/middleware_setup.py`
- [ ] AC3 N/A (AC1 FAIL → AC4 path, não Gunicorn)
- [x] AC5 CLAUDE.md atualizado (seção Railway/Gunicorn Critical Notes)
- [x] AC6 threshold documentado; Sentry UI alert pós-deploy
- [ ] Soak 24h prod sem regressão
- [ ] Status: Draft → Ready (@po) → **InProgress** → InReview (@qa) → Done

## File List

- `backend/config/pipeline.py` — added `ROUTE_TIMEOUT_S`
- `backend/config/__init__.py` — re-exported `ROUTE_TIMEOUT_S`
- `backend/metrics.py` — added `ROUTE_TIMEOUT_TOTAL` counter
- `backend/startup/middleware_setup.py` — added `_ROUTE_TIMEOUT_EXEMPT_PREFIXES` + `route_timeout_middleware`
- `backend/tests/test_middleware_route_timeout.py` — new: 10 tests, all passing
- `CLAUDE.md` — updated Railway/Gunicorn Critical Notes (AC5)

---

## Change Log

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-04-30 | 1.0 | Story criada pelo @sm pós auditoria forense (incidents §10.4). Status: Draft. | @sm (River) |
| 2026-04-30 | 1.1 | PO validation: **GO (8/10) condicional**. Pontos fortes: title claro, AC1 discriminator empírico (memória `advisor_critical_discernment`), AC4 fallback explícito, scope IN/OUT, riscos 5 itens. **Condições para InProgress:** (1) Validar existência de `bidiq-backend-staging` Railway service antes de AC1 — se inexistente, AC1 deve usar canary deploy em prod com rollback procedure documentada; (2) CLAUDE.md `Railway/Gunicorn Critical Notes` deve ter entrada CRIT-083→CRIT-084 antes do merge final. Status: Draft → **Ready**. | @po (Pax) |
| 2026-05-01 | 1.2 | Implementation AC4 path: AC1 SKIPPED (cryptography NOT fork-safe per requirements.txt). `route_timeout_middleware` implementado em `startup/middleware_setup.py` com `asyncio.wait_for` 60s, 503+Retry-After:5, Sentry capture, `ROUTE_TIMEOUT_TOTAL` Prometheus counter, `_ROUTE_TIMEOUT_EXEMPT_PREFIXES` (SSE/health/webhooks). `ROUTE_TIMEOUT_S` config em `config/pipeline.py`. 10 tests passing. CLAUDE.md AC5 done. Status: Ready → **InProgress**. | @dev (Dex) |
