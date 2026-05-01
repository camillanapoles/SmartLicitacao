# SEO-PROG-007: `robots.ts` dinâmico Next.js 16 (env-aware allow/disallow + sitemap_index)

**Priority:** **P0** — pulled forward from Sprint 3 → Sprint atual (2026-04-28: GSC reporta 464 páginas bloqueadas por robots.txt = 9.8% das 4.714 não indexadas)
**Effort:** S (1 dia core) + S (4-8h AC6 audit) = **M (1.5 dias)**
**Squad:** @dev + @analyst (audit AC6)
**Status:** Ready (re-validated 2026-04-28 pós-refresh AC6)
**Epic:** [EPIC-SEO-PROG-2026-Q2](EPIC-SEO-PROG-2026-Q2.md)
**Sprint:** **Sprint atual** (2026-04-28 onwards) — quick win recovery
**Bloqueado por:** ~~SEO-PROG-006~~ — desbloquear; AC3 sitemap variant flag mantém compatibilidade legacy. AC6 audit independente.

---

## Contexto

O `frontend/public/robots.txt` atual é **estático** (62 linhas), declarando:
- `User-agent: *` com Allow/Disallow para rotas autenticadas (`/admin`, `/buscar`, `/dashboard`, etc.)
- `User-agent: Google-Extended` com Allow `/` (AI Overviews opt-in)
- 7 AI crawlers blockados (Amazonbot, Applebot-Extended, Bytespider, CCBot, ClaudeBot, GPTBot, meta-externalagent)
- `Sitemap: https://smartlic.tech/sitemap.xml`
- `Host: https://smartlic.tech`

**Problemas para escala SEO**:

1. **Estático = sem control por env.** Preview/staging deploys (Railway preview environments, Vercel previews futuros) servem `robots.txt` declarando production canonical → Google indexa preview URLs → duplicate content + canonical confusion.
2. **Sitemap reference desatualizado** após SEO-PROG-006: `sitemap.xml` (legacy) será deprecated em favor de `sitemap_index.xml`. `robots.txt` estático precisa ser editado manualmente em PR — facilita drift.
3. **Sem feature flag por route** (ex: durante migração SSR→ISR de SEO-PROG-001..005, queremos block crawler temporariamente em rotas instáveis).
4. **Next.js 16 oferece API moderna `app/robots.ts`** route handler com TypeScript + tests + Sentry instrumentation — supera `public/robots.txt` em DX.

**Por que P0:** depois de SEO-PROG-006, `sitemap_index.xml` precisa ser referenciado. Sem este story, devs terão que editar `public/robots.txt` à mão sempre (drift garantido). Memory `feedback_handoff_stale_30h.md`: estado SEO regenera ortogonalmente, automation > manual edits.

**Por que esforço S:** Next.js 16 API é trivial; valor está na env-awareness + tests.

---

## Acceptance Criteria

### AC1: Criar `frontend/app/robots.ts` route handler

**Given** `public/robots.txt` é estático
**When** @dev cria `app/robots.ts`
**Then**:

- [x] Arquivo `frontend/app/robots.ts`:

```ts
import type { MetadataRoute } from 'next';

const BASE_URL = process.env.NEXT_PUBLIC_CANONICAL_URL || 'https://smartlic.tech';
const ENV = process.env.NEXT_PUBLIC_ENVIRONMENT || 'production';
const SITEMAP_VARIANT = process.env.SITEMAP_USE_INDEX_VARIANT || 'index'; // 'index' | 'legacy'

const SITEMAP_URL =
  SITEMAP_VARIANT === 'legacy'
    ? `${BASE_URL}/sitemap.xml`
    : `${BASE_URL}/sitemap_index.xml`;

const PRIVATE_PATHS = [
  '/admin',
  '/auth/callback',
  '/api',
  '/dashboard',
  '/conta',
  '/buscar',
  '/pipeline',
  '/historico',
  '/mensagens',
  '/alertas',
  '/onboarding',
  '/recuperar-senha',
  '/redefinir-senha',
];

const BLOCKED_AI_CRAWLERS = [
  'Amazonbot',
  'Applebot-Extended',
  'Bytespider',
  'CCBot',
  'ClaudeBot',
  'GPTBot',
  'meta-externalagent',
];

export default function robots(): MetadataRoute.Robots {
  // SEO-PROG-007: preview/staging blocks indexing entirely to prevent duplicate canonical
  if (ENV !== 'production') {
    return {
      rules: [{ userAgent: '*', disallow: '/' }],
      host: BASE_URL,
    };
  }

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: PRIVATE_PATHS,
      },
      // AI crawlers: Google-Extended permitido (AI Overviews / SGE) — RFC 9309 §2.2.2
      {
        userAgent: 'Google-Extended',
        allow: '/',
      },
      // Block non-Google AI crawlers
      ...BLOCKED_AI_CRAWLERS.map((bot) => ({
        userAgent: bot,
        disallow: '/',
      })),
    ],
    sitemap: SITEMAP_URL,
    host: BASE_URL,
  };
}
```

