# Spec: Observatory & SEO Programmatic

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-05-08
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `observatory-seo`
- **Path**: `backend/routes/` (18 routers: observatorio, blog_stats, sitemap_*, empresa_publica, orgao_publico, contratos_publicos, dados_publicos, municipios_publicos, itens_publicos, compliance_publicos, indice_municipal, alertas_publicos, sectors_public, stats_public, calculadora, comparador, daily_digest, weekly_digest), `frontend/app/` (observatorio, cnpj, orgaos, municipios, licitacoes, contratos, blog, alertas-publicos, indice-municipal, compliance)

## Purpose

Módulo de SEO programático + observatory de mercado público. 18 routers backend (~8.300 LOC total), todos públicos (sem auth). Gera ~10.000+ páginas ISR no frontend via DataLake (`pncp_raw_bids` 400d + `pncp_supplier_contracts` 2M+ rows). Drive principal de organic inbound.

## ISR Pattern (Next.js + Backend)

```
Googlebot crawl /licitacoes/limpeza
  → Next.js dynamic route → page server component
  → fetch backend GET /v1/blog/stats/setor/limpeza
        next: { revalidate: 3600 }  ← SEN-FE-001 fix (aligned com revalidate const)
  → fresh (< 1h): serve cached HTML
  → stale (>= 1h): serve stale + trigger background regen
      ISR regen async:
        fetch backend /v1/blog/stats/setor/limpeza
        backend: RPC get_panorama_setor (DataLake GIN index)
        frontend: regenerate static HTML + JSON-LD FAQPage
        update CDN cache
```

**Antipattern SEN-FE-001 (corrigido):**
```
ERRADO:  export const revalidate = 3600 + fetch(url, { cache: 'no-store' })
CORRETO: export const revalidate = 3600 + fetch(url, { next: { revalidate: 3600 } })
```
Misalinhamento quebrava SSG e saturava backend (Stage 2 outage 2026-04-27).

## Sitemap Hierarchy

```
GET /sitemap.xml (index)
  → lista 4 sub-sitemaps:
      /sitemap/0.xml (licitacoes)  ← /sitemap/[id].xml (slash convention Next.js 16)
      /sitemap/1.xml (orgaos)
      /sitemap/2.xml (cnpjs)
      /sitemap/3.xml (licitacoes-do-dia)

Backend sub-sitemaps:
  sitemap_licitacoes.py → SELECT DISTINCT setor_id FROM pncp_raw_bids
  sitemap_orgaos.py     → SELECT DISTINCT cnpj_orgao FROM pncp_raw_bids
  sitemap_cnpjs.py      → SELECT DISTINCT cnpj FROM pncp_supplier_contracts
  sitemap_licitacoes_do_dia.py → bids WHERE data_publicacao = today

Cache-Control: max-age=3600, s-maxage=86400 (SYS-019/GSC-001 fix)
Cap: 50.000 URLs por arquivo (sitemap protocol limit)
```

**Convenção URL:** `/sitemap/[id].xml` (slash) — NÃO `/sitemap-[id].xml` (hyphen obsoleto Next.js 16).

## Routers (18) e DataLake Queries

### Observatory (observatorio.py)
- `GET /v1/observatorio` — panorama nacional top sectores + UFs
- `GET /v1/observatorio/raio-x/setor/{setor_id}` — deep-dive setor
- `GET /v1/observatorio/raio-x/municipio/{municipio_slug}` — análise municipal
- `GET /v1/observatorio/raio-x/orgao/{cnpj}` — perfil órgão comprador
- `GET /v1/observatorio/raio-x/alerta/{alerta_id}` — detalhe alerta

### Blog Stats (blog_stats.py)
- `GET /v1/blog/stats/setor/{setor}` → `get_panorama_setor` RPC
- `GET /v1/blog/stats/setor/{setor}/uf/{uf}` → contratos por setor×UF

### CNPJ / Empresa (empresa_publica.py)
- `GET /v1/empresa/{cnpj}` — perfil fornecedor

```
validate CNPJ format
→ query supplier_contracts WHERE cnpj_fornecedor=cnpj
    aggregate: total_won, valor_total, top_orgaos, evolucao_temporal
→ query entities WHERE cnpj (BrasilAPI enriched)
→ query sanctions_master WHERE cnpj
→ combine → FornecedorProfile
→ Frontend /cnpj/{cnpj}: Organization JSON-LD
```

### Órgão Público (orgao_publico.py)
- `GET /v1/orgao/{cnpj}` — perfil órgão + maiores fornecedores

### Contratos Públicos (contratos_publicos.py)
- `GET /v1/contratos/{setor}/{uf}` — contratos históricos filtrados

