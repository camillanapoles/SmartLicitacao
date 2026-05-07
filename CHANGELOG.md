# Changelog

All notable changes to SmartLic will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Frontend / Legal
- **Página de termos do Plano Fundadores (#793)** — `frontend/app/termos/fundadores/page.tsx` criado com 9 seções legais cobrindo escopo vitalício, fair use, sem garantia de êxito, período de resfriamento (CDC art. 49) e disclaimer de parceria governamental. `frontend/app/termos/page.tsx` atualizado com link para `/termos/fundadores`. Protege juridicamente o SmartLic e informa fundadores sobre os exatos direitos adquiridos.

### Added — Frontend / Intel Reports
- **Intel Reports frontend layer: CTA + checkout + polling + download (#632)** — Adiciona camada frontend completa para Intel Reports (one-time purchase): `IntelReportCTA` "use client" component em `/cnpj/[cnpj]` (parent Server Component com ISR); 4 API proxy routes (`/api/intel-reports/checkout`, `/api/intel-reports/`, `/api/intel-reports/[purchaseId]`, `/api/intel-reports/[purchaseId]/download`); página de sucesso pós-Stripe com polling até 120s (40×3s, `useRef` anti-stale-closure); página de cancelamento. Proxy routes usam factory `createProxyRoute` para rotas simples e padrão manual `getRefreshedToken` + `sanitizeProxyError` para rotas dinâmicas. PDF streaming com `Content-Disposition: attachment`. 6 testes unitários (CTA behavior, 401→signup redirect, checkout_url redirect, Mixpanel events, loading state). Rollback: remover seção #632 de `page.tsx` e deletar arquivos novos.

### Added — Docs / Partners
- **ADR de política do programa de parceiros (#597)** — `docs/adr/partner-program.md` formaliza a política canônica: comissão 20% lifetime, pagamento mensal via Pix no dia 5, atribuição last-click 30 dias, onboarding exige CPF/CNPJ. Default `revenue_share_pct` em `CreatePartnerRequest`, `create_partner()` e `create_partner_referral()` alinhado de 25% para 20%. Valores explícitos em parceiros existentes não são alterados. Snapshot OpenAPI e testes atualizados. Rollback: reverter PR #743.

### Added — Backend / Intel Reports
- **Entrega de Intel Reports via ARQ job (#631)** — `generate_intel_report(ctx, purchase_id)` ARQ job implementado: busca purchase/profile, gera PDFs de Raio-X do concorrente, faz upload para bucket Supabase Storage `intel-reports`, cria signed URLs 30 dias, marca purchase como `ready`, e envia email transacional Resend via novo template `intel_report_ready.html`. Tratamento de falhas com retry/backoff ARQ, status `failed`, refund Stripe automático e email de notificação de falha. Prometheus: `smartlic_intel_report_generated_total{product_type,status}`. Mixpanel: `intel_report_generated`. Job registrado em `WorkerSettings` e em `job_queue.py`. Rollback: reverter commit e desabilitar enqueue no webhook Stripe.

### Added — Tests
- **Edge case tests para keyword density pipeline — TD-BE-023 (#249)** — 71 testes cobrindo `normalize_text`, `match_keywords`, `validate_terms`, `_strip_org_context`, `has_red_flags`, `has_sector_red_flags`, `check_proximity_context` e `check_co_occurrence` para inputs que aparecem em dados reais do PNCP: strings vazias, whitespace-only, strings muito longas (10k tokens), caracteres especiais, Unicode/acentuado português, RTL (árabe), emojis, texto numérico, null bytes e scripts mistos. Nenhuma alteração no código de produção necessária — funções já tratam esses inputs defensivamente. Rollback: reverter commit.
- **Cobertura do módulo health.py — TD-TEST-004 (#202)** — 26 testes unitários cobrindo `HealthStatus` enum, `SourceHealthResult.to_dict()`, `SystemHealth.to_dict()`, `initialize_health_tracking()` / `get_uptime_seconds()`, `check_source_health()` (ConnectError + exceção genérica), `get_health_status()` (integração com mock de rede) e `get_system_health()` (Redis down, circuit breaker degradado). `health.py` (1100+ linhas) tinha cobertura zero antes desta PR.

### Fixed — Backend / Tech Debt
- **Validação de duplicatas de keywords por normalização em sectors_data.yaml (TD-BE-015 #210)** — `_validate_sector_keywords()` e `_check_list_for_duplicates()` adicionados a `backend/sectors.py`. Detecta keywords que colapsam para a mesma forma após `normalize_text()` (ex: "café" e "cafe"). Log de warnings apenas — nunca levanta exceção, nunca bloqueia startup. Checa `keywords`, `exclusions` e `context_required_keywords` por setor. 20 novos testes. Rollback: reverter commit.

### Fixed — Frontend / Accessibility
- **Associação programática de mensagens de erro a inputs via aria-describedby (TD-FE-022 #272)** — `aria-describedby` apontando para IDs únicos nas mensagens de erro adicionado em `SignupForm`, `OnboardingStep2`, `ValueRangeSelector`, `conta-fields` (SelectField + NumberField) e `perfil/page`. `aria-invalid` togula em função do estado de erro. Grupos UF ganham `role="group"` + `aria-labelledby`. Screen readers anunciam erros quando o input recebe foco. Somente atributos aditivos — sem mudança comportamental. Rollback: reverter commit.
- **Atributos aria-label em botões de seleção de UF (TD-UX-001 #194, TD-UX-003 #196)** — `aria-label` dinâmico (`"Selecionar {estado}"` / `"Remover {estado}"`) adicionado aos botões de toggle de UF em `SearchCustomizePanel`. Screen readers agora anunciam o nome completo do estado em vez de soletrar a sigla. Complementa `aria-pressed` já existente. Atributos ARIA do `SavedSearchesDropdown`, `RegionSelector` e focus-trap/autoFocus/Escape do modal Save Search foram implementados em commits anteriores (TD-005 Dialog, WCAG 2.2 AAA). Rollback: reverter commit.

### Added — Frontend / GTM
- **Social proof de volume na landing e /planos (#627)** — `StatsClientIsland.tsx` ganhou linha de métricas de volume estática ("+2 milhões contratos · 27 estados · R$1k–R$500M+") abaixo dos contadores animados existentes. `StatsSection.tsx` espelha a linha no fallback noscript/SSR para SEO. `/planos` ganhou trust strip compacto acima do toggle de billing period. Dados factualmente ancorados no DataLake (`pncp_supplier_contracts` ~2M rows, `pncp_raw_bids` 27 UFs). Rollback: reverter commit `86b20bb00`.
- **Intel Reports: CTA + checkout + polling + download (#632)** — `IntelReportCTA.tsx` client component em `/cnpj/[cnpj]` page (Server Component ISR). Proxies Next.js: `GET /api/intel-reports/` (lista), `POST /api/intel-reports/checkout`, `GET /api/intel-reports/[purchaseId]` (status), `GET /api/intel-reports/[purchaseId]/download` (PDF). Página de sucesso `/intel-reports/[sessionId]` com polling 3s × 40 iterações (120s max). Página de cancelamento `/intel-reports/cancelado`. Unauthenticated click → redirect `/signup?intent=intel_report`.
- **CTA de trial em /observatorio (#619)** — `ObservatorioCTA` client component adicionado ao hub do observatório. Usuários não autenticados veem link `/signup?ref=observatorio-hub`; autenticados veem link `/buscar`. Empty-state de relatórios agora inclui link ativo para `/licitacoes`.

### Added — Backend / Health
- **Check de conectividade OpenAI com cache 5min (TD-BE-025 #214)** — `check_openai_health()` em `health.py` usa `models.list(limit=1)` (sem tokens) para probar reachability da API. Cache em memória 300s evita overhead de quota. Integrado em `get_system_health()`: OpenAI degraded → status do sistema `degraded` (não unhealthy). Retorna `{status, latency_ms, cached}`. Tests em `test_health_openai.py` (4 cenários: ok, degraded, not_configured, cache).

### Fixed — Backend / Security
- **Limite de intervalo de datas PNCP (#206)** — `BuscaRequest` agora rejeita payloads com `data_final - data_inicial > 30 dias` em nível de schema (antes de qualquer chamada downstream). Retorna HTTP 400 com `error_code=date_range_exceeded` e mensagem descritiva em português. Campo `_MAX_DATE_RANGE_DAYS: ClassVar[int] = 30` + `ClassVar` typing em `_VALOR_MAX_CEILING`. Handler `_validation_error_messages()` em `exception_handlers.py` extrai mensagens sem vazar input bruto. OpenAPI snapshot e `api-types.generated.ts` atualizados. 17 testes. Rollback: reverter commit.
- **Rejeição de webhooks Stripe malformados antes do DB (#204)** — `_validate_event_envelope()` valida `event.id` (prefixo `evt_`), `event.type` e `event.data.object` logo após `construct_event()`. Payloads inválidos ou assinaturas forjadas retornam HTTP 400 sem tocar Supabase/idempotency. `_safe_log_value()` sanitiza todos os valores nos logs de webhook (bounded 80 chars, allowlist alnum). Logger rebaixado de `error` para `warning` em erros de validação. Rollback: reverter commit.
- **Validação de termos de busca customizados (#212)** — `BuscaRequest.termos_busca` agora valida com allowlist conservadora pt-BR (letras latinas, dígitos, espaços, vírgulas e hífens). Rejeita payloads com `<`, `;`, `/`, `_` e similares. Limite `max_length=500`. Snapshot OpenAPI atualizado. Rollback: reverter commit.

### Fixed — Backend / Excel
- **Logging estruturado e validação de tipos para geração de Excel (#180 TD-HP-003)** — `_validate_licitacoes_types()` em `excel.py` escaneia valores de dict antes de geração e loga warning para tipos não-serializáveis (observability-only, não raise). `pipeline/stages/generate.py`: `asyncio.to_thread(create_excel)` envolto em try/except; falha na geração define `excel_status='failed'` com log estruturado em vez de exception não tratada. `routes/sessions.py`: `create_excel` na rota de download envolto em try/except com HTTPException 500 acionável. 3 novos testes em `test_excel.py`.

### Added — SEO Admin
- **GSC API sync + dashboard /admin/seo (STORY-SEO-005 #478)** — ARQ cron semanal (dom 06 UTC) sincroniza Google Search Console searchanalytics para `gsc_metrics` (Supabase). Dashboard `/admin/seo` ganhou seção "Query Analytics" com top queries, top pages por CTR e oportunidades CTR <1%. Graceful no-op se `GSC_SERVICE_ACCOUNT_JSON` ausente. Prometheus: `smartlic_gsc_sync_duration_seconds` + `smartlic_gsc_sync_rows_upserted_total`. Migration: `20260422120000_create_gsc_metrics.sql`.

### Fixed — Analytics & Instrumentação
- **CONV-INST-002: correção de shape dos eventos Mixpanel no signup (#606)** — event properties corrigidas para alinhar com spec AC1-AC4: `signup_form_rendered` ganha `rollout_branch`/`has_referral_code`/`source` (remove `fields_count`); `signup_field_blur` renomeia `field_name → field`, `is_filled → has_value`, adiciona `value_length` e `has_validation_error` (exceto campos `password`/`confirmPassword` onde `value_length` é omitido por privacidade LGPD — credential metadata não vai a analytics de terceiros); `signup_field_error` renomeia `field_name → field`, `error_type → error_code`, substitui `btoa()` (encoding reversível, risco PII) por `hashStr()` (hash hex determinístico 8 chars, sem dep externa); `signup_form_abandoned` substitui `fields_filled: number` por `fields_touched: string[]` + `has_errors: boolean`. **Breaking change Mixpanel:** queries salvas em `field_name`/`is_filled`/`fields_filled` devem ser atualizadas para os novos nomes.

### Added — Analytics & Instrumentação
- **Clarity trial+onboarding tagging + first-analysis Mixpanel lifecycle (CONV-INST-005 #572)** — `claritySet('onboarding_step', 'N/3')` nos 3 steps do onboarding; `clarityEvent('trial_started')` + `claritySet('trial_started_at')` pós first-analysis 2xx; eventos Mixpanel `first_analysis_completed/empty/failed` no SSE handler com guard `useRef` anti-double-fire e `viability_high_count` (score ≥ 0.7); `claritySet('trial_days_remaining')` no `AnalyticsProvider` com null-skip para admins.
- **CONV-INST-005 story execution: cnae+ufs context em first-analysis redirect + hashErrorMessage refactor (#608)** — onboarding redirect para `/buscar` inclui `cnae` e `ufs` como query params, passados via `autoAnalysisContext` até o SSE handler para enriquecer payload de `first_analysis_empty`; `hashErrorMessage` extraído para função top-level (elimina duplicação); `first_analysis_failed` usa `search_id` do evento SSE quando disponível. Story file CONV-INST-005 recriado com registro de execução completo.

### Fixed — SEO
- **HTTP 410 Gone para rota raiz órfã `/contratos/orgao` (#612)** — middleware retorna 410 exato para `/contratos/orgao` sem afetar a rota dinâmica `/contratos/orgao/[cnpj]`. Discovery spike documenta análise do export GSC local (44 hits eram CNPJs com artefatos de scrape, não a raiz). Regressão coberta por `contratos-orgao-root-gone.test.ts` e `sitemap-coverage.test.ts`.
- **Redirects 301 para setores legados `/blog/licitacoes` (#613)** — `frontend/lib/legacy-licitacoes-redirects.js` mapeia 7 IDs de setores legados (underscore/renomeados) para slugs canônicos: `materiais_hidraulicos`, `engenharia_rodoviaria`, `manutencao_predial`, `software_desenvolvimento`, `software_licencas`, `medicamentos`, `frota_veicular`. Integrado em `next.config.js` como redirects 301 com UF regex (27 UFs). Não cria catch-all nem redireciona para homepage. 3 testes Jest determinísticos. Rollback: reverter PR ou remover mapeamentos específicos.
- **Sitemap dedup: remover sitemap-blog.xml legado + cobrir /blog/programmatic/{setor}/{uf} no shard id:1 (#661)** — removida rota legada `/sitemap-blog.xml` (103 linhas) que duplicava shards id:1/id:3; adicionados 540 combos (20 setores × 27 UFs) ao shard id:1 via `generateSectorUfParams()`.
- **Meta descriptions CTR (#641)** — 5 páginas GSC P0 (>200 impressões, CTR <1%) reescritas com copy data-driven: número real + benefício + CTA implícito, 120–155 chars. Afeta `/blog/pncp-guia-completo-empresas`, `/blog/licitacoes-engenharia-2026`, `/blog/como-consultar-contratos-publicos-pncp`, `/blog/subcontratacao-licitacoes-regras-lei-14133`, `/perguntas/prazo-publicacao-edital`.

### Added — SEO
- **Landing `/ferramentas/pncp-licitacoes` — queries B2B tool-search (#653)** — Server Component, ISR 24h, sem fetch backend. Captura queries GSC pos 11-17 sem clique ("pncp licitações", "pncp contratos", "consultar contratos pncp"): tabela comparativa Manual (PNCP web) × SmartLic (9 dimensões), how-to 4 passos, CTA trial 14 dias. JSON-LD Article + BreadcrumbList. Links internos de `/licitacoes/[setor]` e `/observatorio`. Registrada em sitemap (case 0, priority 0.8, monthly).
- **`app/robots.ts` dynamic route handler (SEO-PROG-007)** — substitui `public/robots.txt` estático por handler env-aware (Next.js 16 Metadata API). Production: Allow `/` + Disallow paths privados (path-exact trailing-slash para evitar prefix-match RFC 9309 §2.2.2). Preview/staging: block-all. AC6: `/alertas/` path-exact desbloqueia 464 páginas GSC previamente bloqueadas.
- Google-Extended explícito em `Allow: /` para SGE/AI Overviews eligibility.
- Block de 7 AI crawlers (GPTBot, ClaudeBot, Bytespider etc.) para evitar scraping de dados de treinamento.
- `SITEMAP_USE_INDEX_VARIANT` flag — `index` (default, `sitemap_index.xml`) ou `legacy` (rollback para `sitemap.xml`).
- `frontend/scripts/audit-robots-coverage.ts` — script CI que verifica 0 URLs SEO bloqueadas por Disallow.
- 40 unit tests + Playwright E2E coverage (gated em `PREVIEW_BASE_URL`).

---

## [0.5.4] - 2026-04-18 - CACHE WARMING DEPRECATION

### Removed — BREAKING
- **Cache warming proativo (Layer 3 jobs)** — startup warmup + cron 4h + coverage check removidos. DataLake Supabase (~50K bids + 2M+ contratos) é fonte primária com latência <100ms; pré-população de `search_results_cache` virou overhead puro. STORY-CIG-BE-cache-warming-deprecate.
- **Feature flags removidas (env vars):** `WARMUP_ENABLED`, `CACHE_WARMING_ENABLED`, `CACHE_REFRESH_ENABLED`, `CACHE_WARMING_POST_DEPLOY_ENABLED` + constantes associadas (`WARMUP_*`, `WARMING_*`, `CACHE_REFRESH_*`, `CACHE_WARMING_POST_DEPLOY_*`). Setar essas vars em Railway agora é no-op.
- **Módulos deletados:** `backend/jobs/cron/cache_ops.py` (duplicado de `cron/cache.py` herdado do DEBT-v3-S3), `backend/jobs/cron/cache_cleanup.py` (shim), `backend/jobs/cache_jobs.py` (shim).
- **Funções removidas:** `cache_warming_job`, `cache_refresh_job`, `warmup_specific_combinations`, `warmup_top_params`, `ensure_minimum_cache_coverage`, `start_warmup_task`, `start_coverage_check_task`, `_get_prioritized_ufs`, `_get_cache_entry_age`, `get_stale_entries_for_refresh`, `get_top_popular_params`, `get_popular_ufs_from_sessions`, `_warming_wait_for_idle`.
- **Métricas Prometheus deletadas:** `smartlic_cache_refresh_total`, `smartlic_cache_refresh_duration_seconds`, `smartlic_warming_combinations_total`, `smartlic_warming_pauses_total`, `smartlic_warmup_coverage_ratio`, `smartlic_cache_coverage_deficit`.
- **Testes deletados** (~40 testes): `test_cache_warming_noninterference.py`, `test_cache_refresh.py`, `test_crit055_warmup_adaptive.py`, `test_cache_global_warmup.py`, `test_cache_refresh_enabled.py`, `test_ensure_minimum_coverage.py`.
- **Stories marcadas Superseded:** GTM-STAB-007, CRIT-081, CRIT-055, GTM-ARCH-002.

### Preserved
- Cache passivo por-request (L1 InMemoryCache + L2 Redis + `search_results_cache` Supabase).
- SWR reativo em `cache/swr.py::trigger_background_revalidation` — serve stale + revalida em background quando request toca entrada 6-24h.
- `cron/cache.py::start_cache_cleanup_task` — L3 local file cache cleanup a cada 6h continua.
- Migration `20260308330000_debt009_ban_cache_warmer.sql` — conta `system-cache-warmer@internal.smartlic.tech` permanece banida.
- Constante `WARMING_USER_ID` (nil UUID) — mantida como guard defensivo em `cache/manager.py` (STORY-271 / DEBT-009).

---

## [0.5.3] - 2026-04-09 - CONTRACTS BACKFILL + SEO EXPANSION

### Added — Ingestão de Contratos
- **Backfill resiliente de contratos** — checkpoint/resume + circuit breaker check + adaptive delay
- **Cron de contratos diário** — migrado de semanal para diário para backfill contínuo
- **`contracts_incremental_job`** — registrado no worker ARQ com otimizações de resiliência

### Added — SEO Content
- **Wave 3.3** — 10 artigos sobre contratos públicos (+10 blog pages)
- **Wave 2.3 + 3.1 + 3.2** — `/contratos/orgao`, pillar pages, daily digest (+2045 páginas)

---

## [0.5.2] - 2026-02-27 - RELIABILITY SPRINT COMPLETE

### Added — Reliability Architecture
- **Async search 202 Accepted pattern** (STORY-292) — non-blocking search with polling
- **Redis state externalization** (STORY-294) — multi-worker state sharing
- **Progressive results delivery** (STORY-295) — meta-search with incremental updates
- **Bulkhead per source** (STORY-296) — concurrency + timeout isolation per data source
- **SSE Last-Event-ID resumption** (STORY-297) — reconnect without data loss
- **Unified error UX** (STORY-298) — SearchStateManager for consistent error handling
- **SLOs + alerting dashboard** (STORY-299) — admin SLO monitoring with alerts
- **Email alert system** (STORY-301) — CRUD alerts, cron execution, dedup, unsubscribe

### Changed — Security & Observability
- **Security hardening** (STORY-300) — CSP headers, error sanitization, LGPD compliance
- **Supabase circuit breaker** (STORY-291) — eliminates database SPOF
- **Event loop unblock** (STORY-290) — offload sync Supabase calls to thread pool
- **CI/CD pipeline fix** (STORY-293) — restore green builds

### Changed — Pricing & Billing
- **Repricing** (STORY-277) — R$1.999/mes → R$397/mes (mensal), R$357 (semestral), R$317 (anual)
- **Trial duration** — 7 days → 30 days → 14 days (STORY-319: shorter trial converts better)
- **Boleto + PIX** (STORY-280) — additional payment methods via Stripe
