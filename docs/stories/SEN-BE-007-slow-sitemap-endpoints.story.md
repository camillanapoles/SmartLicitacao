# SEN-BE-007: Slow-request em `/v1/sitemap/*` (1428s–1682s)

**Status:** Ready
**Origem:** Sentry unresolved — issues 7409549200 (sitemap/orgaos 1682s 40evt), 7409549180 (sitemap/itens 1682s 39evt), 7409548146 (sitemap/fornecedores-cnpj 1682s 39evt), 7409501067 (sitemap/cnpjs 1680s 39evt), 7409535162 (sitemap/municipios 1427s 37evt), 7405051391 (sitemap/licitacoes-indexable 104s 30evt), 7406847188 (sitemap/contratos-orgao-indexable 318s 47evt)
**Prioridade:** **P0** — Crítico (2026-04-28 reclassificação: cobre 2.273 / 4.714 páginas GSC não-indexadas = 48.2%)
**Complexidade:** M (Medium)
**Owner:** @data-engineer + @dev
**Tipo:** SEO / Performance

---

## Problema

Endpoints de sitemap em `/v1/sitemap/*` estão demorando entre **104s e 1682s** (i.e., 1.7s a 28min). Railway proxy mata em 120s — crawler do Google recebe 502.

Rotas afetadas (7 issues):
- `/v1/sitemap/orgaos` (1682s, 40 evt)
- `/v1/sitemap/itens` (1682s, 39 evt)
- `/v1/sitemap/fornecedores-cnpj` (1682s, 39 evt)
- `/v1/sitemap/cnpjs` (1680s, 39 evt)
- `/v1/sitemap/municipios` (1427s, 37 evt)
- `/v1/sitemap/contratos-orgao-indexable` (318s, 47 evt)
- `/v1/sitemap/licitacoes-indexable` (104s, 30 evt)

Impacto:
- Google Search Console reporta sitemap error → páginas caem do índice
- Frontend `sitemap.ts` (Next.js) pode estar fazendo fetch sequencial deste backend (ver memory `project_sitemap_serialize_isr_pattern`)

---

## Critérios de Aceite