### Dados Públicos + Stats (dados_publicos.py, stats_public.py)
- `GET /v1/dados-publicos/{...}` — raw data open access
- `GET /v1/stats/public` — estatísticas agregadas públicas

### Municípios (municipios_publicos.py)
- `GET /v1/municipios/{slug}` — perfil municipal licitações

### Itens Licitados (itens_publicos.py)
- `GET /v1/itens/{...}` — itens por categoria/produto

### Compliance (compliance_publicos.py)
- `GET /v1/compliance/{cnpj}` — sanções + impedimentos CNPJ

### Índice Municipal (indice_municipal.py)
- `GET /v1/indice-municipal/{municipio_uf}` — scoring municipal (IBGE + PNCP)

### Alertas Públicos (alertas_publicos.py)
- `GET /v1/alertas-publicos/{setor}/{uf}` — preview alertas (public, pagwall CTA)

### Setores e Stats Públicos (sectors_public.py, stats_public.py)
- `GET /v1/setores` — catálogo de setores (público)
- `GET /v1/stats` — stats globais plataforma

### Calculadora + Comparador (calculadora.py, comparador.py)
- `GET /v1/calculadora` — calculadora de viabilidade (sem auth)
- `GET /v1/comparador` — comparador de licitações (sem auth)

### Digests (daily_digest.py, weekly_digest.py)
- `GET /v1/digest/daily` — digest diário público (preview de novas licitações)
- `GET /v1/digest/weekly/{setor}` — resumo semanal por setor

## DataLake Query Path (RPC)

```
SEO route handler
  → get_supabase(service_role=True)
  → sb.rpc('get_panorama_setor', {setor_id, days, uf})
      → Postgres function: uses GIN index (objeto tsquery) + idx (setor_id, uf)
      → returns aggregated panorama: {total_bids, valor_total, top_orgaos, evolucao_mensal}
  → Backend serialize → PanoramaStats
  → Frontend consume + JSON-LD generation
```

## CTA Tracking (Trial Conversion)

```
User anônimo em SEO page: clica 'Crie conta grátis'
  → POST /v1/analytics/track-cta {cta='trial-signup', source='/licitacoes/limpeza'}
  → 204 (fire-and-forget)
  → INSERT cta_tracking(cta, source, user_agent, ip_hash, ts)
  → redirect /signup?from=licitacoes-limpeza
```

## Frontend Routes (10.000+ páginas ISR)

| Pattern | JSON-LD Type | revalidate |
|---------|-------------|-----------|
| `/observatorio/[slug]` + raio-x subpages | FAQPage | 3600s |
| `/cnpj/[cnpj]`, `/fornecedores/[cnpj]` | Organization | 3600s |
| `/orgaos/[slug]` | Organization | 3600s |
| `/municipios/[slug]` | Place | 3600s |
| `/licitacoes/[setor]` | ItemList | 3600s |
| `/contratos/[setor]/[uf]` | ItemList | 3600s |
| `/contratos/orgao/[cnpj]` | ItemList | 3600s |
| `/blog/{contratos,licitacoes,panorama,programmatic}/[setor]` | Article | 3600s |
| `/alertas-publicos/[setor]/[uf]` | ItemList | 3600s |
| `/indice-municipal/[municipio-uf]` | Place | 3600s |
| `/compliance/[cnpj]` | Organization | 3600s |

## _run_with_budget Compliance (EPIC-RES-BE-2026-Q2)