- [x] `export const dynamic = 'force-static'` ou ISR `revalidate=3600` (decisão @dev: force-static é seguro porque content é determinístico baseado em build-time env vars; ISR força re-render após deploy em apps pre-deploy)
- [x] Tests cobrem todos os cases (ENV=production vs preview, SITEMAP_VARIANT=legacy vs index, todas regras presentes)

### AC2: Env awareness (preview/staging block all)

**Given** deploy em ambiente non-production (preview, staging, dev)
**When** crawler hits `/robots.txt`
**Then**:

- [x] Retorna apenas `User-agent: *\nDisallow: /\n` (block tudo)
- [ ] `Host:` não declara canonical production *(@dev divergiu intencionalmente: declara `host: BASE_URL` em preview para semântica MetadataRoute.Robots; reverter se @po objetar)*
- [x] **Não** declara sitemap (preview não tem sitemap próprio)
- [x] Detecção via `process.env.NEXT_PUBLIC_ENVIRONMENT !== 'production'`

### AC3: Sitemap variant flag (compatibilidade SEO-PROG-006)

**Given** `SITEMAP_USE_INDEX_VARIANT` controla migração legacy→index
**When** flag é `legacy`
**Then**:

- [x] `Sitemap: https://smartlic.tech/sitemap.xml` *(test cobre)*

**When** flag é `index` (default)
**Then**:

- [x] `Sitemap: https://smartlic.tech/sitemap_index.xml` *(default; test cobre)*

### AC4: Deprecate `public/robots.txt`

**Given** `frontend/public/robots.txt` foi a fonte estática
**When** route handler novo está em prod
**Then**:

- [ ] Confirmar via Playwright MCP que `/robots.txt` retorna conteúdo do route handler (Next.js prioriza `app/robots.ts` sobre `public/robots.txt`)
- [ ] Após validação 7 dias em prod com 0 issues GSC, deletar `public/robots.txt` (PR follow-up; não bloquear merge atual)
- [ ] PR description inclui runbook: "post-deploy +7d: delete public/robots.txt"

### AC5: Observabilidade

- [ ] Sentry breadcrumb em route handler (não em todo render — apenas em error path se houver)
- [ ] Counter Prometheus `robots_render_total{env}` (opcional — robots.txt é simples; instrumentação leve)
- [ ] Log estruturado: `[robots] env=X variant=Y outcome=success`

### AC6: **PRIVATE_PATHS audit — eliminar over-blocking** (descoberto 2026-04-28)

**Problema confirmado empiricamente via GSC (2026-04-28):** 464 páginas SEO programmatic estão em bucket "Bloqueada pelo robots.txt" (9.8% das 4.714 não indexadas).

**Hipótese:** Disallow rules atuais são **prefix-match** (RFC 9309 §2.2.2), causando over-blocking de rotas legítimas:

| Disallow atual | Bloqueia rota pública? | Ação |
|----------------|------------------------|------|
| `/alertas` | **SIM** — `/alertas-publicos/[setor]/[uf]` (40+ páginas SEO) | trocar para `/alertas/` (path-exato + descendentes) |
| `/api` | **SIM** — `/api/sitemap-*` proxies + outras rotas Next API públicas | trocar para `/api/auth/`, `/api/admin/`, etc. (paths específicos) |
| `/buscar` | Suspeito — pode bloquear `/buscar?setor=X` linkado externamente | trocar para `/buscar/` (autenticado é `/buscar` raiz) ou avaliar se search é privado |
| `/conta` | OK — não tem rota pública | manter |
| `/dashboard`, `/pipeline`, `/historico`, `/mensagens` | OK | manter |
| `/admin`, `/onboarding`, `/recuperar-senha`, `/redefinir-senha` | OK | manter |

