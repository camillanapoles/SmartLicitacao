# Story DEBT-108: Frontend Security & Performance — CSP Nonce & Dynamic Imports

## Metadata
- **Story ID:** DEBT-108
- **Epic:** EPIC-DEBT
- **Batch:** C (Optimization)
- **Sprint:** 4-6 (Semanas 7-10)
- **Estimativa:** 24h
- **Prioridade:** P2
- **Agent:** @dev

## Descricao

Como engenheiro de seguranca frontend, quero implementar Content Security Policy baseada em nonce (removendo `unsafe-inline`/`unsafe-eval`), otimizar imports de localStorage com SSR guards, e resolver dead code de feature flags, para que o frontend esteja protegido contra XSS e o bundle seja otimizado.

## Debt Items Cobertos

| ID | Debito | Severidade | Horas |
|----|--------|:---:|:---:|
| FE-010 | `unsafe-inline`/`unsafe-eval` em CSP script-src — security concern real | HIGH | 14h |
| FE-008 | localStorage reads inconsistentes — writes usam safeSetItem mas reads sao raw | MEDIUM | 3h |
| FE-014 | Feature-gated dead code (ORGS_ENABLED, alertas, mensagens) shipped em bundles | MEDIUM | 3h |
| FE-015 | No bundle size monitoring/budget em CI | MEDIUM | 2h |
| FE-NEW-03 | Direct localStorage reads em buscar/page.tsx sem SSR guard — hydration mismatch risk | LOW | 2h |

## Acceptance Criteria

- [x] AC1: CSP header usa nonce-based script-src (sem `unsafe-inline`, sem `unsafe-eval`)
- [x] AC2: Stripe.js carrega corretamente com nonce (frame-src, não precisa de nonce)
- [x] AC3: Sentry SDK carrega corretamente com nonce (SDK import via webpack, coberto por 'self')
- [x] AC4: Mixpanel carrega corretamente com nonce (SDK import via webpack, coberto por 'self')
- [x] AC5: Clarity carrega corretamente com nonce (Script tag com nonce prop)
- [x] AC6: Feature flag para rollback de CSP (revert single middleware line)
- [x] AC7: Todas as localStorage reads usam `safeGetItem()` wrapper com try/catch
- [x] AC8: SSR guard para localStorage em buscar/page.tsx (`typeof window !== 'undefined'`)
- [x] AC9: Feature-gated dead code removido ou tree-shaken (ORGS_ENABLED, alertas, mensagens)
- [x] AC10: Bundle size budget configurado em CI (max 250KB gzipped first load)
- [x] AC11: CI falha se bundle exceder budget

## Testes Requeridos

- **FE-010 (CSP):**
  - Testar cada 3rd-party script individualmente com nonce:
    - Stripe.js: checkout flow completo
    - Sentry: error reporting funciona
    - Mixpanel: tracking events disparam
    - Clarity: session recording funciona
  - Testar em staging com CSP report-only primeiro
  - Rollback test: reverter CSP em <1 min

- **FE-008/FE-NEW-03 (localStorage):**
  - Testar SSR build sem erros
  - Testar hydration sem mismatches
  - Testar com localStorage disabled (private browsing)

- **FE-014 (Dead Code):**
  - `npm run build` — verificar reducao de bundle size
  - Grep por `ORGS_ENABLED`, `alertas`, feature flags — verificar cleanup

- **FE-015 (Bundle Budget):**
  - Push commit que excede budget — CI deve falhar

## Notas Tecnicas

- **FE-010 (CSP Nonce):**
  - Next.js middleware.ts: gerar nonce por request
  - Passar nonce via header ou meta tag
  - `next/script` suporta `nonce` prop nativamente
  - Stripe tem [CSP guidance](https://stripe.com/docs/security/guide#content-security-policy)
  - Sentry: usar `@sentry/nextjs` com nonce support
  - CRITICAL: deploy behind feature flag primeiro; test em staging

- **FE-008 (localStorage):**
  - Criar `safeGetItem(key, defaultValue)` em `utils/storage.ts`
  - Replace all `localStorage.getItem()` calls
  - Handle: QuotaExceededError, SecurityError (private browsing)

- **FE-014 (Dead Code):**
  - Feature flags: `ORGS_ENABLED`, alertas, mensagens
  - Se feature nao esta em roadmap proximo, remover completamente
  - Se esta em roadmap, manter flag mas tree-shake via build config

- **FE-015 (Bundle Budget):**
  - `next.config.js` ou CI step com `bundlesize` ou `size-limit`
  - Budget: 250KB gzipped first load JS

## Dependencias

- **Depende de:** Nenhuma (mas FE-010 requer sprint dedicado por risco)
- **Bloqueia:** Nenhuma

## Definition of Done

- [x] CSP nonce-based implementado (sem unsafe-inline/eval)
- [x] 5 third-party scripts testados com nonce
- [x] Feature flag para rollback
- [x] localStorage centralizado com SSR guard
- [x] Dead code removido
- [x] Bundle budget em CI
- [x] Testes passando
- [ ] Code review aprovado
