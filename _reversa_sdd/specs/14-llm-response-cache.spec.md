# Spec: LLM Response Cache (Redis)

> Spec executável (SDD) gerada para LLM-CACHE-SPEC-001 em 2026-05-09 (PR #160 shipped 2026-05-08)
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `llm-response-cache`
- **Path**: `backend/llm.py` (helpers `_build_resumo_cache_key`, `get_or_generate_resumo_cached`, constante `_LLM_SUMMARY_CACHE_TTL`)
- **Owner**: Backend Search team (compartilhado com SRE — observabilidade)
- **Status**: shipped 2026-05-08 22:10 BRT (PR #160 — `perf(backend): cache Redis para respostas LLM por licitacao_id+tipo`)

## Purpose

Cache transparente de respostas do GPT-4.1-nano para sumários executivos (`ResumoLicitacoes`) gerados em `gerar_resumo()`. Evita chamadas duplicadas à OpenAI quando o mesmo conjunto de licitações é resumido novamente — economia direta de custo (input $0.10 / output $0.40 per 1M tokens) e redução de p95 latência da etapa LLM no pipeline de busca.

Cache é **passive read-through, write-on-miss**, single-layer (Redis L2 — não há L1 in-memory para LLM como existe no cache de search results). Falha de Redis é graceful: chamada vai direto à OpenAI sem propagar exceção.

## Inputs / Outputs

| Camada | Input | Output |
|--------|-------|--------|
| `_build_resumo_cache_key` | `licitacoes: list[dict]`, `sector_name: str`, `termos_busca: str | None`, `setor_id: str | None` | `str` no formato `llm:summary:{sha256_hex}` |
| `get_or_generate_resumo_cached` (wrapper async) | mesmos 4 args (kwargs `sector_name`, `termos_busca`, `setor_id`) + `licitacoes: list[dict[str, Any]]` | `ResumoLicitacoes` (Pydantic) |
| Redis SET payload | `resumo.model_dump_json()` (str UTF-8) | — |
| Redis GET payload | str (JSON) | rehidrata via `ResumoLicitacoes.model_validate_json` |

## Cache key derivation (SHA-256)

`backend/llm.py:806-838`:

1. Para cada licitação em `licitacoes`, extrai um stable bid ID via fallback chain: `numeroControlePNCP` → `codigoCompra` → `id` (primeiro truthy ganha). Bids sem nenhum desses campos são silenciosamente ignorados na chave (mas continuam no payload da OpenAI — caso edge raro).
2. Monta payload determinístico:
   ```python
   {"bid_ids": sorted(bid_ids), "sector_name": "...", "termos_busca": "...", "setor_id": "..."}
   ```
3. Serializa via `json.dumps(payload, sort_keys=True, ensure_ascii=False)` — `sort_keys=True` é crítico para estabilidade.
4. Hash via `hashlib.sha256(raw.encode()).hexdigest()`.
5. Prefixo namespace: `llm:summary:{digest}` (alinhado com convenção `module:operation:hash` do projeto).

**Order-independence:** garantida por `sorted(bid_ids)` — invocações com a mesma lista em ordens diferentes produzem a mesma chave. Validado por `tests/test_llm_cache.py::test_build_resumo_cache_key_order_independent`.

## TTL policy

- **Constante**: `_LLM_SUMMARY_CACHE_TTL = 7 * 24 * 3600` (7 dias em segundos) — `backend/llm.py:803`.
- **Justificativa**: o conjunto de bids identificado pelos IDs ordenados é determinístico — mesmo input → mesmo sumário (modulo recompute_temporal_alerts). Bids têm dataAberturaProposta no horizonte de poucos dias a semanas; após 7 dias a janela típica já encerrou e o sumário deixaria de ser referenciável de qualquer forma. TTL maior empilharia memória Redis sem ganho prático.
- **Comando Redis**: `SETEX key 604800 value` via `redis_cache.setex(cache_key, _LLM_SUMMARY_CACHE_TTL, resumo.model_dump_json())` em `backend/llm.py:904`.

## Fallback semantics (Redis indisponível)

Wrapper é **fail-open**: qualquer exceção em GET ou SETEX é capturada e logada em DEBUG, sem propagar para o caller.

| Estado Redis | Comportamento |
|--------------|---------------|
| GET → cache hit (str não-vazia) | `ResumoLicitacoes.model_validate_json(cached_raw)` + `recompute_temporal_alerts()` (re-aplica alertas time-sensitive sobre `now()`); incrementa `LLM_SUMMARY_CACHE_HITS` |
| GET → cache miss (None/empty) | incrementa `LLM_SUMMARY_CACHE_MISSES`, chama `gerar_resumo()`, tenta SETEX |
| GET → exceção (CB open, timeout, conexão recusada) | log DEBUG `llm.cache_read_error`, fallthrough para chamar `gerar_resumo()` (tratado como miss sem incrementar contador) |
| SETEX → exceção | log DEBUG `llm.cache_write_error`, retorna `resumo` mesmo assim — fire-and-forget |
| `licitacoes == []` | short-circuit: chama `gerar_resumo([], …)` direto (caso fast-path determinístico em `gerar_resumo:248-255`); Redis não é tocado |

Validado por `tests/test_llm_cache.py::test_redis_unavailable_falls_back_to_openai` e `::test_redis_write_failure_does_not_raise`.

## Wrapper API contract

```python
async def get_or_generate_resumo_cached(
    licitacoes: list[dict[str, Any]],
    *,
    sector_name: str = "licitações",
    termos_busca: str | None = None,
    setor_id: str | None = None,
) -> ResumoLicitacoes
```

- **Async-only**: cache layer requer `await redis_cache.get/setex` — chamadores síncronos devem ir direto a `gerar_resumo()` (não há wrapper sync).
- **Substitui** `gerar_resumo()` em call sites de produção mas **delega** internamente em cache miss — assinatura compatível para drop-in.
- **`recompute_temporal_alerts` é re-aplicado em cache hit** (`backend/llm.py:884`): campos time-sensitive (`alerta_urgencia`, `destaques` com datas) NÃO podem vir cacheados — são recomputados contra `datetime.now(UTC)` e `dataEncerramentoProposta`/`dataAberturaProposta` reais. Garante consistência entre serve cached e serve fresh do mesmo set de bids.

## Functional Requirements

- **FR-1**: Cache key deve ser determinística e order-independent sobre `licitacoes`.
- **FR-2**: Empty input (`licitacoes == []`) NÃO deve tocar Redis.
- **FR-3**: Cache hit NÃO deve chamar OpenAI (asserção via `mock_gerar.assert_not_called`).
- **FR-4**: Cache miss DEVE chamar OpenAI E armazenar resultado com TTL = 7d.
- **FR-5**: Falha de Redis (read OR write) NUNCA deve propagar exceção ao caller.
- **FR-6**: `recompute_temporal_alerts` DEVE ser re-aplicada em cada serve (hit ou miss) — alertas/destaques temporais nunca vêm cacheados.

## Non-Functional Requirements

- **NFR-1**: cache hit latency <50ms p95 (Redis local + JSON deserialize).
- **NFR-2**: cache hit rate observado via `smartlic_llm_summary_cache_hits_total` / (hits + misses) — esperado ≥30% steady-state após warm-up de 24h (validar pós-deploy).
- **NFR-3**: zero impacto na disponibilidade — fallback transparente em outage Redis.
- **NFR-4**: economia de custo OpenAI: cada hit evita ~$0.0002-0.0008 (gpt-4.1-nano @ ~3-5K input + ~500 output tokens) — meta direta da story PR #160.

## Constraints

- **CON-1**: Wrapper async-only — não há equivalente sync. Todos os call sites em prod (search pipeline + ARQ job) já são async.
- **CON-2**: Stable bid ID depende de PNCP/PCP/ComprasGov populando `numeroControlePNCP` / `codigoCompra` / `id`. Bids sintéticos sem qualquer ID degradam cache key (são ignorados na chave mas a chamada ainda funciona).
- **CON-3**: TTL hardcoded em constante de módulo — não há env override para ajuste rápido (sair do path hot requer deploy). Aceito porque 7d é stable.
- **CON-4**: `cache_module.redis_cache` import lazy dentro do wrapper (linhas 876, 902) — evita boot-time hard dependency em Redis quando módulo é importado em testes que não exercitam o path async.

## Test coverage

`backend/tests/test_llm_cache.py` (279 LOC, 9 tests):

| Test | Validates |
|------|-----------|
| `test_build_resumo_cache_key_stable` | FR-1 — same inputs → same key |
| `test_build_resumo_cache_key_different_inputs` | FR-1 — different `sector_name` → different key |
| `test_build_resumo_cache_key_different_bids` | FR-1 — different bid lists → different key |
| `test_build_resumo_cache_key_order_independent` | FR-1 — sorted IDs garantem order-independence |
| `test_build_resumo_cache_key_no_stable_id` | CON-2 — bids sem ID não quebram a função |
| `test_cache_hit_skips_openai` | FR-3 — `gerar_resumo` não é chamado em hit |
| `test_cache_hit_does_not_call_gerar_resumo_second_time` | FR-3 — segunda chamada ainda hits cache |
| `test_cache_miss_calls_openai_and_stores` | FR-4 — miss chama OpenAI E faz SETEX com TTL=604800 |
| `test_redis_unavailable_falls_back_to_openai` | FR-5 — `ConnectionError` em GET não propaga |
| `test_redis_write_failure_does_not_raise` | FR-5 — `TimeoutError` em SETEX não propaga |
| `test_empty_input_bypasses_cache` | FR-2 — Redis nunca é consultado em empty input |
| `test_cache_module_redis_cache_is_importable` | smoke test do singleton |

## Observability

| Métrica Prometheus | Tipo | Definida em |
|--------------------|------|-------------|
| `smartlic_llm_summary_cache_hits_total` | Counter | `backend/metrics.py:1225` |
| `smartlic_llm_summary_cache_misses_total` | Counter | `backend/metrics.py:1230` |

Logs DEBUG (não estruturados como métricas):
- `llm.cache_hit key=…`
- `llm.cache_miss key=…`
- `llm.cache_stored key=… ttl=604800`
- `llm.cache_read_error key=… err=…`
- `llm.cache_write_error key=… err=…`

Hit rate dashboard query Prometheus:
```
rate(smartlic_llm_summary_cache_hits_total[5m]) /
  (rate(smartlic_llm_summary_cache_hits_total[5m]) + rate(smartlic_llm_summary_cache_misses_total[5m]))
```

## Code traceability

- `backend/llm.py:803` — constante `_LLM_SUMMARY_CACHE_TTL = 7 * 24 * 3600`
- `backend/llm.py:806-838` — `_build_resumo_cache_key`
- `backend/llm.py:841-909` — `get_or_generate_resumo_cached` (async wrapper)
- `backend/llm.py:200-403` — `gerar_resumo` (delegate em miss)
- `backend/llm.py:125-198` — `recompute_temporal_alerts` (re-aplicada em hit, linha 884)
- `backend/pipeline/stages/generate.py:273` — call site no estágio `generate` da search pipeline
- `backend/jobs/queue/jobs.py:428` — call site em `llm_summary_job` (ARQ background)
- `backend/metrics.py:1225-1233` — counters Prometheus
- `backend/cache_module.py` — singleton `redis_cache` (interface assumida: `async get(key)`, `async setex(key, ttl, value)`)
- `backend/tests/test_llm_cache.py` (279 LOC) — coverage completo

## Dependencies

- **Upstream**: `cache_module.redis_cache` (cliente Redis async pooled), `OpenAI SDK 1.109` (`gerar_resumo`), `Pydantic 2.12` (`ResumoLicitacoes`).
- **Downstream**: search pipeline stage `generate` + ARQ `llm_summary_job` consomem o wrapper. Excel/PDF não dependem do sumário cacheado diretamente.
- **Sibling specs**: `01-search-pipeline.spec.md` (FR-8 — LLM via ARQ background), `06-jobs-cron.spec.md` (deferred — `llm_summary_job` é hospedado pelo job queue).

## Acceptance Criteria (PR #160)

- AC-1: Mesma busca repetida em janela <7d retorna sumário sem call à OpenAI (validado por `LLM_SUMMARY_CACHE_HITS` incrementando em prod).
- AC-2: Cache transparente — nenhuma mudança no contrato de API exposto ao frontend.
- AC-3: Outage Redis NÃO degrada disponibilidade do `/v1/buscar` (validado por `test_redis_unavailable_falls_back_to_openai`).
- AC-4: TTL = 7 dias asserted no test e na constante de módulo.
- AC-5: Time-sensitive fields (`alerta_urgencia`, `destaques` com datas) sempre refletem `now()` mesmo em hit (FR-6 via `recompute_temporal_alerts`).

## Errors

Wrapper não levanta exceção própria. Erros possíveis:

| Source | Error | Tratamento |
|--------|-------|-----------|
| `gerar_resumo` | `ValueError("OPENAI_API_KEY not set")` | propaga (config error — fail loud) |
| `gerar_resumo` | OpenAI API errors (rate limit, network) | propaga; caller (`llm_summary_job` linha 434) faz fallback para `gerar_resumo_fallback` |
| `redis_cache.get` | `ConnectionError`, `TimeoutError` | swallow + DEBUG log + fallthrough para `gerar_resumo` |
| `redis_cache.setex` | `ConnectionError`, `TimeoutError` | swallow + DEBUG log + retorna resumo gerado |
| `ResumoLicitacoes.model_validate_json` | `ValidationError` (corrupted cache entry) | swallow (capturado pelo `except Exception` largo no read path), trata como miss |

---

## Notas de implementação (contexto histórico)

- PR #160 (`fix/160-llm-response-cache`) merged 2026-05-08. Issue #160 referenciada em comentários inline (`backend/pipeline/stages/generate.py:272`, `backend/jobs/queue/jobs.py:427`).
- Spec criada após o fato (LLM-CACHE-SPEC-001) para fechar lacuna doc-coverage no `_reversa_sdd/`. Confiança 🟢 CONFIRMADO em todas seções porque todo claim referencia código já em `main`.
- Não há L1 in-memory cache para LLM (diferente do search-results-cache que tem InMemoryCache + Supabase). Decisão consciente: setor-aware bid sets são cardinality-alta (cada usuário tem combinação única) → L1 teria hit rate baixo e custo de invalidação não-trivial. Redis L2 é suficiente.
