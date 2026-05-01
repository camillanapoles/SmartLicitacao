# SAB-002: Unicode escape sequences renderizadas como texto literal

**Origem:** UX Premium Audit P0-02
**Prioridade:** P0 — BLOQUEADOR
**Complexidade:** M (Medium)
**Sprint:** SAB-P0 (imediato)
**Owner:** @dev
**Screenshots:** `ux-audit/24-historico.png`, `ux-audit/25-pipeline.png`, `ux-audit/26-alertas.png`

---

## Problema

Textos em 3 páginas principais exibem Unicode escapes como texto literal em vez de caracteres acentuados:

| Página | Texto renderizado | Esperado |
|--------|------------------|----------|
| Histórico (header) | `Hist\u00f3rico` | Histórico |
| Pipeline (empty state) | `licita\u00e7\u00f5es`, `est\u00e1gios`, `c\u00e1`, `in\u00edcio` | licitações, estágios, cá, início |
| Alertas (subtítulo) | `notificacoes automaticas sobre novas licitacoes` | notificações automáticas sobre novas licitações |

**Causa provável:** Strings JSON com Unicode escapes (`\u00e7`) sendo renderizadas sem `JSON.parse()`, ou double-encoding (JSON.stringify de strings que já são UTF-8).

**REGRESSÃO:** Este bug foi identificado no audit de 2026-02-23 (BUG P2 item UX-353) e **não foi corrigido**. Agora aparece em mais páginas.

---

## Critérios de Aceite

### Diagnóstico

- [x] **AC1:** Mapear TODAS as páginas que exibem texto com Unicode escapes (Histórico, Pipeline, Alertas + qualquer outra)
  - 8 files: historico, pipeline, alertas, dashboard, ajuda, BottomNav, Sidebar, SearchResults
- [x] **AC2:** Identificar a origem do texto: é hardcoded no frontend, vem do backend via API, ou vem do banco (Supabase)?
  - All hardcoded in frontend source code (JSX text content and attributes)
- [x] **AC3:** Determinar se é double-encoding (JSON.stringify de string já escaped) ou falta de decoding (string JSON crua)
  - Two patterns: (1) `\u00XX` escape sequences in JSX (not decoded by JSX compiler), (2) plain missing accents in alertas

### Fix Global

- [x] **AC4:** Corrigir na FONTE (não em cada componente). Se é backend: garantir que JSON responses usam UTF-8 puro. Se é frontend: garantir decode correto onde os textos são definidos.
  - Replaced all 31 `\u00XX` escapes with UTF-8 characters + fixed 7 plain missing accents in alertas
- [x] **AC5:** Histórico — header exibe "Histórico" com acento correto
- [x] **AC6:** Pipeline empty state — todos os textos com acentos corretos: "licitações", "estágios", "início"
- [x] **AC7:** Alertas subtítulo — "notificações automáticas sobre novas licitações"
- [x] **AC8:** Buscar e corrigir qualquer OUTRO texto com padrão `\uXXXX` em todo o frontend (`grep -r '\\u00' frontend/`)
  - dashboard (15 instances), ajuda (1), BottomNav (1), SearchResults (1)

### Prevenção

- [x] **AC9:** Adicionar lint rule ou test que detecta `\u00` em strings hardcoded do frontend (prevenção de regressão)
  - 11 tests added to `__tests__/accents-smoke.test.tsx` (SAB-002 section): 8 file scans + 3 specific assertions

---

## Arquivos Prováveis

- `frontend/app/historico/page.tsx` — header "Histórico"
- `frontend/app/pipeline/page.tsx` — empty state texts
- `frontend/app/alertas/page.tsx` — subtítulo
- Qualquer arquivo com strings contendo `\u00`

## Files Changed

| File | Changes |
|------|---------|
| `frontend/app/historico/page.tsx` | 8 fixes: Concluída, histórico, Faça, parâmetros (×2), análise, você (×2) |
| `frontend/app/pipeline/page.tsx` | 5 fixes: Faça, licitações (×3), estágios, possível, cá, início, avança, está |
| `frontend/app/alertas/page.tsx` | 7 fixes: Faça, notificações, licitações (×2), automáticos, alterações, excluído, vírgula, última, você |
| `frontend/app/dashboard/page.tsx` | 15 fixes: Ícone, Faça, indisponíveis (×6), Inteligência, Após/você/verá, Tendências, Mês, período, rápido, Histórico |
| `frontend/app/ajuda/page.tsx` | 1 fix: cartão, crédito, Bancário, até, úteis, confirmação |
| `frontend/components/BottomNav.tsx` | 1 fix: Histórico |
| `frontend/components/Sidebar.tsx` | Already fixed (pre-existing) |
| `frontend/app/buscar/components/SearchResults.tsx` | 1 fix: Análise |
| `frontend/__tests__/accents-smoke.test.tsx` | +11 SAB-002 regression prevention tests |

## Notas

- Este é um bug de REGRESSÃO que persiste há 5+ dias. Prioridade máxima na correção.
- O fix deve ser global (na fonte), não patch por página.
- Root cause: JSX text content and attribute strings do NOT process `\u00XX` Unicode escape sequences — they render as literal text. Fix: replace with actual UTF-8 characters.
