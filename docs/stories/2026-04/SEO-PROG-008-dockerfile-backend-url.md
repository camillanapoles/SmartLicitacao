# SEO-PROG-008: Auditar `Dockerfile` ARG `BACKEND_URL` + build-time assertion + chain fallback

**Priority:** P0
**Effort:** S (0.5-1 dia)
**Squad:** @devops + @dev
**Status:** Done
**Epic:** [EPIC-SEO-PROG-2026-Q2](EPIC-SEO-PROG-2026-Q2.md)
**Sprint:** Sprint 1 (29/abr–05/mai)
**Sprint Window:** 2026-04-29 → 2026-05-05
**Bloqueado por:** — (independente, fundação)

---

## Contexto

O `frontend/Dockerfile` atual já contém `ARG BACKEND_URL` (linha 50) e `ENV BACKEND_URL=$BACKEND_URL` (linha 78) — **adicionados em STORY-SEO-020 (commit 2026-04-24)** após o incidente "sitemap-4.xml com 0 entries". Esta story **NÃO** introduz a feature; ela **valida que o gap está fechado e adiciona defesa em profundidade** para prevenir regressão.

**Referência memory `reference_frontend_dockerfile_backend_url_gap.md` (2026-04-24):**

> Build-time server fetches (sitemap.ts etc.) caem em localhost:8000 fallback pois só `NEXT_PUBLIC_BACKEND_URL` é ARG. Fix: chain fallback em código.

E memory `reference_railway_backend_url_already_set.md`:

> bidiq-frontend já tem BACKEND_URL=https://api.smartlic.tech; Wave 3.3 de plans antigos é no-op.

**Razões para fortalecer pós-fix existente** (esta story):

1. **Sem assertion build-time:** se Railway `bidiq-frontend.BACKEND_URL` for desconfigurado (drift, rotação humana, terraform error), build passa silenciosamente com `BACKEND_URL=""` → fetches caem em `'http://localhost:8000'` fallback → sitemap-4.xml volta a 0 entries.
2. **Chain fallback inconsistente entre rotas:** `frontend/app/sitemap.ts:22` usa `process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'` (correto). `frontend/app/cnpj/[cnpj]/page.tsx:7` usa `process.env.BACKEND_URL || 'http://localhost:8000'` (incompleto — sem fallback NEXT_PUBLIC_). `frontend/app/itens/[catmat]/page.tsx:48` mesmo padrão incompleto. Inconsistência = manutenção difícil + risco de regressão.
3. **Sem CI gate:** se alguém adicionar nova rota SSG com `process.env.BACKEND_URL || 'http://localhost:8000'` direto, ninguém detecta sem grep manual.

**Por que P0:** memory `feedback_build_hammers_backend_cascade.md` documenta que sitemap.ts saturou backend em 2026-04-27 — root cause foi build SSG hammering. Se BACKEND_URL volta a `localhost:8000` por config drift, o blast radius é o mesmo (build inteiro falha + sitemap vazio em prod). Esta story é *defense-in-depth* contra recidiva.

**Por que esforço S:** não introduz nova feature; apenas codifica padrão + adiciona assertion + escreve test.

---

## Acceptance Criteria

### AC1: Audit `frontend/Dockerfile` linhas 44-78

**Given** Dockerfile já tem `ARG BACKEND_URL` (linha 50) e `ENV BACKEND_URL=$BACKEND_URL` (linha 78)
**When** @devops audita
**Then**:

- [ ] Confirmar que ARG é declarado **DEPOIS** de `WORKDIR /app` mas **ANTES** de `RUN npm run build` (linhas 50 e 78 atualmente — verify ordering)
- [ ] Confirmar Debug echo (linha 100-110) printa `BACKEND_URL=$BACKEND_URL` no build output
- [ ] Confirmar Railway `bidiq-frontend` service vars contém `BACKEND_URL=https://api.smartlic.tech`:

```bash
railway variables --service bidiq-frontend --kv | grep -E "^(BACKEND_URL|NEXT_PUBLIC_BACKEND_URL)="
# Expected:
# BACKEND_URL=https://api.smartlic.tech
# NEXT_PUBLIC_BACKEND_URL=https://api.smartlic.tech
```

- [ ] Documentar resultado do audit em PR description (output do comando + screenshot Railway dashboard se necessário)

### AC2: Build-time assertion em Dockerfile

**Given** queremos build falhar rápido se `BACKEND_URL` ausente
**When** @devops adiciona assertion após `RUN echo "..." && \` debug block (após linha 110)
**Then**:

- [ ] Adicionar bloco RUN entre debug echo e `npm run build`:

```dockerfile
# SEO-PROG-008: Build-time assertion — fail fast se BACKEND_URL ausente em prod
RUN if [ "$NEXT_PUBLIC_ENVIRONMENT" = "production" ] && [ -z "$BACKEND_URL" ]; then \
      echo "ERROR: BACKEND_URL is required in production builds. Set Railway service variable bidiq-frontend.BACKEND_URL=https://api.smartlic.tech"; \
      exit 1; \
    fi && \
    echo "BACKEND_URL assertion: OK ($BACKEND_URL)"
```

- [ ] Mesmo bloco para `NEXT_PUBLIC_BACKEND_URL` (client-side fetches)
- [ ] Build em preview/staging não exige (assertion condicionada a `NEXT_PUBLIC_ENVIRONMENT=production`)

### AC3: Chain fallback consistente em todas rotas SSG

**Given** rotas SSG usam fetch a backend em build/runtime ISR
**When** @dev faz audit + fix
**Then**:

- [ ] Padrão canônico aplicado em **TODAS** as rotas SSG:

```ts
const backendUrl =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  'http://localhost:8000';
```

- [ ] Audit grep:

```bash
grep -rn "process.env.BACKEND_URL" frontend/app/ frontend/lib/
# Esperado: cada match usa chain `BACKEND_URL || NEXT_PUBLIC_BACKEND_URL || localhost:8000`
```

- [ ] Files conhecidos para fix (mínimo):
  - `/mnt/d/pncp-poc/frontend/app/cnpj/[cnpj]/page.tsx:7` — fix `process.env.BACKEND_URL || 'http://localhost:8000'` para chain completo
  - `/mnt/d/pncp-poc/frontend/app/orgaos/[slug]/page.tsx:7` — same
  - `/mnt/d/pncp-poc/frontend/app/itens/[catmat]/page.tsx:48` — same (in `fetchProfile`)
  - `/mnt/d/pncp-poc/frontend/app/itens/[catmat]/page.tsx:62` — same (in `generateStaticParams`)
- [ ] Audit final: zero ocorrências de `process.env.BACKEND_URL || 'http://localhost:8000'` (sem chain NEXT_PUBLIC_) em `frontend/app/`

### AC4: Helper utility `getBackendUrl()` (DRY)

**Given** padrão repetido em N rotas é vetor de drift
**When** @dev cria helper
**Then**:

- [ ] Criar `frontend/lib/backend-url.ts`:

```ts
/**
 * Returns the backend URL for server-side fetches (SSG, ISR, route handlers).
 *
 * Chain de fallback documentado em SEO-PROG-008:
 * 1. BACKEND_URL — server-side, set via Railway bidiq-frontend service var
 * 2. NEXT_PUBLIC_BACKEND_URL — client-side default, fallback se BACKEND_URL ausente
 * 3. http://localhost:8000 — dev local fallback
 *
 * Memory reference: feedback_build_hammers_backend_cascade.md
 *  — sitemap-4.xml ficou vazio quando Dockerfile não tinha ARG BACKEND_URL.
 */