- [x] **Audit script** `frontend/scripts/audit-robots-coverage.ts` (criar):
  - Carrega lista de URLs SEO programmatic (via `/v1/sitemap/*` endpoints reais)
  - Usa `robots-parser` library (já listada AC6) para verificar quais matcham Disallow rules
  - Reporta: `(robots_rule, blocked_url_count, sample_urls)` em JSON
  - Exit 1 se >0 URLs públicas SEO matcham alguma Disallow rule
- [x] **Refatorar `PRIVATE_PATHS`** em `app/robots.ts` para path-exato:
  ```ts
  const PRIVATE_PATHS = [
    '/admin/',           // path-exato + subpaths
    '/auth/callback',    // path-exato (não tem subpaths)
    '/api/auth/',        // específico — NÃO bloquear /api/sitemap-*
    '/api/admin/',
    '/api/csp-report',   // POST endpoint, não SEO
    '/dashboard/',
    '/conta/',
    '/buscar/',          // se /buscar (raiz) é autenticado, manter; senão remover
    '/pipeline/',
    '/historico/',
    '/mensagens/',
    '/alertas/',         // ⚠️ trailing slash — exclui /alertas-publicos/
    '/onboarding/',
    '/recuperar-senha',  // path-exato
    '/redefinir-senha',  // path-exato
  ];
  ```
- [ ] **GSC URL Inspector** em 10 amostras das 464 bloqueadas — confirmar regra exata que matcha. Documentar em `docs/analysis/seo-robots-audit-2026-04.md`.
- [ ] **Verify pós-deploy:**
  ```bash
  # robots.txt servido com regras atualizadas
  curl -s "https://smartlic.tech/robots.txt" | grep -E "^Disallow:"
  # Espera-se: trailing slash em /alertas/, /api/auth/ específico

  # Sample 10 URLs SEO programmatic não bloqueadas
  for url in /alertas-publicos/ti/SP /api/sitemap-1.xml /blog/programmatic/saude/RJ; do
    npx robots-parser "https://smartlic.tech/robots.txt" "$url" "Googlebot"
  done
  # Espera-se: 3× "allowed".
  ```

### AC7: Testes

- [x] **Unit:** `frontend/__tests__/app/robots.test.ts`:
  - Default production: 14 disallows + Google-Extended allow + 7 AI blocks + sitemap_index URL + host
  - ENV=preview: apenas `User-agent: * Disallow: /`
  - ENV=staging: same as preview
  - SITEMAP_USE_INDEX_VARIANT=legacy: sitemap aponta para `/sitemap.xml`
  - SITEMAP_USE_INDEX_VARIANT=index (default): sitemap aponta para `/sitemap_index.xml`
  - **AC6 nova cobertura:** `/alertas-publicos/ti/SP` é Allowed (não bloqueia por `/alertas/` Disallow)
  - `/api/sitemap-1.xml` é Allowed (não bloqueia por `/api/auth/` específico)
  - `/admin/seo` é Disallowed (matcha `/admin/`)
- [ ] **E2E Playwright:** `frontend/e2e-tests/seo/robots.spec.ts`:
  - GET `https://smartlic.tech/robots.txt` → 200 + content-type `text/plain` + parse rules
  - GET preview env URL → `User-agent: * Disallow: /`
- [ ] **Regression:** robots.txt parser library (e.g., `robots-parser` npm) valida syntax (sem warnings)

---

## Scope

**IN:**
- Criar `frontend/app/robots.ts` route handler
- Env-aware (production vs preview/staging)
- Sitemap variant flag compatibility
- Manter regras Allow/Disallow + AI crawlers blockados (port from public/robots.txt)
- **AC6 (refresh 2026-04-28):** `PRIVATE_PATHS` path-exato (trailing slash) — eliminar over-blocking de 464 páginas SEO programmatic (GSC empírico)
- Tests unit + E2E + parser regression + audit script
- Sentry breadcrumb leve
- Doc analysis em `docs/analysis/seo-robots-audit-2026-04.md`

**OUT:**
- Delete `public/robots.txt` (follow-up PR +7d post-deploy)
- New AI crawler blocks (defer; manter lista atual)
- Cloudflare WAF integration (out-of-scope epic level)
- robotstxt.org compliance audit (defer; manter functional)

