# STORY-SEO-028: 55 URLs `/blog/licitacoes/{cat}/{uf}` 404 (categorias órfãs)

## Status

**Ready (GO @po 2026-04-27)** — promovida Draft → Ready; ver §"Verdict @po"

## Prioridade

P2 — Médio (55 URLs com 404 confirmado; afeta percepção de qualidade do site para Google)

## Origem

- Inspeção GSC root-cause 2026-04-27 (`docs/sessions/2026-04/2026-04-27-gsc-rootcause-brief-for-sm.md` §3.1 + S5)

## Tipo

SEO / Data / Routing

## Owner

@dev + @data-engineer

## Story

**As a** time de growth orgânico,
**I want** que URLs `/blog/licitacoes/{categoria}/{uf}` apontando para categorias removidas/renomeadas redirecionem para alternativa válida (ou retornem 410 Gone),
**so that** Google atualize seu índice e pare de reportar 55 hits 404 em queries com referência externa antiga.

## Problema

GSC cluster "Não encontrado (404)" reporta 55 URLs em `/blog/licitacoes/{categoria}/{uf}`. Exemplo validado: `https://smartlic.tech/blog/licitacoes/materiais_hidraulicos/mg` → 404.

Rota frontend `app/blog/licitacoes/[setor]/[uf]/page.tsx` linha 188 dispara `notFound()` quando:
- `!sector` — categoria não existe na enum/list válida
- `!ALL_UFS.includes(ufUpper)` — UF malformada

Hipótese: categoria `materiais_hidraulicos` foi renomeada para `materiais-hidraulicos` (underscore→hyphen) ou removida; URLs com nome antigo permanecem em backlinks/sitemap legacy.

## Critérios de Aceite

- [ ] **AC1:** Mapeamento exportado: para cada uma das 55 URLs únicas no cluster, identificar categoria + UF e classificar como (a) renomeada/migrada, (b) removida, (c) UF malformada
- [ ] **AC2:** Para categorias renomeadas (ex: `materiais_hidraulicos` → `materiais-hidraulicos`): adicionar 301 redirect na rota dinâmica (next.config.js redirects ou middleware)
- [ ] **AC3:** Para categorias removidas: confirmar que sitemap NÃO emite URLs antigas; opcionalmente retornar 410 Gone explícito
- [ ] **AC4:** Lista canônica de categorias válidas é centralizada em uma source-of-truth única (ex: `frontend/app/lib/sectors.ts` ou similar) — verificar se já existe e está sincronizada com backend `sectors_data.yaml`
- [ ] **AC5:** Sitemap em produção (`/sitemap/3.xml` ou onde blog está) não inclui combinações de categoria órfã
- [ ] **AC6:** Pós-deploy: ≤5 URLs `/blog/licitacoes/*/*` no cluster 404 do GSC em 30 dias
- [ ] **AC7:** Para os 11 hits específicos em `/blog/licitacoes/cidade` (sub-pattern observado no cluster noindex §3.2): validar que esse path é intencional (rota `app/blog/licitacoes/cidade/[cidade]/[setor]/page.tsx` existe)

### Anti-requisitos

- NÃO redirect 301 para homepage como fallback genérico (soft 404 penalty)
- NÃO criar páginas vazias só para evitar 404 — pior que 404

## Tasks / Subtasks

- [x] Task 1 — Exportar e classificar URLs (AC: 1)
  - [x] @data-engineer extrai 55 URLs do arquivo `/mnt/d/pncp-poc/gsc-404-urls.txt` (filtrando por `/blog/licitacoes/`)
  - [x] Comparar `{categoria}` extraído vs lista canônica de setores
  - [x] Output: planilha/tabela com classificação a/b/c
- [x] Task 2 — Source-of-truth de setores (AC: 4)
  - [x] Verificar se `frontend/app/lib/sectors.ts` (ou equivalente) existe
  - [x] Sincronizar com `backend/sectors_data.yaml`
  - [x] Documentar como adicionar/renomear setor sem quebrar URLs antigas
- [x] Task 3 — Redirects (AC: 2)
  - [x] @dev adiciona redirects em `next.config.js` ou `middleware.ts` para mapeamentos identificados
- [ ] Task 4 — 410 Gone (AC: 3)
  - [ ] @dev modifica `app/blog/licitacoes/[setor]/[uf]/page.tsx` para retornar 410 quando setor é deprecated (vs 404 genérico)
- [ ] Task 5 — Validação (AC: 6, 7)
  - [ ] Re-medir GSC em 30d
  - [x] Confirmar `/blog/licitacoes/cidade` continua funcionando (não regressão)

## Referência de implementação

- `frontend/app/blog/licitacoes/[setor]/[uf]/page.tsx` (rota afetada)
- `frontend/app/blog/licitacoes/cidade/[cidade]/[setor]/page.tsx` (rota relacionada)
- `frontend/app/lib/sectors.ts` (verificar nome real)
- `backend/sectors_data.yaml`
- Brief: `docs/sessions/2026-04/2026-04-27-gsc-rootcause-brief-for-sm.md` §3.1

## Riscos