export function getBackendUrl(): string {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    'http://localhost:8000'
  );
}
```

- [ ] Refatorar usages conhecidos para importar `getBackendUrl()`:
  - `frontend/app/sitemap.ts` (linha 22)
  - `frontend/app/cnpj/[cnpj]/page.tsx`
  - `frontend/app/orgaos/[slug]/page.tsx`
  - `frontend/app/itens/[catmat]/page.tsx`
  - Outros call sites encontrados via grep (audit AC3)
- [ ] Bundle delta verification: helper é tree-shakable (named export, sem side effects).

### AC5: CI lint gate (opcional mas recomendado)

**Given** queremos prevenir regressão (novo arquivo com `localhost:8000` direto)
**When** @devops adiciona ESLint custom rule ou grep CI step
**Then**:

- [ ] Opção A (mais simples): GH Actions step em `.github/workflows/frontend-tests.yml`:

```yaml
- name: Audit BACKEND_URL chain fallback
  run: |
    cd frontend
    if grep -rn "process.env.BACKEND_URL || 'http://localhost" app/ lib/ | grep -v "NEXT_PUBLIC_BACKEND_URL"; then
      echo "ERROR: Found incomplete BACKEND_URL chain. Use getBackendUrl() from lib/backend-url.ts"
      exit 1
    fi
```

- [ ] Opção B (mais robusta, defer): ESLint custom rule. Out-of-scope desta story.

### AC6: Testes

- [ ] **Unit:** `frontend/__tests__/lib/backend-url.test.ts`:
  - `getBackendUrl()` retorna `BACKEND_URL` quando set
  - Fallback para `NEXT_PUBLIC_BACKEND_URL` quando `BACKEND_URL` undefined
  - Fallback para `'http://localhost:8000'` quando ambas undefined
  - Mock via `vi.stubEnv`
- [ ] **Smoke E2E:** após deploy staging, validar `curl https://staging.smartlic.tech/sitemap_index.xml` retorna XML não vazio (validação indireta de BACKEND_URL OK em build)
- [ ] **Build assertion test:** simular build local com `BACKEND_URL=` empty + `NEXT_PUBLIC_ENVIRONMENT=production` → confirmar exit code 1 com error message claro

---

## Scope

**IN:**
- Audit Railway `bidiq-frontend` service vars
- Dockerfile build-time assertion (production-only)
- Chain fallback consistente (`BACKEND_URL || NEXT_PUBLIC_BACKEND_URL || localhost`)
- Helper `frontend/lib/backend-url.ts` + refactor usages
- CI grep gate (Opção A)
- Tests unit + smoke E2E

**OUT:**
- ESLint custom rule (defer Opção B)
- Multi-environment matrix (preview/staging URL config) — out-of-scope; assertion é production-only
- Backend URL rotation policy (out-of-scope)
- Railway IaC (terraform) para vars (out-of-scope)

---

## Definition of Done

