# Flowchart — Módulo `observatory+seo-programmatic`

> Gerado pelo **Reversa Archaeologist** em 2026-04-27 · Confiança 🟢 CONFIRMADO

## SEO programmatic page lifecycle (frontend ISR)

```mermaid
flowchart TD
    A[Googlebot crawl /licitacoes/limpeza] --> B[Next.js dynamic route]
    B --> C[Page server component]
    C --> D[fetch backend GET /v1/blog/stats/setor/limpeza next: revalidate=3600]
    D -->|fresh < 1h| E[serve cached HTML]
    D -->|stale >= 1h| F[serve stale + trigger background regen]
    F --> G[ISR regen async]
    G --> H[fetch backend pncp_raw_bids tsquery setor='limpeza']
    H --> I[backend RPC get_panorama_setor]
    I --> J[400 OK panorama JSON]
    J --> K[regenerate static HTML + JSON-LD FAQPage]
    K --> L[update CDN cache]
    E --> M[200 page]
    F --> M
```

## Sitemap generation hierarchy

```mermaid
flowchart TD
    A[/sitemap.xml index] --> B[lists 4 sub-sitemaps]
    B --> S1[/sitemap-licitacoes.xml]
    B --> S2[/sitemap-orgaos.xml]
    B --> S3[/sitemap-cnpjs.xml]
    B --> S4[/sitemap-licitacoes-do-dia.xml]
    S1 -->|backend| BE1[GET sitemap_licitacoes.py]
    S2 -->|backend| BE2[GET sitemap_orgaos.py]
    S3 -->|backend| BE3[GET sitemap_cnpjs.py]
    S4 -->|backend| BE4[GET sitemap_licitacoes_do_dia.py daily fresh]
    BE1 --> Q1[query distinct setor_id from pncp_raw_bids]
    BE2 --> Q2[query distinct cnpj_orgao]
    BE3 --> Q3[query distinct cnpj_fornecedor from supplier_contracts]
    BE4 --> Q4[query bids WHERE data_publicacao = today]
    Q1 & Q2 & Q3 & Q4 --> R[XML render with Cache-Control max-age=3600 swr=86400]
    R -->|cap 50k URLs por arquivo| OUT[response]
```

## CNPJ profile flow (/empresa/{cnpj})

```mermaid
flowchart TD
    A[GET /v1/empresa/{cnpj}] --> B[validate CNPJ format]
    B --> C[query supplier_contracts WHERE cnpj_fornecedor]
    C --> D[aggregate: total_won, valor_total, top_orgaos, evolucao_temporal]
    D --> E[query entities WHERE cnpj for BrasilAPI enriched data]
    E --> F[query sanctions_master WHERE cnpj]
    F --> G[combine FornecedorProfile]
    G --> H[200 JSON]
    H --> I[Frontend /cnpj/{cnpj}/page.tsx renders + Organization JSON-LD]
```

## DataLake query path (RPC)

```mermaid
flowchart TD
    A[SEO route handler] --> B[get_supabase service-role]
    B --> C[sb.rpc 'get_panorama_setor', {setor_id, days, uf}]
    C --> D[Postgres function]
    D --> E[uses GIN index on objeto tsquery + idx setor_id, UF]
    E --> F[returns aggregated panorama]
    F --> G[Backend serialize PanoramaStats]
    G --> H[Frontend consume]
```

## Trial CTA tracking

```mermaid
sequenceDiagram
    participant U as Anonymous user
    participant SEO as SEO page (rendered)
    participant API as POST /v1/analytics/track-cta
    participant DB as cta_tracking

    U->>SEO: clica 'Crie conta grátis'
    SEO->>API: POST {cta='trial-signup', source='/licitacoes/limpeza'}
    API-->>SEO: 204
    API->>DB: INSERT cta_tracking(cta, source, user_agent, ip_hash, ts)
    SEO->>U: redirect /signup?from=licitacoes-limpeza
```

## SEN-FE-001 cache alignment fix

```mermaid
flowchart TD
    OLD[ANTIPATTERN: export const revalidate = 3600 + fetch cache:'no-store'] --> X[SSG quebra: 4146 fetches build-time]
    X --> XX[backend saturação Stage 2 outage 2026-04-27]
    NEW[FIX: export const revalidate = 3600 + fetch next:{revalidate:3600}] --> OK[ISR funcional]
    OK --> OK1[build estático bem-formed]
    OK1 --> OK2[regen on-demand 1h]
```
