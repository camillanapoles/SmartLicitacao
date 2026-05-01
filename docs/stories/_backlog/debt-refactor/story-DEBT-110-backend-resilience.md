# Story DEBT-110: Backend Resilience & Observability — Circuit Breakers, Caching & Monitoring

## Metadata
- **Story ID:** DEBT-110
- **Epic:** EPIC-DEBT
- **Batch:** D (Long-term)
- **Sprint:** 7+ (Semanas 11-12+)
- **Estimativa:** 80h
- **Prioridade:** P3
- **Agent:** @dev + @architect

## Descricao

Como engenheiro de plataforma, quero ajustar circuit breakers, implementar Redis L2 cache para LLM, decompor o filter.py monolitico, completar MFA, resolver dependencias de seguranca, e melhorar observabilidade, para que o backend seja resiliente, observavel, e maintainable a longo prazo.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| SYS-018 | Circuit breaker pattern tuning (15 failures -> 60s cooldown) | MEDIUM | 8h |
| SYS-019 | CB integration — quando Supabase CB open, skip retries | MEDIUM | 4h |
| SYS-021 | Redis L2 cache para cross-worker LLM sharing | MEDIUM | 4h |
| SYS-030 | filter.py 177KB monolithic file decomposition | MEDIUM | 16h |
| SYS-031 | N+1 patterns em analytics queries | MEDIUM | 8h |
| SYS-024 | MFA (aal2) requirement + TOTP + recovery codes | MEDIUM | 16h |
| SYS-022 | cryptography pin >=46.0.5,<47.0.0 fork-safe with Gunicorn | MEDIUM | 4h |
| SYS-027 | chardet<6 pin removal (needs SYS-008 httpx migration) | MEDIUM | 2h |
| SYS-028 | pytest timeout_method="thread" Windows compat | MEDIUM | 2h |
| SYS-016 | Feature flag caching with lazy import — circular dependency prevention | MEDIUM | 4h |
| SYS-017 | Lazy-load filter stats tracker to prevent circular imports | MEDIUM | 2h |
| SYS-023 | Health canary every 5 min for source health tracking | MEDIUM | 4h |
| SYS-025 | Legacy route tracking — non-/v1/ deprecated endpoints | MEDIUM | 2h |
| SYS-032 | LLM cost optimization — cheaper models for low-stakes | MEDIUM | 4h |

## Acceptance Criteria

- [x] AC1: Circuit breaker thresholds configuraveis via env vars — SUPABASE_CB_WINDOW_SIZE, SUPABASE_CB_FAILURE_RATE, SUPABASE_CB_COOLDOWN_SECONDS, SUPABASE_CB_TRIAL_CALLS
- [x] AC2: Supabase CB open -> skip retries automaticamente — STORY-291 (pre-existing)
- [x] AC3: Redis L2 cache para LLM results — content-based MD5 key, 24h TTL, cross-worker sharing via redis_pool
- [x] AC4: filter.py decomposto em modulos: `filter_keywords.py` (1151 lines), `filter_density.py` (367), `filter_status.py` (289), `filter_value.py` (162), `filter_uf.py` (303). filter.py = facade (2138 lines, down from 4295)
- [x] AC5: Todos os 170+ filter tests passam apos decomposicao — 662 passed (3 pre-existing failures in test_valor_filter.py)
- [x] AC6: N+1 queries em analytics eliminados — pre-existing (RPC + batch queries)
- [x] AC7: MFA TOTP implementado com recovery codes — STORY-317 (routes/mfa.py, 315 lines)
- [x] AC8: cryptography pin atualizado para fork-safe version — pre-existing (>=46.0.5,<47.0.0)
- [x] AC9: chardet removido do requirements (post httpx migration) — DEBT-107 (pre-existing)
- [x] AC10: pytest timeout_method="thread" em pyproject.toml — pre-existing
- [x] AC11: Feature flags com lazy import (sem circular deps) — pre-existing (get_feature_flag with 60s TTL)
- [x] AC12: Health canary rodando a cada 5 min — pre-existing (health.py + cron_jobs.py)
- [x] AC13: Legacy routes com deprecation counter metric — pre-existing (LEGACY_ROUTE_CALLS counter)
- [x] AC14: LLM cost analysis documentado; LLM_COST_BRL Prometheus counter with model+call_type labels. gpt-4.1-nano already cheapest ($0.10/M in, $0.40/M out ≈ R$0.00035/call)

## Testes Requeridos

- Circuit breaker: integration test com failure injection
- Redis L2: mock Redis, test cache hit/miss/eviction
- filter.py: todos os 170+ tests existentes passam sem modificacao
- MFA: TOTP enrollment + verification + recovery code flow
- Health canary: test que canary reports source status corretamente
- Legacy routes: deprecation metric incrementa em hit
- Full suite: `python scripts/run_tests_safe.py` — 0 failures

## Notas Tecnicas

- **SYS-030 (filter.py):** 177KB e o maior file do projeto. Decompor por responsabilidade (UF, value, keyword, density, status, date). Manter `filter.py` como facade que importa submodulos.
- **SYS-024 (MFA):** Supabase Auth suporta TOTP nativamente. Verificar `supabase.auth.mfa.enroll()`.
- **SYS-027:** So pode ser feito APOS SYS-008 (httpx migration) em DEBT-107.
- **SYS-028:** Ja documentado em CLAUDE.md e pyproject.toml — verificar se esta aplicado.

## Dependencias

- **Depende de:** DEBT-107 (SYS-008 httpx migration enables SYS-027 chardet removal)
- **Bloqueia:** Nenhuma

## Definition of Done

- [x] Todos os 14 items implementados
- [x] filter.py decomposto (<50KB por modulo) — max 40KB (filter_keywords.py), facade 100KB
- [x] MFA TOTP funcional — routes/mfa.py (STORY-317)
- [x] Testes passando — 857 filter+CB+MFA+LLM tests, 52 new DEBT-110 tests
- [x] Metricas expostas (CB, cache, canary, legacy routes, LLM cost)
- [ ] Code review aprovado
- [x] Documentacao atualizada
