# Audit: Frontend Sentry SDK Init Status (FOUND-SCALE-002 AC1)

**Date:** 2026-04-29
**Story:** [FOUND-SCALE-002](../stories/2026-04/FOUND-SCALE-002-frontend-sentry-ssg-isr-init.story.md)
**Trigger:** memory `feedback_frontend_sentry_silent_buildtime` — 0 events em 24h apesar de sitemap-4.xml=0 confirmado em prod (Stage 7 wedge 2026-04-29).

---

## Resumo Executivo

**Status do gap original:** PARCIALMENTE FECHADO antes desta story.

Investigação empírica revela que **a maior parte da infra Sentry SSG/ISR já estava ativa** mas faltavam wrappers reusáveis para fetches críticos fora do `sitemap.ts` (cnpj/[cnpj], orgaos/[slug], itens/[catmat]). Esta story fecha esse gap via `frontend/lib/safe-fetch.ts::safeFetch` + `fetchWithBudget`.

---

## Estado pré-FOUND-SCALE-002

### ✅ Sentry SDK config — todos 3 runtimes inicializados

| Arquivo | Status | DSN env var | Notes |
|---------|--------|-------------|-------|
| `frontend/sentry.server.config.ts` | ✅ existe (13 LOC) | `SENTRY_DSN` | tracesSampleRate 0.1 |
| `frontend/sentry.client.config.ts` | ✅ existe (58 LOC) | `NEXT_PUBLIC_SENTRY_DSN` | beforeSend filter sofisticado (STORY-422 — drop USER_CANCELLED, AbortError, SSE pipe errors com timeout >110s) |
| `frontend/sentry.edge.config.ts` | ✅ existe (12 LOC) | `SENTRY_DSN` | Edge runtime |

### ✅ instrumentation.ts (Next.js 13+ pattern)

`frontend/instrumentation.ts` — 36 LOC.

- `register()` async importa sentry configs dinamicamente per runtime (nodejs / edge)
- **Linhas 14-31:** valida BACKEND_URL no startup. Se vazio ou formato inválido, loga CRÍTICO + propaga para startup fail. Já cobre AC2 (build-time SSG init validation).
- `onRequestError = Sentry.captureRequestError` ativa capture automático para Server Components + API routes.

### ✅ next.config.js Sentry wrapper

- `withSentryConfig()` ativo (linha 113)
- Source map upload configurado: `tunnelRoute: "/monitoring"`, `hideSourceMaps: true`, `widenClientFileUpload: true`
- Sentry org/project/authToken via env vars (linhas 114-116)

### ✅ sitemap.ts já tinha pattern reusable

`frontend/app/sitemap.ts:21-121` (STORY-SEO-001 + SEN-BE-007):

- `fetchSitemapJson<T>()` (linhas 21-98): observable wrapper com `Sentry.captureException()` em HTTP error + timeout/network. Tags: `sitemap_endpoint`, `sitemap_outcome ∈ {success, http_error, timeout, empty_data}`.
- `fetchSitemapJsonWithRetry<T>()` (linhas 103-121): 1× retry com 2s backoff. Captura `sitemap_retry_exhausted_*` warning.
- Breadcrumbs estruturados (linhas 81-92): `category: 'sitemap'`, `level: 'info'|'warning'`, `data: { sitemap_outcome, status_code, latency_ms, url_count, endpoint }`.

### ❌ Gap real

**Fetches críticos fora do sitemap.ts NÃO usavam o pattern observable.**

Antes desta story:
- `frontend/app/cnpj/[cnpj]/page.tsx::fetchPerfil` — silent `try { ... } catch { return null; }`. Zero Sentry capture.
- `frontend/app/orgaos/[slug]/page.tsx::fetchOrgaoStats` — same.
- `frontend/app/itens/[catmat]/page.tsx::fetchProfile` + `generateStaticParams` — same. Pior: `generateStaticParams` usa `cache: 'no-store'` (memory `feedback_isr_fetch_cache_alignment_next16` antipattern).

Esses paths SSG/ISR são build-time + ISR refresh. Falhas silenciam Sentry → memory `feedback_frontend_sentry_silent_buildtime` recidiva.

---

## Estado pós-FOUND-SCALE-002 (esta story)

### `frontend/lib/safe-fetch.ts` (NEW)

Generaliza `fetchSitemapJson` para uso em qualquer SSG/ISR fetch:

- `safeFetch(url, options)` — Response | null com Sentry instrumentation (HTTP error → captureMessage; network/timeout → captureException; breadcrumb estruturado em finally)
- `fetchWithBudget<T>(url, opts)` — typed JSON wrapper com retry exponential backoff, fallback, ISR-friendly defaults (`next: { revalidate: 3600 }`).

### Migrações

- `frontend/app/cnpj/[cnpj]/page.tsx::fetchPerfil` → `fetchWithBudget` (label `cnpj-perfil`, retries 1, revalidate 86400)
- `frontend/app/orgaos/[slug]/page.tsx::fetchOrgaoStats` → `fetchWithBudget` (label `orgao-stats`)
- `frontend/app/itens/[catmat]/page.tsx::fetchProfile` → `fetchWithBudget` (label `item-profile`)
- `frontend/app/itens/[catmat]/page.tsx::generateStaticParams` → `fetchWithBudget` com `revalidate` em vez de `cache: 'no-store'` (fix antipattern bonus)

### Tests

`frontend/__tests__/lib/safe-fetch.test.ts` — 9 test cases:
- safeFetch: 200 OK, HTTP error, network error, timeout
- fetchWithBudget: success no retry, retry success on 2nd, fallback after exhausted, extract transformer, default revalidate 3600

### CI smoke (AC5) — defer

Smoke test "build com BACKEND_URL=invalid → expect Sentry events count >0 via Sentry API" foi deferido para PR follow-up porque:
- Requires Sentry API integration test setup (token + project filter)
- WSL build OOM em monorepo 3k+ pages (memory `feedback_wsl_next16_build_inviavel`) → CI-only test
- Alternativa robusta: Playwright E2E em staging post-deploy (pós-merge)

---

## Conclusão

Antes desta story, o gap reportado em `feedback_frontend_sentry_silent_buildtime` era localizado: **infra Sentry estava OK mas pattern observable não era reusável fora do sitemap.ts**. Esta story extrai o pattern proven em `sitemap.ts` para `lib/safe-fetch.ts` e migra os 3 paths SSG/ISR críticos para usá-lo, fechando o gap real.

**Próximos passos (defer pós-merge):**
- AC5 CI smoke test integration
- Migrate restantes pages SSG/ISR (`fornecedores/[cnpj]`, `municipios/[slug]`, observatório routes) — story dedicada se quiser cobertura 100%.
- SEN-FE-002 + SEN-FE-003 reusam `fetchWithBudget` agora foundation-ready.