Todos os 18 routers SEO programáticos DEVEM usar `_run_with_budget` em seus handlers (RES-BE-015 — PR #600/#603). Handlers sem budget podem wedge o event loop sob saturation.

```python
# Padrão obrigatório em routers SEO:
from pipeline.budget import _run_with_budget

@router.get("/v1/blog/stats/setor/{setor}")
async def get_blog_stats(setor: str):
    return await _run_with_budget(
        _fetch_blog_stats, setor,
        budget_s=ROUTE_TIMEOUT_S,
        phase="seo_blog_stats"
    )
```

## robots.txt (RFC 9309 compliant)

```
User-agent: *
Allow: /alertas-publicos/  ← prefix-match (SEO-026 fix PR #595)
Disallow: /buscar
Disallow: /dashboard
...
```

**Fix SEO-026:** RFC 9309 prefix-match libera `/alertas-publicos/*` no robots.txt (regex `Allow: /alertas-publicos` sem trailing slash era rejeitado por alguns crawlers).

## Invariants

1. **Todos routers públicos** — sem `require_auth`, sem `require_active_plan`
2. **DataLake-first** — queries via `search_datalake` RPC, nunca live APIs
3. **`_run_with_budget` obrigatório** em todos handlers (CI gate `audit-execute-without-budget.yml`)
4. **ISR revalidate alignment** — `const revalidate = N` DEVE igualar `next: { revalidate: N }` em fetch
5. **Sitemap slash convention** — `/sitemap/[id].xml` (Next.js 16)
6. **Cache-Control sub-sitemaps** — `s-maxage=86400` (SYS-019)
7. **IP hash** em CTA tracking (LGPD compliant)

## Functional Requirements

- **FR-1**: `GET /v1/blog/stats/setor/{setor}` retorna PanoramaStats via `get_panorama_setor` RPC
- **FR-2**: `GET /v1/empresa/{cnpj}` retorna FornecedorProfile (supplier_contracts + entities + sanctions)
- **FR-3**: Sitemap `/sitemap.xml` lista 4 sub-sitemaps com URLs corretas
- **FR-4**: Sub-sitemaps retornam XML com Cache-Control `max-age=3600, s-maxage=86400`
- **FR-5**: CTA tracking persiste ip_hash (não IP raw) + source
- **FR-6**: Todos handlers sob `_run_with_budget(budget_s=ROUTE_TIMEOUT_S)`
- **FR-7**: robots.txt com `Allow: /alertas-publicos/` (trailing slash, RFC 9309)

## Non-Functional Requirements

- **NFR-1**: `get_panorama_setor` RPC <100ms p95 (GIN index)
- **NFR-2**: ISR regen: primeiro request stale serve cached + regen em background (<3s p95)
- **NFR-3**: Sub-sitemaps: cap 50.000 URLs por arquivo
- **NFR-4**: Frontend build: ~4.146 páginas SSG (AbortSignal.timeout obrigatório p/ evitar cascade)
- **NFR-5**: CDN cache: `s-maxage=86400` sub-sitemaps (Googlebot recrawl diário)

## Constraints

- **CON-1**: 400d retention em `pncp_raw_bids` obrigatório (STORY-OBS-001) — observatório precisa histórico
- **CON-2**: Build SSG pode saturar backend → DB timeout → wedge (CRIT documentado): AbortSignal.timeout obrigatório em fetch no frontend
- **CON-3**: `pncp_supplier_contracts` crawl 3x/semana — dados podem ter até 56h de atraso
- **CON-4**: Sanções `sanctions_master` é tabela estática (atualização manual)
- **CON-5**: CNPJ validation deve ocorrer antes de qualquer DB query (formato: 14 dígitos numéricos)

## Acceptance Criteria

- AC-1: `GET /v1/blog/stats/setor/limpeza` retorna `panorama.total_bids > 0` (DataLake ativo)
- AC-2: `/sitemap.xml` retorna XML com 4 `<sitemap>` entries
- AC-3: `/sitemap/0.xml` retorna XML com `Cache-Control: s-maxage=86400`
- AC-4: Frontend `/licitacoes/limpeza` renderiza com `revalidate=3600` e JSON-LD `@type: ItemList`
- AC-5: CTA click → `cta_tracking` INSERT sem IP raw (apenas hash)
- AC-6: CI gate `audit-execute-without-budget.yml` não falha em routers SEO

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `setor_not_found` | 404 | setor_id não existe nos 20 setores |
| `cnpj_invalid` | 422 | CNPJ formato inválido |
| `municipio_not_found` | 404 | municipio_slug sem dados DataLake |
| `timeout_exceeded` | 503 | _run_with_budget expirou |
| `sitemap_generation_error` | 500 | DB query failure em sitemap (raro) |

## Code Traceability

- `backend/routes/observatorio.py` — observatory principal
- `backend/routes/blog_stats.py` — `get_panorama_setor` endpoint
- `backend/routes/empresa_publica.py` — CNPJ profile
- `backend/routes/sitemap_licitacoes.py` + `sitemap_orgaos.py` + `sitemap_cnpjs.py` + `sitemap_licitacoes_do_dia.py` — 4 sub-sitemaps
- `backend/datalake_query.py` — `search_datalake` RPC wrapper
- `backend/pipeline/budget.py:_run_with_budget` — obrigatório em todos handlers
- `frontend/app/licitacoes/[setor]/page.tsx` — ISR consumer
- `frontend/app/sitemap/[id]/route.ts` — sitemap route handler

## Dependencies

- Supabase (`pncp_raw_bids`, `pncp_supplier_contracts`, `enriched_entities`, `sanctions_master`, `indice_municipal`, `cta_tracking`)
- `get_panorama_setor` RPC (Postgres function)
- `pipeline.budget._run_with_budget` (timeout enforcement)
- Next.js ISR (`revalidate=3600`)
- JSON-LD structured data (FAQPage, Organization, ItemList, Place, Article)
- Google Search Console (external — monitoring cache-control, robots.txt)
