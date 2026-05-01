# Runbook: Frontend Sentry Coverage (qual contexto SDK ativo)

**Story:** [FOUND-SCALE-002](../stories/2026-04/FOUND-SCALE-002-frontend-sentry-ssg-isr-init.story.md)
**Created:** 2026-04-29
**Audience:** dev/oncall investigando "por que Sentry não capturou X em prod"

---

## Contextos de execução Next.js 16 + Sentry SDK status

| Contexto | Runtime | Sentry SDK init | Captura automática | Wrappers manuais necessários |
|----------|---------|-----------------|---------------------|-----------------------------|
| **Server Components / Server Actions** | nodejs | `instrumentation.ts::register()` carrega `sentry.server.config.ts` | `Sentry.captureRequestError` via `onRequestError` export | Não — captura é hook-driven |
| **API Routes (`app/api/*/route.ts`)** | nodejs | idem | idem | Não |
| **SSG (`generateStaticParams`, `generateMetadata`, page server fns)** | nodejs (build context) | idem (build runs `register()`) | **NÃO automático** — tu deve `try/catch + Sentry.captureException` ou usar `fetchWithBudget` | **SIM — use `fetchWithBudget`** (fechado em FOUND-SCALE-002) |
| **ISR refresh** | nodejs (revalidation context) | idem | **NÃO automático** | **SIM — use `fetchWithBudget`** |
| **Client Components ('use client')** | browser | `sentry.client.config.ts` via `_app` instrumentation | Sim — error boundary + global error handler | Não para erros runtime; mas para fetch errors silentes (`try/catch` swallowed) → use `safeFetch` ou explicit `Sentry.captureException` |
| **Edge Runtime (`runtime: 'edge'`)** | edge | `sentry.edge.config.ts` via `register()` | Sim para uncaught | Wrappers OK também |

---

## Quando Sentry NÃO captura automaticamente (gaps históricos)

### Gap 1: SSG/ISR fetch silent failures

**Sintoma observado em prod (Stage 7, 2026-04-29):** sitemap-4.xml=0 entries, mas zero Sentry events em 24h.

**Root cause:** SSG fetches em `try/catch` que retornam `null` ou `[]` silenciosamente.

```typescript
// ❌ ANTIPATTERN — Sentry nunca vê falha
async function fetchPerfil(cnpj: string): Promise<Profile | null> {
  try {
    const resp = await fetch(`${BACKEND_URL}/v1/empresa/${cnpj}/perfil`);
    if (!resp.ok) return null;  // silent
    return await resp.json();
  } catch {
    return null;  // silent
  }
}
```

**Fix (FOUND-SCALE-002):**

```typescript
// ✅ Use fetchWithBudget — observability built-in
import { fetchWithBudget } from '@/lib/safe-fetch';
import { getBackendUrl } from '@/lib/backend-url';

async function fetchPerfil(cnpj: string): Promise<Profile | null> {
  return fetchWithBudget<Profile>(`${getBackendUrl()}/v1/empresa/${cnpj}/perfil`, {
    timeout: 10000,
    retries: 1,
    revalidate: 86400,
    label: 'cnpj-perfil',
  });
}
```

### Gap 2: `cache: 'no-store'` em SSG

**Sintoma:** SSG renderiza vazio, ISR não revalida coerentemente.

**Memory ref:** `feedback_isr_fetch_cache_alignment_next16` — `revalidate=N` + `cache: 'no-store'` quebra SSG.

**Fix:** sempre `next: { revalidate: N }`. `fetchWithBudget` força esse default — NUNCA aceita `cache: 'no-store'`.

### Gap 3: Build-time env var ausente

**Sintoma:** `BACKEND_URL` ausente → fetch cai em `localhost:8000` → build inteiro silently corrompido.

**Status atual:** `frontend/instrumentation.ts:14-31` valida BACKEND_URL no startup. Falha startup se env var inválida. `frontend/Dockerfile:138-153` falha build em prod se BACKEND_URL ausente. Helper `getBackendUrl()` em `frontend/lib/backend-url.ts` codifica chain canônica.

---

## Como verificar coverage em runtime

### 1. Force trigger Sentry event em SSG

Local (dev):

```bash
# Force fetch fail no build:
BACKEND_URL=http://invalid:8000 npm run build 2>&1 | grep -i "sentry\|fetch_outcome"
```

Verificar evento na dashboard Sentry: https://sentry.io/organizations/confenge/issues/?project=smartlic-frontend

### 2. Sentry breadcrumb em ISR refresh

Cada `fetchWithBudget` call emite breadcrumb mesmo em sucesso (`fetch_outcome: success`). Útil para traçar latência ISR pós-fact em sessões com erro downstream.

### 3. Audit grep — paths que ainda usam fetch raw

```bash
cd frontend
grep -rEn "await fetch\(" app --include="*.ts" --include="*.tsx" \
  | grep -v "node_modules" \
  | grep -v "__tests__" \
  | grep -v "sentry.client.config" \
  | head -20
```

Cada match é candidato a migrar para `safeFetch` ou `fetchWithBudget`. Não obrigatório (client components com error boundary já cobertos). Foco: SSG/ISR build paths + critical user flows.

---

## Tags Sentry úteis para queries

Convenção via `safeFetch` / `fetchWithBudget`:

| Tag | Valores | Uso |
|-----|---------|-----|
| `fetch_label` | string ad-hoc | identifica call site (e.g. `cnpj-perfil`) |
| `fetch_outcome` | `success` \| `http_error` \| `timeout` \| `network_error` \| `parse_error` \| `budget_exhausted` | filtra por tipo de falha |
| `sitemap_outcome` | `success` \| `http_error` \| `timeout` \| `empty_data` | sitemap.ts legacy (preservado para back-compat) |
| `sitemap_endpoint` | string label | sitemap.ts legacy |

Sentry query exemplo:

```
project:smartlic-frontend fetch_outcome:budget_exhausted
project:smartlic-frontend fetch_label:cnpj-perfil fetch_outcome:timeout
```

---

## Falsos negativos comuns

- **`fetch_outcome: success` mas dados vazios:** wrappers só sinalizam falha de transporte. Validação de payload (e.g. `array.length === 0`) é responsabilidade do caller.
- **Sentry rate limit (free tier):** projetos free têm cap de events/mês. Sob outage longo, eventos podem ser droppados. Verificar dashboard Sentry → Stats → "Rate Limited".
- **`tracesSampleRate: 0.1`** em `sentry.server.config.ts`: 90% de traces são sampled out. Erros (captureException) NÃO são afetados — só performance traces.

---

## Refs

- Memory: `feedback_frontend_sentry_silent_buildtime` (2026-04-27)
- Memory: `feedback_build_hammers_backend_cascade` (2026-04-27)
- Memory: `feedback_isr_fetch_cache_alignment_next16` (2026-04-24)
- Memory: `feedback_wsl_next16_build_inviavel` (2026-04-24)
- Memory: `reference_frontend_dockerfile_backend_url_gap` (2026-04-24)
- Story: [FOUND-SCALE-002](../stories/2026-04/FOUND-SCALE-002-frontend-sentry-ssg-isr-init.story.md)
- Story: [SEO-PROG-008](../stories/2026-04/SEO-PROG-008-dockerfile-backend-url.md) — `getBackendUrl()` helper
- Code: `frontend/lib/safe-fetch.ts` — wrappers
- Code: `frontend/lib/backend-url.ts` — env chain helper
- Code: `frontend/instrumentation.ts` — startup validation
- Code: `frontend/sentry.{client,server,edge}.config.ts` — SDK init