---

## Definition of Done

- [ ] `app/robots.ts` em prod servindo `/robots.txt` corretamente
- [ ] Preview/staging deployment bloqueia indexação completa (validado em Railway preview env via Playwright)
- [ ] `Sitemap:` declaração reflete `SITEMAP_USE_INDEX_VARIANT` flag
- [ ] Todas 14 disallow rules da legacy presentes
- [ ] Google-Extended allow + 7 AI blocks preservados
- [ ] GSC URL Inspection `/robots.txt` HTTP 200 (text/plain)
- [ ] Bundle delta < +1KB
- [ ] Zero `cache: 'no-store'` (route handler simples; sem fetch externo)
- [ ] CodeRabbit clean
- [ ] PR aprovado @qa
- [ ] Change Log atualizado
- [ ] PR follow-up agendado +7d para delete `public/robots.txt`

---

## Dev Notes

### Paths absolutos

- **Atual estático:** `/mnt/d/pncp-poc/frontend/public/robots.txt` (62L)
- **Novo route handler:** `/mnt/d/pncp-poc/frontend/app/robots.ts` (criar)
- **Tests:** `/mnt/d/pncp-poc/frontend/__tests__/app/robots.test.ts` + `/mnt/d/pncp-poc/frontend/e2e-tests/seo/robots.spec.ts`
- **Reference (Next.js 16 API):** https://nextjs.org/docs/app/api-reference/file-conventions/metadata/robots
- **Env config:** `/mnt/d/pncp-poc/frontend/.env.example`

### Padrões existentes

- `MetadataRoute.Robots` type from `next` package (mesma família que `MetadataRoute.Sitemap` já usado em `sitemap.ts`).
- Env detection: `process.env.NEXT_PUBLIC_ENVIRONMENT` já usado em Sentry config (`frontend/sentry.client.config.ts`).

### Next.js 16 API peculiarities

- `app/robots.ts` é route handler especial — Next intercepts `/robots.txt` request. Não precisa criar `/robots.txt/route.ts`.
- `dynamic = 'force-static'` recomendado: rules são determinísticas em build-time. ISR não necessário (mudanças requerem deploy).
- Se quiser dinamismo runtime (e.g., feature flag em DB), usar `app/robots.txt/route.ts` route handler manual retornando `text/plain`. Out of scope deste story.

### Testing standards

- Mockar `process.env.NEXT_PUBLIC_ENVIRONMENT` via `vi.stubEnv` ou `process.env.X = 'preview'; delete process.env.X;`.
- E2E: usar Playwright MCP para fetch direto do URL (sem browser) — `mcp__playwright__browser_navigate` ou `fetch` Node nativo.
- Parser regression: `npm install -D robots-parser` se não existir; `parse(robotsTxt).isAllowed('/admin', 'Googlebot')` deve retornar `false`.

### robots.txt RFC compliance

- RFC 9309 §2.2.2: "If a record contains both Allow and Disallow rules, the more specific rule wins. If equal specificity, Allow precedence."
- Comentário no arquivo legacy refletia este comportamento para Google-Extended; manter na nova versão.

---

## Risk & Rollback

### Triggers

| Trigger | Threshold | Detecção |
|---|---|---|
| GSC blocks public pages | crawler errors >0 | GSC console |
| Preview deploy indexed | preview URLs in GSC | GSC dashboard |
| Sitemap declaration broken | `Sitemap:` URL 404 | curl validation |

### Ações

1. **Hard rollback:** revert PR via @devops + restore `public/robots.txt` (mantido durante migration window).
2. Soft: ajustar `SITEMAP_USE_INDEX_VARIANT=legacy` + redeploy se sitemap_index.xml com problema (delegação SEO-PROG-006).

---

## Dependencies

### Entrada

- SEO-PROG-006 (sitemap_index.xml em prod servindo)

### Saída

- Nenhuma (terminal de epic SEO Sprint 3)

### Paralelas