- **R1 (Médio):** Se categoria foi removida intencionalmente, redirect pode confundir usuário levando a página não relacionada — preferir 410 nesses casos
- **R2 (Baixo):** Mudança em `next.config.js` requer rebuild — incluir em deploy normal

## Dependências

- **Bloqueada por:** STORY-INC-001 (validação requer backend respondendo)
- **Coordena com:** STORY-SEO-001 (sitemap-4 InProgress)

## Verdict @po (2026-04-27)

**GO — Ready (6/6 sections PASS).**

| Section | Status | Notas |
|---------|--------|-------|
| 1. Goal & Context Clarity | PASS | 55 URLs concreto; valor business (qualidade percebida pelo Google) explícito |
| 2. Technical Implementation Guidance | PASS | Hipótese underscore→hyphen + caminhos `app/blog/licitacoes/[setor]/[uf]/page.tsx` + AC sobre source-of-truth setores |
| 3. Reference Effectiveness | PASS | Brief §3.1 + arquivo bruto `gsc-404-urls.txt` + `backend/sectors_data.yaml` |
| 4. Self-Containment | PASS | Anti-requisitos cobrem armadilhas (soft 404 redirect) |
| 5. Testing Guidance | PASS | AC6 mensura GSC pós-deploy 30d; AC4 testa source-of-truth |
| 6. CodeRabbit Integration | N/A | Não configurado |

**Overlap check:** STORY-SEO-017 cobre `/blog/licitacoes-do-dia/{data}` (42 URLs, hardcoded 30 dias) — **distinto** de meu cluster `/blog/licitacoes/{cat}/{uf}` (55 URLs, cat+uf programmatic). Sem duplicação.

**Pré-requisito de execução:** STORY-INC-001 era pré-requisito mencionado, mas withdrawn. Substituir por: **bloqueada parcialmente por SEN-BE-001/SEN-BE-008** (mensuração GSC AC6 só faz sentido com backend funcional). Tasks 1-4 podem rodar imediatamente.

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-27 | @sm (River) | Story criada a partir do brief GSC root-cause §3.1 + S5 |
| 2026-04-27 | @po (Sarah) | **Validação 6-section: 6/6 PASS → GO**. Status: Draft → Ready. Substituir bloqueio "STORY-INC-001" por "SEN-BE-001 + SEN-BE-008" (INC-001 withdrawn). |
| 2026-05-06 | @dev (Dex) | Classificação local dos 55 URLs, redirects 301 para setores legados claros e testes focados adicionados. |

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `node .aiox-core/development/scripts/generate-greeting.js dev` falhou antes/depois do install frontend porque o root não tem `node_modules/js-yaml` instalado.
- `npm run lint` em `frontend/` falhou: `next lint` interpretado como diretório inválido pelo Next instalado (`Invalid project directory provided, no such directory: /tmp/pncp-issue-613/frontend/lint`).
- `npm run typecheck -- --pretty false` em `frontend/` falhou: script `typecheck` ausente no `frontend/package.json`.

### Completion Notes List

- Classifiquei os 55 URLs locais de `gsc-404-urls.txt` em `docs/spikes/STORY-SEO-028-gsc-404-blog-licitacoes-classification.md`: 8 renamed/migrated, 31 canonical sector leaf URLs, 16 city URLs, 0 removed, 0 UF malformed.
- Adicionei redirects 301 apenas para aliases legados observados: `materiais_hidraulicos`, `engenharia_rodoviaria`, `manutencao_predial`, `software_desenvolvimento`, `software_licencas`, `medicamentos`, `frota_veicular`.
- Não adicionei fallback genérico nem redirect para homepage. Como a classificação local encontrou 0 categorias removidas e 0 UFs malformadas, 410 explícito não foi necessário nesta implementação.
- Confirmei que `/blog/licitacoes/cidade/[cidade]` e `/blog/licitacoes/cidade/[cidade]/[setor]` existem; os 16 URLs `cidade` do cluster batem com slugs canônicos de cidade/setor.
- Confirmei que `frontend/app/sitemap.ts` já normaliza IDs backend com `backendIdToFrontendSlug()` antes de emitir `/blog/licitacoes/{setor}/{uf}` no shard `id:2`.

### File List

- `docs/spikes/STORY-SEO-028-gsc-404-blog-licitacoes-classification.md`
- `docs/stories/STORY-SEO-028-blog-licitacoes-orphan-categorias.md`
- `frontend/__tests__/seo/legacy-licitacoes-redirects.test.js`
- `frontend/lib/legacy-licitacoes-redirects.js`
- `frontend/next.config.js`

### Validation

- `npm ci` em `frontend/` — passou; instalou dependências locais para validação.
- `npm test -- --runTestsByPath __tests__/seo/legacy-licitacoes-redirects.test.js --runInBand` em `frontend/` — passou (3 testes).
- `npx tsc --noEmit --pretty false` em `frontend/` — passou.
- `node -e "Promise.resolve(require('./next.config.js').redirects()).then(...)"` em `frontend/` — passou; gerou 7 redirects legados.
- `node - <<'NODE' ... unstable_getResponseFromNextConfig ... NODE` em `frontend/` — passou; redirect legado testado como 301 com query string preservada.
- `git diff --check` — passou.
