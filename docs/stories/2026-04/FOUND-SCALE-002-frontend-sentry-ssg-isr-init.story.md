# FOUND-SCALE-002: Frontend Sentry SDK Init em SSG Build + ISR Runtime

**Priority:** P1 (observability gap)
**Effort:** M (2-4 dias)
**Squad:** @dev + @architect
**Status:** Ready
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 3
**Dependências bloqueadoras:** Sentry credentials configurados (memory `reference_sentry_credentials`)

---

## Contexto

Memory `feedback_frontend_sentry_silent_buildtime` 2026-04-27: 0 events em 24h apesar de sitemap-4.xml=0 confirmado em prod. SDK init em SSG build / ISR runtime suspect — sem Sentry no SSG, não há detecção precoce de build hammer cascade (memory `feedback_build_hammers_backend_cascade`: SSG 4146 pages saturou backend hobby DB pool).

Distinto de RES-BE-013 (audit prod env vars `PYTHONASYNCIODEBUG=1` etc.): essa cobre backend env vars; esta story cobre frontend Sentry SDK runtime init pattern.

`frontend/sentry.{client,server,edge}.config.ts` provavelmente existem mas init pode falhar em build/ISR contexts.

---

## Acceptance Criteria

### AC1: Audit Sentry config

- [ ] Read `frontend/sentry.client.config.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`
- [ ] Read `frontend/next.config.js` Sentry wrapper
- [ ] Verify `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN` env vars em Railway frontend
- [ ] Output `docs/audit/frontend-sentry-init-status.md`

### AC2: Build-time SSG init

- [ ] Confirm Sentry SDK init pré-fetch em SSG (build context):
  - `app/sitemap.ts` (786L per sm-briefing-refactor)
  - `app/{cnpj,orgaos,municipios,observatorio}/[slug]/page.tsx` SSG/ISR pages
- [ ] Test: trigger fetch fail em sitemap build → Sentry deve capturar exception
- [ ] Force trigger via `npm run build` com BACKEND_URL inválido → expect Sentry event

### AC3: Runtime ISR init

- [ ] Confirm Sentry SDK init em ISR runtime (`revalidate=3600` paths)
- [ ] Test: ISR refresh fail → Sentry capturar
- [ ] Verify CRUX/perf metrics enviados

### AC4: `safeFetch` wrapper

- [ ] Criar `frontend/lib/safe-fetch.ts`:
  ```typescript
  export async function safeFetch(url: string, options?: RequestInit): Promise<Response | null> {
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(15000),
        ...options
      });
      if (!response.ok) {
        Sentry.captureMessage(`Fetch ${response.status}: ${url}`, 'warning');
      }
      return response;
    } catch (e) {
      Sentry.captureException(e, { tags: { fetch_url: url } });
      return null;
    }
  }
  ```
- [ ] Migrate sitemap.ts + dynamic pages para usar `safeFetch`

### AC5: Smoke test

- [ ] CI step: build com `BACKEND_URL=http://invalid:8000` → expect Sentry events generated (validate via Sentry API count)
- [ ] Memory `reference_frontend_dockerfile_backend_url_gap`: BACKEND_URL ARG fix already applied; verify

### AC6: Docs

- [ ] `docs/runbooks/frontend-sentry-coverage.md` — qual contexto SDK ativo, qual silencioso

---

## Scope

**IN:** audit + ensure SDK init build/ISR + safeFetch wrapper + smoke test + docs
**OUT:** Backend Sentry (separate, já live) · MS Clarity instrumentation (memory `reference_ms_clarity_instrumentation` separate)

---

## Definition of Done

- [ ] Sentry events visible in Sentry dashboard for SSG build failures
- [ ] safeFetch deployed em paths críticos
- [ ] CI smoke test passes
- [ ] Audit report criado
- [ ] @po validation GO

---

## Dev Notes

- Memory `reference_sentry_credentials`: org=confenge, projs=smartlic-frontend
- Memory `feedback_wsl_next16_build_inviavel`: WSL build OOM em monorepo 3k+ pages — usar CI para AC5 smoke test
- Memory `feedback_isr_fetch_cache_alignment_next16`: revalidate semantics — preserve

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Sentry quota exhaustion (build noise) | Sample rate config; tracesSampleRate=0.1 em build context |
| safeFetch retorna null silently | Add logging + alert on null cascade |

**Rollback:** revert safeFetch migrations; SDK config preserved.

---

## Dependencies

**Entrada:** Sentry credentials (existing) · BACKEND_URL ARG fix (Done memory)
**Saída:** habilita debugging SSG/ISR cascades futuras (memory `feedback_build_hammers_backend_cascade` recurrence prevention)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Sentry SSG/ISR init explícito. |
| 2 | Complete description | ✓ | Memory `feedback_frontend_sentry_silent_buildtime` referenciada — 0 events em 24h apesar sitemap fail. |
| 3 | Testable acceptance criteria | ✓ | 6 ACs com CI smoke test forçando fetch fail. |
| 4 | Well-defined scope | ✓ | OUT exclude backend Sentry + Clarity. |
| 5 | Dependencies mapped | ✓ | Sentry credentials existing. |
| 6 | Complexity estimate | ✓ | M (2-4d). |
| 7 | Business value | ✓ | Detecta build hammer cascade futura. |
| 8 | Risks documented | ✓ | Sample rate config evita quota exhaustion. |
| 9 | Criteria of Done | ✓ | 5 itens com Sentry events visible. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-RES-BE observability. |

Status: Draft → Ready.

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada via batch. Origem: `_reversa_sdd/sm-briefing-refactor.md` FOUND-SCALE-002. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