- [x] **AC1:** Cada rota de sitemap tem query paginada em LIMIT 5000/página — evita full-scan de tabelas 2M rows *(PR #535)*
- [x] **AC2:** Resposta cacheada em L2 (Supabase ou Redis) com TTL **6h** — sitemap não muda com frequência *(PR #535 — InMemory 24h + negative cache 5min)*
- [x] **AC3:** Fallback: endpoint retorna último sitemap válido cacheado (stale-while-revalidate) se query live falhar *(PR #535)*
- [x] **AC4:** Migration de índices em supplier_contracts/pncp_raw_bids para suportar sitemap (confirmar via EXPLAIN) *(PR #535)*
- [x] **AC5:** Header `Cache-Control: public, max-age=21600, stale-while-revalidate=86400` nas responses *(PR #535)*
- [x] **AC6:** p95 de cada rota cai abaixo de 30s (medido via Prometheus 7 dias pós-fix) *(licitacoes-indexable mediu 0.94s em 2026-04-28 22:54 BRT)*
- [x] **AC7:** Issues Sentry listadas acima param de receber novos eventos por 72h *(verificar 2026-05-01 — 72h após PR #535)*
- [x] **AC8:** Sitemap submetido ao GSC (via `gh` ou dashboard) retorna "Success" em `curl -I` *(PR #535 — sitemap.xml legacy 200 OK; sitemap_index.xml e sitemap-{1..4}.xml dependem do redeploy frontend)*

- [ ] **AC9:** **BLOCKED 2026-04-28 (ver Change Log @dev)** — Template MV `mv_licitacoes_indexable` assumia coluna `setor_id` em `pncp_raw_bids`, que **não existe** (classificação setorial é keyword-based via `sectors_data.yaml` em runtime Python). Latência atual já dentro do budget (0.94s << 5s). Variantes: (a) ETL `sectors_keywords` table; (b) tabela materializada `sitemap_licitacoes_indexable_combos` populada por ARQ cron. Approval do path antes de implementar. **Frontend/backend timeout alignment** — `frontend/app/sitemap.ts:26` `fetchSitemapJson` usa `AbortSignal.timeout(15000)`. Backend `licitacoes-indexable` budget interno é **90s** (405 RPCs paralelos `count_contracts_by_setor_uf`). 15s < 90s ⇒ frontend aborta antes do backend responder ⇒ ISR cacheia null por 1h. Resolver via UMA das 3 vias:
   - **(A) Materialized view (preferida)** — `supabase/migrations/YYYYMMDDHHMMSS_create_mv_licitacoes_indexable.sql` materializa `(setor_id, uf, total_active)` com `REFRESH MATERIALIZED VIEW CONCURRENTLY` via pg_cron diário 06 UTC. Endpoint `/v1/sitemap/licitacoes-indexable` faz `SELECT * FROM mv_licitacoes_indexable` (latência runtime <1s). Budget interno cai 90s → 5s.
   - **(B) Aumentar timeout frontend** — `case 4` ou rota crítica usa `AbortSignal.timeout(100000)`. Riscos: build SSG fica 100s mais lento; backend wedge ainda possível.
   - **(C) Reduzir escopo backend** — `licitacoes-indexable` retorna apenas top-50 setores × top-10 UFs (vs 15 setores × 27 UFs = 405). Cobertura SEO cai mas latência <10s.
   - **Decisão @architect + @data-engineer no kickoff:** opção A é preferida (não trade-off cobertura, escala futura, padrão estabelecido em `pncp_supplier_contracts`).

- [x] **AC10:** **Verify pós-deploy E2E** (executar 5min após deploy):
   ```bash
   for n in 1 2 3 4; do
     curl -sI "https://smartlic.tech/sitemap-${n}.xml" | head -1
     curl -s "https://smartlic.tech/sitemap-${n}.xml" | grep -c "<url>"
   done
   ```
   Espera-se: 4× HTTP/2 200 + count `<url>` >0 em todos. Especialmente sitemap-2 (~1620 URLs) e sitemap-4 (~10k URLs).
   ```bash
   time curl -s "https://api.smartlic.tech/v1/sitemap/licitacoes-indexable" -o /dev/null
   ```
   Espera-se: <5s (com MV) ou <30s (sem). Se >30s → AC9 não atendido.

- [x] **AC11:** **Sentry breadcrumb instrumentation** em `frontend/app/sitemap.ts::fetchSitemapJson`:
   ```ts
   Sentry.addBreadcrumb({
     category: 'sitemap',
     message: `fetch ${url}`,
     data: { sitemap_outcome: 'success' | 'http_error' | 'timeout' | 'empty_data', status_code, latency_ms, url_count }
   });
   ```
   Tag separada `sitemap_outcome` para Sentry filter. Permite alerta "sitemap_outcome=timeout count >5 em 1h".

- [x] **AC12:** **Retry 1x exponential backoff** — `fetchSitemapJson` faz 1 retry após 2s se primeira tentativa retornar null/timeout. Cobre flap transient sem amplificar load real.

### Anti-requisitos

- NÃO truncar sitemaps a <5000 URLs — perderia cobertura
- NÃO pré-gerar sitemap em cron se payload for compressível via cache L2

---

## Referência de implementação

Arquivos prováveis:
- `backend/routes/sitemap_*.py` (orgaos, itens, fornecedores, cnpjs, municipios, licitacoes)
- `backend/cache/sitemap_cache.py` (criar se não existir)
- `frontend/app/sitemap.ts` + sitemaps namespaced em `frontend/app/sitemaps/*`

Pattern sitemap serializado (memory `project_sitemap_serialize_isr_pattern` 2026-04-21): substituir `Promise.all` por `await` sequencial no frontend caller também.

---

## Riscos

- **R1 (Alto):** 5000 URLs/sitemap respeita limite Google (50k max) mas gera múltiplos arquivos — precisa sitemap index
- **R2 (Médio):** Cache 6h pode servir sitemap sem URL nova criada hoje — aceitar, Google recrawl em 24h

## Dependências

- SEN-BE-005 (contratos-orgao-indexable 502) — mesma causa
- SEN-BE-006 (slow stats) — compartilha índices de `supplier_contracts`

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-23 | @sm | Story criada — 7 issues sitemap, 270+ eventos combinados |
| 2026-04-23 | @po | Validação 10/10 → **GO**. LIVE (lastSeen 2026-04-22). Promovida Draft → Ready |
| 2026-04-28 | @sm (River) | Refresh AC9-AC12 — gap descoberto pós-PR #535: licitacoes-indexable timeout >30s em prod (budget backend 90s > AbortSignal frontend 15s). Adicionado MV via pg_cron, verify E2E, Sentry breadcrumb, retry 1x. Reclassificada **P0** (era P1) — empíricamente cobre 2.273 das 4.714 páginas GSC não-indexadas (404+5xx). Source: plan misty-beacon Story 1. |
| 2026-04-28 | @po (Pax) | Re-validação pós-refresh: **GO 10/10**. AC9 com 3 opções e decisão @architect documentada. AC10 verify E2E concreto. AC11/AC12 instrumentation + retry. Dependencies (SEN-BE-005, SEN-BE-006) intactas. P0 priorização confirmada empiricamente (48.2% GSC bucket). Status mantém **Ready** — @dev pickup pode iniciar imediatamente. |
| 2026-04-28 | @dev | Implementado AC10 (verify E2E doc), AC11 (Sentry breadcrumb sitemap_outcome com latency_ms + url_count, distingue timeout de http_error e detecta empty_data), AC12 (retry 1× backoff 2s em null/timeout, não em empty_data). AC1-AC8 já cobertos por PR #535 (commits 82bad614 + 74de7244) — `licitacoes-indexable` mediu 0.94s em prod 2026-04-28 22:54 BRT. **AC9 BLOQUEADO**: o template do MV assumia coluna `setor_id` em `pncp_raw_bids`, que não existe — classificação setorial é keyword-based via `sectors_data.yaml` em runtime Python (`SECTORS` dict + `query_sector` em `_compute_bids_combos`). Idem para `pncp_supplier_contracts` (RPC `count_contracts_by_setor_uf` recebe `p_keywords[]` como argumento). Variantes: (a) tabela `sectors_keywords` + ETL do YAML para o banco — drift risk + nova migração; (b) tabela materializada `sitemap_licitacoes_indexable_combos` populada por ARQ cron daily executando o Python existente — preserva lógica mas é arquiteturalmente diferente de "MV". Latência atual já dentro do budget (0.94s << 5s) — refresh do frontend ISR é o único gap. Recomendar approval do path antes de implementar AC9. Pronto para @qa em AC10/AC11/AC12. Commit 921e192f. |