- [ ] Audit Railway documentado em PR (BACKEND_URL=https://api.smartlic.tech confirmed)
- [ ] Dockerfile assertion adicionada e testada (build local com env vazio falha; com env setada passa)
- [ ] Helper `lib/backend-url.ts` criado + ≥4 call sites refatorados
- [ ] Grep audit zero ocorrências de antipattern
- [ ] CI workflow `frontend-tests.yml` falha PR que reintroduz antipattern (validar com test PR sintético)
- [ ] Bundle delta < +1KB
- [ ] Sitemap_index.xml validation pós-deploy: shards retornam URLs não vazias
- [ ] CodeRabbit clean
- [ ] PR aprovado @qa + @devops
- [ ] Change Log atualizado

---

## Dev Notes

### Paths absolutos

- **Dockerfile:** `/mnt/d/pncp-poc/frontend/Dockerfile` (linhas 44-78 + new assertion)
- **Helper novo:** `/mnt/d/pncp-poc/frontend/lib/backend-url.ts`
- **Call sites para refactor:**
  - `/mnt/d/pncp-poc/frontend/app/sitemap.ts:22`
  - `/mnt/d/pncp-poc/frontend/app/cnpj/[cnpj]/page.tsx:7`
  - `/mnt/d/pncp-poc/frontend/app/orgaos/[slug]/page.tsx:7`
  - `/mnt/d/pncp-poc/frontend/app/itens/[catmat]/page.tsx:48,62`
  - Audit completo via `grep -rn "process.env.BACKEND_URL" frontend/app/ frontend/lib/`
- **CI workflow:** `/mnt/d/pncp-poc/.github/workflows/frontend-tests.yml`
- **Tests:** `/mnt/d/pncp-poc/frontend/__tests__/lib/backend-url.test.ts`

### Padrões existentes

- Chain fallback canônico já usado em `sitemap.ts:22` (replicar pattern).
- Sentry tags pattern em `sitemap.ts:32-35` (não aplicável aqui — helper é puro).

### Railway service variables

- Memory `reference_railway_backend_url_already_set.md`: `BACKEND_URL=https://api.smartlic.tech` já set; verificar com `railway variables --service bidiq-frontend --kv | grep BACKEND_URL`.
- Se não setada: `railway variables set BACKEND_URL=https://api.smartlic.tech --service bidiq-frontend` (delegado @devops).

### Testing standards

- **Build assertion test:** rodar `docker build --build-arg BACKEND_URL= --build-arg NEXT_PUBLIC_ENVIRONMENT=production -f frontend/Dockerfile frontend/` e verificar exit 1.
- **Helper unit:** padrão `vi.stubEnv` ou diretamente `process.env.X = 'val'; ... delete process.env.X`. Memory `feedback_test_regex_invariant_semantic.md`: preferir match por `outcome === 'use_BACKEND_URL'` sobre frase literal "BACKEND_URL is set".

### Build OOM mitigation (correlato)

- Esta story NÃO mitiga build OOM (escopo SEO-PROG-014). Mas fix de fallback chain previne build success com bad config (que mascararia OOM como real success).

---

## Risk & Rollback

### Triggers

| Trigger | Threshold | Detecção |
|---|---|---|
| Sitemap-N.xml retorna 0 URLs | shards entities vazios | Playwright smoke |
| Build assertion falha em prod (BACKEND_URL drift) | exit 1 | Railway logs |
| Refactor introduz import cycle ou bundle bloat | size-limit fail | CI |

### Ações

1. **Soft rollback:** revert chain fallback fix em call sites; helper permanece (compatível com pattern antigo).
2. **Hard rollback:** revert PR via @devops.
3. **Railway drift:** `railway variables set BACKEND_URL=https://api.smartlic.tech --service bidiq-frontend` + force redeploy.

---

## Dependencies

### Entrada

- Nenhuma (independente, fundação Sprint 1).

### Saída

- SEO-PROG-001..005 (rotas SSR→ISR usam `getBackendUrl()` helper)
- SEO-PROG-006 (sitemap_index usa helper)

### Paralelas

- Sprint 1 paralelo: RES-BE-001, RES-BE-002, MON-FN-001, MON-FN-005.

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-27
**Verdict:** GO
**Score:** 10/10

### 10-Point Checklist

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Clear and objective title | OK | Título preciso: audit + assertion + chain fallback |
| 2 | Complete description | OK | Reconhece explícito que ARG BACKEND_URL JÁ existe (STORY-SEO-020); story é defense-in-depth, NÃO over-engineering |
| 3 | Testable acceptance criteria | OK | AC1-AC6 testáveis; AC2 build assertion testável via docker build local |
| 4 | Well-defined scope (IN/OUT) | OK | OUT explícito: ESLint rule defer Opção B, multi-env matrix, terraform IaC |
| 5 | Dependencies mapped | OK | Independente (fundação Sprint 1); saída para SEO-PROG-001..005 + 006 |
| 6 | Complexity estimate | OK | Effort S (0.5-1 dia) consistente: codifica padrão + assertion + helper + test |
| 7 | Business value | OK | Previne CRIT recidiva (memory `feedback_build_hammers_backend_cascade.md`) + DRY via helper |
| 8 | Risks documented | OK | 3 triggers; ações soft/hard/Railway drift |
| 9 | Criteria of Done | OK | 11 itens; sitemap_index validation pós-deploy; CI gate validado com PR sintético |
| 10 | Alignment with PRD/Epic | OK | Confirmação empírica: `ARG BACKEND_URL` linha 50 + `ENV BACKEND_URL=$BACKEND_URL` linha 78 — fato verdadeiro |

### Observations

- **Confirmação empírica:** grep no Dockerfile confirma `ARG BACKEND_URL` linha 50 + `ENV BACKEND_URL=$BACKEND_URL` linha 78 — story corretamente reconhece state atual e não duplica trabalho.
- AC4 (helper `getBackendUrl()`) é DRY refator de alto valor — 4+ call sites para refactor + audit grep para regression.
- AC5 (CI grep gate) é defesa proativa contra reintrodução do antipattern.
- Story não introduz nova feature — apenas codifica padrão + assertion + tests. Effort S apropriado.
- AC1 inclui validação Railway service vars via CLI (não dashboard) — alinha com CLAUDE.md "ALWAYS prefer CLI over web dashboards".

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-27 | 1.0 | Story criada — defense-in-depth pós STORY-SEO-020 (BACKEND_URL ARG já existe) | @sm (River) |
| 2026-04-27 | 1.1 | PO validation: GO (10/10). Defense-in-depth bem documentado, não over-engineering. Status Draft→Ready. | @po (Pax) |
| 2026-04-29 | 1.2 | **Stage 7 wedge ground + sm-briefing-100pct refresh**. **Trigger:** sm-briefing-100pct.md §3.3.4. **Ground:** Stage 7 reinforce — Disc 1 user-suggested AT BUILD TIME INVIABILIZED durante outage. Cobertura build-time PERMANECE escopo desta story; AT RUNTIME variant deferida para `OPS-DEVOPS-001` (não-overlap). AC reforced: build-time assertion + chain fallback + CI grep gate como defense-in-depth. **Cross-ref:** OPS-DEVOPS-001 (runtime internal hostname `bidiq-backend.railway.internal`). | @sm (River) |
| 2026-04-29 | 1.3 | v1.2 refresh validation: GO (10/10). Stage 7 reinforce Disc 1 build-time inviabilizado é fato confirmado. Não-overlap OPS-DEVOPS-001 explícito. Status mantém Ready. | @po (Pax) |
| 2026-04-29 | 1.4 | **Implementado Wave 2 — zany-kurzweil session.** AC2 (Dockerfile assertion) já feito linhas 138-153 (skip — pre-existing). AC1+AC3-AC6 done: helper `frontend/lib/backend-url.ts::getBackendUrl()` chain `BACKEND_URL \|\| NEXT_PUBLIC_BACKEND_URL \|\| 'http://localhost:8000'`. Refactor 4 callsites P0 (cnpj/[cnpj], orgaos/[slug], itens/[catmat] x2, sitemap.ts). CI grep gate em `.github/workflows/frontend-tests.yml` rejeita antipattern `process.env.BACKEND_URL \|\| 'http://localhost'` sem NEXT_PUBLIC fallback. Tests 5 cases em `__tests__/lib/backend-url.test.ts`. Status: Ready → Done. | @dev (James) |

## File List

- `frontend/lib/backend-url.ts` (NEW) — `getBackendUrl()` helper chain (AC4)
- `frontend/__tests__/lib/backend-url.test.ts` (NEW) — 5 test cases (AC6)
- `frontend/app/sitemap.ts` (refactor linha 26) — usa helper, mantém chain (AC3)
- `frontend/app/cnpj/[cnpj]/page.tsx` (refactor linha 7) — usa helper (AC3)
- `frontend/app/orgaos/[slug]/page.tsx` (refactor linha 7) — usa helper (AC3)
- `frontend/app/itens/[catmat]/page.tsx` (refactor linhas 47, 62) — usa helper em fetchProfile + generateStaticParams (AC3)
- `.github/workflows/frontend-tests.yml` (add step "Lint BACKEND_URL fallback chain") — CI grep gate (AC5)
