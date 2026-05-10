# SEO-P0-003 — Auditoria de unicidade + noindex/merge das ~9k programáticas

**Data:** 2026-05-10
**Issue:** [#989](https://github.com/tjsasakifln/pncp-poc/issues/989)
**Epic:** #986
**Branch:** `feat/989-pseo-uniqueness-audit-noindex`

## Contexto

GSC (28d, 2026-05-09) mostra ~1.000 páginas com impressões dos ~10k+ URLs declarados em `frontend/app/sitemap.ts`. As ~9.000 restantes estão fora do índice — desde a March 2026 Core Update o classificador HCU é always-on e site-wide, então a seção mais fraca arrasta o domínio inteiro. 7.014 impressões US a 0,03% CTR é o perfil clássico que SpamBrain pondera como "Scaled Content Abuse — minor keyword variants without sufficient differentiation".

## Escopo desta PR

Por convenção (#988/#990 separadas), esta PR entrega:

1. Script de auditoria `scripts/seo/uniqueness_audit.py` (Python stdlib + httpx).
2. Helpers TypeScript em `frontend/lib/seo/noindex.ts` + slug list auto-gerada em `frontend/lib/seo/noindex-slugs.ts`.
3. Wiring de `metadata.robots.index = !isNoindexed(...)` em 4 page families:
   - `frontend/app/cnpj/[cnpj]/page.tsx`
   - `frontend/app/fornecedores/[cnpj]/page.tsx`
   - `frontend/app/contratos/orgao/[cnpj]/page.tsx`
   - `frontend/app/blog/licitacoes/[setor]/[uf]/page.tsx`
4. Filtragem de URLs flagged em `frontend/app/sitemap.ts` (sub-sitemaps id:2 e id:4).
5. CSV inicial em `docs/seo/audits/uniqueness-2026-05.csv` (apenas header — preenchimento out-of-band).
6. Suite de testes: pytest em `scripts/tests/test_seo_uniqueness_audit.py` + jest em `frontend/lib/seo/__tests__/noindex.test.ts`.

**Deferido para PRs separadas:**

- **canonical merge** (`alternates: { canonical: <winner> }`) — issue #990. O CSV emitido pelo audit já carrega `action=canonical_merge` para uso pela próxima PR.
- **title duplicates / hreflang** — issues #987 / #988.

## Pipeline do script

```
python scripts/seo/uniqueness_audit.py \
  --sitemap https://smartlic.tech/sitemap.xml \
  --output  docs/seo/audits/uniqueness-2026-05.csv \
  --sample  500 \
  --families fornecedores-cnpj cnpj contratos-orgao blog-licitacoes-setor-uf \
  --emit-noindex-lib frontend/lib/seo/noindex-slugs.ts
```

1. Crawla sitemap index + sub-sitemaps (5 sub).
2. Filtra URLs por route family (regex contra path).
3. (Opcional) Estratifica amostra `--sample N` por família — determinístico via seed=42. Necessário para sessões curtas: o crawl completo de ~10k URLs leva 80+ min com politeness 0.5s.
4. Fetch + extract texto server-rendered (strip script/style/nav/footer/header).
5. Tokeniza (preserva acentos PT-BR), gera 5-shingles, computa Jaccard contra todos os pares dentro da mesma família.
6. Classifica em `action`:
   - similarity ≥ 0.70 → **canonical_merge** (deferido)
   - 0.40 ≤ sim < 0.70 + word_count < 300 → **noindex**
   - sim < 0.40 + word_count ≥ 300 → **keep**
   - else → **noindex** (catch-all: thin + low-similarity = baixo sinal)
7. Emite CSV. Opcionalmente regenera `frontend/lib/seo/noindex-slugs.ts` com a lista determinística (sorted) das slugs `action=noindex`.

## Thresholds (Discovered Labs 2026)

| Sinal | Limite | Resultado |
|-------|--------|-----------|
| Dados únicos por página | ≥ 40% | mínimo para HCU não classificar como doorway |
| Dados únicos por página | ≥ 70% | safe zone |
| Diff vs vizinho-template | < 30% | trigger SCA |

Os shingles k=5 + Jaccard são o proxy operacional desses limites. Threshold 0.70 mapeia para "70% overlap" do conteúdo textual.

## Como executar a auditoria completa

O crawl real de ~10k URLs (5 sub-sitemaps × ~2k URLs/sitemap) excede 80 min em sessão única. Procedimento recomendado:

1. Rodar fora de horário de pico (após 22h BRT) contra produção:
   ```bash
   python scripts/seo/uniqueness_audit.py \
     --sitemap https://smartlic.tech/sitemap.xml \
     --output  docs/seo/audits/uniqueness-2026-05.csv \
     --politeness 0.5 \
     --emit-noindex-lib frontend/lib/seo/noindex-slugs.ts
   ```
2. Revisar contagem por `action` no log de stderr.
3. Cross-validar com GSC Coverage: páginas em `keep` que aparecem como "Crawled - currently not indexed" devem ser registradas em SEO-P1-005 / SEO-P2-009 para enriquecimento.
4. Commit do CSV + lib regenerada.
5. Verificar redução do `lastmod` count em `curl https://smartlic.tech/sitemap.xml | wc -l` após o deploy ter ISR-revalidado.

## Métricas de sucesso (medir 28d pós-merge)

| Métrica | Antes | Meta |
|---------|-------|------|
| Indexation rate (pages indexed / declared) | ~10% | ≥ 80% (com taxa absoluta menor mas sem drag) |
| Impressões totais (curto prazo, -14d) | baseline | -20-30% (remoção de zumbis) |
| CTR posições médias páginas `keep` (médio prazo, 28-90d) | baseline | em alta por remoção de drag site-wide HCU |

## Risco aceito

Prune temporário derruba inventory de impressões. **Trade explícito:** trocar volume de impressões zumbis (que não convertem cliques) por re-ranking das páginas que importam. Plano de rollback: bastará popular `NOINDEX_SLUGS` como `Set()` vazio em `noindex-slugs.ts` para reverter — `metadata.robots.index` cai de volta para `true` e sitemap volta a emitir todas as URLs no próximo ISR (1h).

## Constraints técnicas obedecidas

- Sitemap convention `/sitemap/[id].xml` (memory ref) — não tocada.
- ISR alignment: nenhum `cache: 'no-store'` adicionado em rotas com `revalidate=N` (memory ref SEN-FE-001).
- `lib/seo/noindex.ts` é puro client-safe (sem fetch); funciona em build-time e em ISR.
- Skip Next 16 build (WSL OOM, memory ref) — testes apenas via pytest e jest.

## Arquivos alterados

```
scripts/seo/__init__.py                                                  (new)
scripts/seo/uniqueness_audit.py                                          (new, ~470 LOC)
scripts/tests/test_seo_uniqueness_audit.py                               (new, ~280 LOC)
frontend/lib/seo/noindex.ts                                              (new)
frontend/lib/seo/noindex-slugs.ts                                        (new, auto-gen, empty)
frontend/lib/seo/__tests__/noindex.test.ts                               (new)
frontend/app/sitemap.ts                                                  (filter wiring)
frontend/app/cnpj/[cnpj]/page.tsx                                        (robots gate)
frontend/app/fornecedores/[cnpj]/page.tsx                                (robots gate)
frontend/app/contratos/orgao/[cnpj]/page.tsx                             (robots gate)
frontend/app/blog/licitacoes/[setor]/[uf]/page.tsx                       (robots gate)
docs/seo/audits/uniqueness-2026-05.csv                                   (header only)
docs/sessions/2026-05/seo-p0-003-uniqueness-audit.md                     (this doc)
```