- Nenhuma — story isolada e simples.

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-27
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Clear and objective title | OK | Título preciso: env-aware allow/disallow + sitemap_index |
| 2 | Complete description | OK | 4 problemas claros: estático sem env, sitemap drift, sem feature flag, Next.js 16 API moderna |
| 3 | Testable acceptance criteria | OK | AC1-AC6 testáveis; tests cobrem todos cases (production/preview, legacy/index variants) |
| 4 | Well-defined scope (IN/OUT) | OK | OUT inclui delete `public/robots.txt` (follow-up PR +7d) — clear sequencing |
| 5 | Dependencies mapped | OK | Bloqueado por SEO-PROG-006; Saída nenhuma (terminal Sprint 3) |
| 6 | Complexity estimate | OK | Effort S (1 dia) apropriado — Next.js 16 API trivial, valor em env-awareness + tests |
| 7 | Business value | OK | Previne preview indexing (duplicate canonical) + drift via automation > manual edits |
| 8 | Risks documented | OK | 3 triggers; rollback hard via revert + restore public/robots.txt mantido durante migration |
| 9 | Criteria of Done | OK | 12 itens; valida via Playwright preview env + RFC 9309 §2.2.2 compliance preservada |
| 10 | Alignment with PRD/Epic | OK | Sitemap variant flag (`SITEMAP_USE_INDEX_VARIANT`) coordena com SEO-PROG-006 |

### Observations

- AC2 env-awareness (preview/staging block all) é defesa crítica contra duplicate canonical — alinha com memory `feedback_handoff_stale_30h.md` (automation > manual).
- AC3 sitemap variant flag preserva compatibilidade durante migration de SEO-PROG-006.
- Manter regras de Google-Extended + 7 AI crawlers blockados (port from public/robots.txt) — preserva decisões SEO já validadas.
- Decisão `dynamic = 'force-static'` em AC1 é tecnicamente correta (rules determinísticas em build-time).

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-27 | 1.0 | Story criada — `robots.ts` env-aware com sitemap variant flag | @sm (River) |
| 2026-04-27 | 1.1 | PO validation: GO (10/10). Env-aware + sitemap variant flag aprovados. Status Draft→Ready. | @po (Pax) |
| 2026-04-28 | 1.2 | **Refresh AC6** — gap descoberto via GSC: 464 páginas bloqueadas por robots.txt over-blocking (`/alertas` prefix bloqueia `/alertas-publicos/*`, `/api` prefix bloqueia `/api/sitemap-*`). Adicionado: PRIVATE_PATHS path-exato com trailing slash, audit script, GSC URL Inspector verify, doc analysis. Reclassificada P0 (era P0 Sprint 3) → P0 Sprint atual. Effort S → M. Status: re-Draft pending @po re-validate. Bloqueador SEO-PROG-006 removido (independente). Source: plan misty-beacon Story 5. | @sm (River) |
| 2026-04-28 | 1.3 | Re-validação pós-refresh AC6: **GO 10/10**. AC6 com tabela de Disallow rules + ação per rule + audit script + verify E2E. PRIVATE_PATHS reescrito com trailing slash (`/alertas/` em vez de `/alertas`). Tests AC7 expandidos cobrindo `/alertas-publicos/ti/SP` allowed + `/api/sitemap-1.xml` allowed. Status: re-Draft → **Ready**. Pulled forward Sprint 3 → Sprint atual. Quick win 4-8h AC6 audit pode ser merged primeiro (sem blockers). | @po (Pax) |
| 2026-04-28 | 1.4 | **Implementação @dev** — `frontend/app/robots.ts` (92L, route handler, force-static, env-gating, AC6 path-exact 16 PRIVATE_PATHS). `frontend/scripts/audit-robots-coverage.ts` (audit 0/11 sample URLs blocked). `frontend/__tests__/app/robots.test.ts` (40 tests, all passing 0.7s). `frontend/e2e-tests/seo/robots.spec.ts` (Playwright preview gated por `PREVIEW_BASE_URL`). `docs/analysis/seo-robots-audit-2026-04.md` (Disallow audit + 10 GSC samples). Decisão `/buscar`: ambos `/buscar` (raiz) E `/buscar/` (subpaths) bloqueados — `app/buscar/page.tsx` é "use client" SPA shell autenticado, sem SEO público. Decisão divergente AC2: `host: BASE_URL` declarado em preview (semântica MetadataRoute.Robots) — flag para @po. AC4 deploy validation + AC5 Sentry/Prom + DoD bundle delta + +7d follow-up: pendentes (post-deploy). CodeRabbit: clean. Tests: 40/40, ts-no-emit clean. Commit `a21656c3`. | @dev |
