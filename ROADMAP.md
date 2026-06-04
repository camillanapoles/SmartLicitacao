# ROADMAP — SmartLic

**Versao:** 6.2 | **Atualizado:** 2026-06-04 | **Status:** Intel Reports 87.5%, Reposicionamento 100%, Q2 Multi-Camada 61.2%, Wave 4 0%

## 2026-04-24 — EPIC-GROWTH-VIRAL-2026-Q3: On-Page CAC-Zero

21 stories novas organizadas em 6 waves (142 SP, 4 sprints). Objetivo: K-factor B2B ≥0.20, 30% signups via viral loops, -40% CAC em 6 meses. Inspiração Manus (waitlist + replay), Lovable (gallery + remix), ChatGPT (share), Loom/Calendly (todo output é anúncio). Adaptações B2G com pseudonimização default + opt-in LGPD.

- **Wave 0 Infra (GV-001):** A/B testing framework + funnel auto-tracking (BLOCKER)
- **Wave 1 Viral Loops (GV-002-005):** watermark + pseudonimização, analysis replay, embed widget, propose-to-colleague
- **Wave 2 Scarcity (GV-006-008):** early-access waitlist, trending gallery, live impact ticker
- **Wave 3 Habit (GV-009-012):** daily matching, badges+certificate LinkedIn, weekly wins digest, post-win celebration
- **Wave 4 Collaboration (GV-013-015):** team invites tiered, consultoria→cliente read-only, concorrente alert
- **Wave 5 Monetization (GV-016-018):** usage milestone ROI variant, exit-intent modal, referral tiered+social widget
- **Wave 6 Content (GV-019-021):** sectorial benchmarking, ROI calculator embed, churn winback campaign

Epic master: `docs/stories/2026-04/EPIC-GROWTH-VIRAL-2026-Q3.md`. Estende STORY-289/312/432/449 sem duplicar. Milestone #4 criado. Issues ainda nao criados — status: Draft.

---

## 2026-04 — Cache Warming Deprecation (DataLake é a fonte)

Decisão arquitetural baseada no novo modelo de dados: Supabase agora armazena ~50K licitações abertas (`pncp_raw_bids`) + 2M+ contratos históricos (`supplier_contracts`, estratégia 100% orgânica de inbound via SEO). Consultas vão ao DB com latência <100ms.

- **Layer 3 cache warming proativo removido** — jobs startup/cron/coverage-check deletados (`cron/cache.py` reduzido a cleanup; `jobs/cron/cache_ops.py` deletado; `cache_warming_job` + `cache_refresh_job` removidos).
- **Feature flags deletadas:** `WARMUP_ENABLED`, `CACHE_WARMING_ENABLED`, `CACHE_REFRESH_ENABLED`, `CACHE_WARMING_POST_DEPLOY_ENABLED` + constantes `WARMING_*`, `CACHE_REFRESH_*`, `WARMUP_*`.
- **Funções admin removidas:** `get_stale_entries_for_refresh`, `get_top_popular_params`, `get_popular_ufs_from_sessions` (consumidas apenas pelos jobs).
- **Cache passivo permanece:** `search_results_cache` (Supabase 24h) + Redis L2 + InMemory L1 + SWR por-request em `cache/swr.py::trigger_background_revalidation`.
- **Stories substituídas (Superseded):** GTM-STAB-007, CRIT-081, CRIT-055, GTM-ARCH-002 marcadas como Superseded.
- **STORY-CIG-BE-cache-warming-deprecate** (branch `fix/cig-be-wave2-tier1-plus-tier2`) — deleta 6 arquivos de teste (~40 testes obsoletos), remove código, atualiza docs.
- **Migration `20260308330000_debt009_ban_cache_warmer.sql` mantida** — conta banida permanece (agora por razão ainda mais forte: não existe mais).


---

## Status Atual

```
POC CORE:            [####################] 100% DEPLOYED
GTM LAUNCH:          [####################] 100% (10/10 stories)
GTM FIXES:           [####################] 100% (37 fixes)
GTM RESILIENCE:      [####################] 100% (25/25 stories)
RELIABILITY SPRINT:  [####################] 100% (13/13 stories, 4 sprints)
REPOSICIONAMENTO B2G:[####################] 100% (23/23 issues — milestone fechado)
FOUNDERS PLAN:       [####################] 100% (23 issues — #782–#795, #861–#872)
TECH DEBT (TD):      [####################] 100% (61/61 issues fechadas)
INTEL REPORTS:       [################....] 87.5% (7/8 issues, 1 open blocker)
UX PREMIUM:          [....................] 0% (issues nao criados — spec em docs/stories/)
Q2 MULTI-CAMADA:     [############........] 61.2% (5 EPICs + CONV + Verticais, 85 issues, 52 closed, 33 open)
Q2 WAVE 4 (JUN):     [....................] 0% (54 issues novas — #1400–#1453)
```

**Production:** https://smartlic.tech

---

## Fases Concluidas

### Fase 1 — POC Core (Jan 2026)
PNCP client, filtering engine, Excel export, LLM summaries, Next.js frontend. Deployed Jan 28.

### Fase 2 — Multi-Sector + GTM Launch (Feb 1-14)
15 sectors, Stripe billing, onboarding wizard, trial conversion, SSE progress, PCP integration, pipeline management. 10 GTM stories + 37 production fixes.

### Fase 3 — GTM Resilience (Feb 17-20)
25 stories across 6 tracks. See `docs/gtm-resilience-summary.md` for details.

| Track | Stories | Key Deliverables |
|-------|---------|------------------|
| A — Never Empty | 5 | Fallback cascade, partial results, coverage bar |
| B — Smart Cache | 6 | Two-level cache, SWR, hot/warm/cold priority, admin dashboard |
| C — Coverage UX | 3 | Confidence indicator, freshness, reliability badges |
| D — Classification | 5 | Zero-match LLM, viability assessment, feedback loop |
| E — Observability | 3 | Structured logging, Prometheus metrics, Sentry |
| F — Infrastructure | 3 | ARQ job queue, OpenTelemetry tracing, schema validation |

### Fase 4 — Reliability Sprint (Feb 22-27)
13 stories across 4 sprints. Architecture hardening for multi-worker production.

| Sprint | Stories | Key Deliverables |
|--------|---------|------------------|
| Sprint 0 — Make It Work | STORY-283, 290, 291, 292, 293 | Event loop unblock, Supabase circuit breaker, async search 202 pattern, CI fix |
| Sprint 1 — Make It Reliable | STORY-294, 295, 296, 297, 298 | Redis state externalization, progressive results, bulkhead per source, SSE resumption, unified error UX |
| Sprint 2 — Make It Observable | STORY-299, 300 | SLOs + alerting dashboard, security hardening (CSP, LGPD) |
| Sprint 3 — Make It Competitive | STORY-301, 302 | Email alert system (CRUD, cron, dedup), documentation cleanup |

### Fase 4.1 — GTM Repricing (Feb 25-26)
Market-validated pricing realignment.

| Story | Title | Status |
|-------|-------|--------|
| STORY-277 | Repricing R$1.999 → R$397/mes | Completed |
| STORY-280 | Boleto + PIX via Stripe | Completed |
| STORY-284 | GTM Quick Wins | Completed |

### Fase 4.2 — Reposicionamento B2G Phase 0 (Mai 2026) — 100% Concluido

23 de 23 issues fechadas (milestone #5 fechado). Reposicionamento completo do produto para B2G, novas páginas e disclaimers legais.

| Série | Entregáveis |
|-------|-------------|
| REPO-001–005 | Labels GitHub, doc copywriting guidelines, audit disclaimers legais, lead_capture estendido, fix CNPJ footer |
| REPO-006–012 | Hero homepage reescrito, REPO-007 disclaimer servidor público, bloco 3 níveis, /consultoria-b2g, /navbar dropdown, footer colunas, componente DiagnosticForm |
| REPO-013–018 | ViabilityVerdict plug pSEO, CTA contextual 4 rotas, REPO-015, title/meta GSC-driven, Mixpanel eventos padronizados, Rename PNCP→nossas fontes |
| REPO-019–022 | Mixpanel funnel, remover copy garantia ganho, Disclaimer recomendação algorítmica, Gate decision doc 14d |

Milestone: `Reposicionamento B2G Phase 0` (#5) — 23/23 fechado. #775 (INDEX) fechado em 2026-05-13.

### Fase 4.3 — pSEO Health Sprint (Mai 2026) — Concluido

10 issues P0 qualidade de sinal Google (#656–#665). BreadcrumbList JSON-LD, DISTINCT queries, og:image dinâmica, sitemap freshness, robots.ts fix, sameAs bug fix. Milestone #2 fechado (12 issues total).

### Fase 4.4 — On-Page CTA & Copy Sprint (Mai 2026) — Concluido

10 issues CTA/copy (#619–#621, #623–#627, #651, #652). CTAs inline programmatic pages, TrialCountdown copy, social proof, meta descriptions GSC. Milestone #3 fechado (12 issues total). Nota: #622 nao existe — range original com gap.

### Fase 4.5 — Conversão + Instrumentação (Mai 2026) — Concluido

CONV-INST-001–005: Mixpanel page-load, signup lifecycle events, email confirmation, CNPJ deep-link onboarding, MS Clarity trial tagging. SEC-HMAC-001: HMAC verify webhook. SEC-SECDEF-001/002: SECURITY DEFINER audit + CI guard. Todas as issues fechadas (#606, #607, #608, #697, #698, #714, #854, #855, #901, #902).

### Fase 5 — Founders Plan (Mai 2026) — Concluido

Plano Fundadores vitalício R$997 one-time. 23 issues implementados em 2 dias.

| Entregável | Issues |
|-----------|--------|
| Backend: pivot checkout one-time, webhook entitlement, session-status endpoint | #782, #783, #785, #861, #862, #863, #865 |
| DB: campos founder em profiles, feature flag FOUNDERS_OFFER_ENABLED | #784, #794 |
| Frontend: /fundadores page, banner global, CTAs pSEO, /pricing comparação, /obrigado dual-state | #786, #787, #788, #789, #792, #864, #870, #872 |
| Tracking: founders_* events Mixpanel | #790 |
| Email: welcome founders template | #791, #868 |
| Legal: /termos/fundadores, founders-policy.md | #793, #795 |
| Copy: headline pain-focused, FAQ objeções reais, features benefit-driven | #867 |

---

## Backlog Ativo

### Intel Reports Epic (87.5% — 1 blocker open)

Milestone: `Intel Reports Epic` (#1) — open:1, closed:7.

| Story | Título | Status |
|-------|--------|--------|
| #628 | Migration + RPC cnpj_supplier_intel | Closed |
| #629 | PDF Generator + LLM narrative Raio-X | Closed |
| #630 | Stripe checkout + webhook fulfillment | Closed |
| #631 | ARQ background job + Storage delivery | Closed |
| #632 | Frontend CTA + checkout flow + polling | Closed |
| #826 | RPC sector_uf_intel (INTEL-REPORT-002) | Closed |
| #634 | EPIC: One-Time Data Products — Raio-X + Mapa Setorial | Closed |
| #633 | Mapa de Oportunidade Setorial (R47) | **OPEN — BLOCKER** |

### Technical Debt (TD — 100% concluido)

61 TD issues (#178–#238). Todas fechadas. 0 abertas.

| Sprint | Stories | Focus |
|--------|---------|-------|
| Sprint 0 | TD-HP-001 a TD-HP-012 | Hot path (LLM fallback, Excel buffer, PNCP parsing, race conditions) |
| Sprint 1 | TD-GTM-001 a TD-GTM-004 | GTM infra (Supabase singleton, rate limiter, plan capabilities, security) |
| Sprint 2 | TD-UX-001 a TD-UX-004 | Accessibility (ARIA labels, keyboard nav, focus, color contrast) |
| Sprint 3 | TD-CODE-001, TD-TEST-001 a TD-TEST-005 | Test coverage + god component split |
| Sprint 4 | TD-BE-002 a TD-BE-025 | Backend (SQL injection, validation, error handling, health checks) |
| Sprint 5 | TD-FE-002 a TD-FE-031 | Frontend (state mgmt, re-renders, code splitting, form validation, API interceptors) |
| Sprint 6 | TD-OPS-001 a TD-OPS-014 | DevOps (CI coverage, deploy pipeline, health checks, load tests) |
| Sprint 7 | TD-TEST-012 a TD-TEST-028 | Testing (async concurrency, E2E scenarios, accessibility, security, error recovery) |

### UX Premium (UX-301 to UX-335) — Spec pendente

Source: `docs/stories/EPIC-UX-PREMIUM-2026-02.md` (35 problems from production audit). Issues ainda nao criados no tracker.

| Priority | Stories | Examples |
|----------|---------|----------|
| P0 Critical | UX-301, UX-302, UX-304 | Timeout, progress, filter issues |
| P1 High | UX-305 to UX-318 | Landing, navigation, validation, confirmations |
| P2 Medium | UX-319 to UX-331 | Heartbeat, dark mode, skeletons, keyboard nav |
| P3 Low | UX-332 to UX-335 | Sound feedback, SEO, accessibility |

### Growth Viral Epic Q3 (GV-001 to GV-021) — Draft

Source: `docs/stories/2026-04/EPIC-GROWTH-VIRAL-2026-Q3.md`

| Sprint | Stories | Foco | SP |
|--------|---------|------|----|
| 1 | GV-001, 002, 005, 018 | Infra + viral loops base + referral UI | 26 |
| 2 | GV-003, 006, 009, 012, 013, 017, 021 | Replay + waitlist + daily + winback | 42 |
| 3 | GV-004, 007, 010, 014, 016 | Embed + trending + badges + consultoria | 45 |
| 4 | GV-008, 011, 015, 019, 020 | Ticker + wins digest + concorrente + content | 29 |

Status: todas Draft — Milestone criado (#4), issues a criar.

---

## Q2 2026 — Inteligencia Multi-Camada (em execucao)

5 EPICs lançados 2026-05-16 a 2026-06-02 + CONV + Verticais Premium. 85 issues (52 closed, 33 open). Foco: camada de inteligência B2G profunda além da busca. Progresso real: 61.2% concluído (recálculo audit 2026-06-04 — 110 estava inflado).

### EPIC-SUBINTEL — Inteligencia de Cadeia de Fornecimento (#1224)

| Issue | Título | Status |
|-------|--------|--------|
| #1224 | EPIC-SUBINTEL — Inteligência de Cadeia de Fornecimento / Subcontratação | Open |
| #1225 | SUBINTEL-002 — RPC subcontract_regional_dependency | Closed |
| #1226 | SUBINTEL-002 — RPC subcontract_regional_dependency | Closed |
| #1227 | SUBINTEL-003 — RPC supplier_growth_anomaly (Wave 0) | Closed |
| #1228 | SUBINTEL-010 — Radar de Subcontratação: score + página + narrativa LLM | Closed |
| #1229 | SUBINTEL-011 — Score de Oportunidade de Parceria em /fornecedores/[cnpj] | Open |
| #1230 | SUBINTEL-012 — Índice de Dependência Regional: heatmap visual (Wave 1) | Open |
| #1231 | SUBINTEL-020 — Rede de fornecedores recorrentes por órgão (Wave 2) | Open |
| #1232 | SUBINTEL-021 — Matching B2B entre fornecedores opt-in LGPD (Wave 2) | Open |
| #1233 | SUBINTEL-022 — Potenciais subcontratações por edital aberto: bloco aditivo | Open |
| #1235 | SUBINTEL-031 — Novo tier premium "SmartLic Insight" (empacotamento) | Open |
| #1234 | SUBINTEL-030 — Capability allow_subcontract_intel + feature flag (Wave 3) | Closed |

### EPIC-PREDINT — Inteligencia Preditiva de Demanda Governamental (#1260)

| Issue | Título | Status |
|-------|--------|--------|
| #1260 | EPIC-PREDINT — Inteligência Preditiva de Demanda Governamental | Open |
| #1264 | PREDINT-001 — RPC predict_opportunity_window | Closed |
| #1265 | PREDINT-002 — RPC predict_budget_cycle | Closed |
| #1266 | PREDINT-003 — RPC predict_seasonal_calendar | Closed |
| #1267 | PREDINT-004 — RPC predict_incumbent_decay | Closed |
| #1268 | PREDINT-005 — RPC predict_expansion_organs | Closed |
| #1269 | PREDINT-010 — Radar de Recorrência Governamental (página flagship) | Open |
| #1270 | PREDINT-011 — Heatmap Nacional de Oportunidades Futuras | Open |
| #1271 | PREDINT-012 — Calendário Sazonal Interativo (grid UF × setor × mês) | Open |
| #1291 | PREDINT-000 — Capability allow_predictive_intel + feature flag | Closed |

### EPIC-COMPINT — Inteligencia Concorrencial Profunda (#1261)

| Issue | Título | Status |
|-------|--------|--------|
| #1261 | EPIC-COMPINT — Inteligência Concorrencial Profunda (OSINT B2G) | Open |
| #1272 | COMPINT-001 — RPC competitor_territory_map | Closed |
| #1273 | COMPINT-002 — RPC competitor_win_metrics | Closed |
| #1274 | COMPINT-003 — RPC competitor_shadow_network | Closed |
| #1275 | COMPINT-010 — Mapa de Território Competitivo (página flagship) | Open |
| #1276 | COMPINT-011 — Seção 'Inteligência Concorrencial' em /fornecedores/[cnpj] | Open |
| #1292 | COMPINT-000 — Capability allow_competitive_intel + feature flag | Closed |

### EPIC-NETINT — Camada de Rede / Inteligencia Coletiva B2G (#1263)

| Issue | Título | Status |
|-------|--------|--------|
| #1263 | EPIC-NETINT — Camada de Rede / Inteligência Coletiva B2G | Open |
| #1283 | NETINT-001 — Schema network_events_agg + mecanismo de coleta anonimizada | Closed |
| #1284 | NETINT-002 — RPC network_intel_snapshot | Closed |
| #1285 | NETINT-003 — RPC network_orgao_patterns | Closed |
| #1286 | NETINT-004 — RPC network_discount_trends | Closed |
| #1287 | NETINT-010 — Feed de Inteligência Coletiva (bloco aditivo na dashboard) | Open |
| #1288 | NETINT-011 — Bloco 'Padrões de Mercado' em páginas de setor (pSEO aditivo) | Closed |

### EPIC-B2GOPS — Sistema Operacional B2G (#1262)

| Issue | Título | Status |
|-------|--------|--------|
| #1262 | EPIC-B2GOPS — Sistema Operacional B2G (Terminal do Operador) | Open |
| #1277 | B2GOPS-001 — Schema workspace_watchlists + RPCs | Closed |
| #1278 | B2GOPS-002 — Schema workspace_documents + RPCs de gestão documental | Closed |
| #1279 | B2GOPS-003 — Schema workspace_timeline + RPCs de timeline operacional | Closed |
| #1280 | B2GOPS-010 — Workspace Colaborativo (página flagship /workspace) | Open |
| #1281 | B2GOPS-011 — Alertas Inteligentes (watchlist + contratos + timeline) | Open |
| #1282 | B2GOPS-012 — Centro de Guerra de Pregão (/workspace/centro-guerra/[id]) | Open |
| #1294 | B2GOPS-004 — Schema workspace_war_rooms + RPCs + SSE channel | Closed |
| #1293 | B2GOPS-000 — Capability allow_workspace_basic + feature flag | Closed |

### CONV — Conversao pSEO (39 issues — 13 open, 26 closed)

14 issues originais (#1310–#1323) criados 2026-05-31 + 25 sub-issues expandidos 2026-06-01 a 2026-06-02. Foco: otimizacao de conversao em paginas programaticas.

**Wave 1 — Core (14 issues originais #1310–#1323)**

| Issue | Título | Prioridade | Status |
|-------|--------|-----------|--------|
| #1310 | CONV-001: pSEO — Caixa de valor agressiva acima da dobra | P0 | Closed |
| #1311 | CONV-002: Landing pages transacionais — Fornecedor/CNPJ/Órgão/Contrato | P0 | Closed |
| #1312 | CONV-003: Captura contextual — Blog/Perguntas/Glossário com simulador | P0 | Open |
| #1313 | CONV-004: 'Aha moment' pré-cadastro — Insight grátis | P0 | Closed |
| #1314 | CONV-005: Monetização de entrada — Microtransações (relatórios avulsos) | P0 | Open |
| #1315 | CONV-006b: Rollout SERP — Reescrever títulos/metadescriptions 74 páginas | P0 | Closed |
| #1316 | CONV-007: Trilhas por intenção — 4 clusters de busca | P0 | Open |
| #1317 | CONV-008a: Subcontratação como categoria central — Páginas flagship | P0 | Open |
| #1318 | CONV-009: Instrumentar conversão — Scroll/CTA/Checkout/Abandono | P0 | Closed |
| #1319 | CONV-010: Landing pages autônomas — Cada página = proposta comercial | P0 | Open |
| #1320 | CONV-006a: Quick Win SERP — Reescrever 4 piores páginas (deploy 24h) | P0 | Closed |
| #1321 | CONV-008b: Subcontratação — Blocos aditivos em páginas existentes | P1 | Open |
| #1322 | CONV-011: Sequência de pós-compra — Email transacional + upsell 0h/48h/7d | P0 | Open |
| #1323 | CONV-012: Infraestrutura de A/B testing para páginas pSEO | P1 | Closed |

**Wave 1b — Novas issues (2026-06-01 a 2026-06-02)**

| Issue | Título | Prioridade | Status |
|-------|--------|-----------|--------|
| #1324 | CONV-013: Botão WhatsApp direto com founder — captura por canal Brasil | P1 | Closed |
| #1325 | CONV-009b: Wirear instrumentação pSEO nas páginas reais | P0 | Closed |
| #1327 | CONV-002b: Wirear PSEOTemplate + PreviewCTA nas 5 entity pages | P0 | Closed |
| #1328 | CONV-014: Liberar sistema de alertas — remover feature flag | P0 | Closed |
| #1329 | CONV-015: Landing pages de caso de uso — hubs conectando intenção a dados | P1 | Closed |
| #1330 | CONV-016: Sinais de urgência em páginas pSEO | P1 | Closed |
| #1332 | CONV-017: Interlinking journeys programático | P1 | Closed |
| #1333 | CONV-018: Segmento do usuário no primeiro contato | P1 | Closed |

**Wave 2 — Microtransações (CONV-005b, #1326, #1334–#1337)**

| Issue | Título | Status |
|-------|--------|--------|
| #1334 | CONV-005b-1: Schema digital_products + migration + seed | Closed |
| #1335 | CONV-005b-2: Endpoint POST /api/checkout/one-time genérico | Closed |
| #1326 | CONV-005b: Checkout modular para microtransações | Open |
| #1336 | CONV-005b-3: Preview configurável + componente checkout frontend | Open |
| #1337 | CONV-005b-4: ARQ job delivery + página obrigado pós-compra | Open |

**Wave 3 — Pós-compra (CONV-011b, #1331, #1338–#1340)**

| Issue | Título | Status |
|-------|--------|--------|
| #1338 | CONV-011b-1: Schema post_purchase_sequences + webhook | Closed |
| #1331 | CONV-011b: Sequência de pós-compra — email + upsell 0h/48h/7d | Open |
| #1339 | CONV-011b-2: 3 templates email (delivery, followup, reengagement) | Closed |
| #1340 | CONV-011b-3: ARQ jobs post_purchase_sequence + tracking Mixpanel | Closed |

**Verticais Premium (2026-06-02)**

| Issue | Título | Status |
|-------|--------|--------|
| #1373 | P0: Ativar 4 feature flags premium — verticais já codificados | Closed |
| #1374 | P0: White-Label — modelo de inexigibilidade + landing page institucional | Closed |
| #1375 | P0: Ativar B2G_OPS_ENABLED — Pipeline Premium add-on R$0/mês | Closed |
| #1376 | P0: Ativar SUBCONTRACT_INTEL_ENABLED — Supplier Intelligence add-on | Closed |
| #1377 | P0: Ativar COMPETITIVE_INTEL_ENABLED — Competitive Intelligence add-on | Closed |
| #1378 | P0: Ativar PREDICTIVE_INTEL_ENABLED — Predictive Intelligence add-on | Closed |
| #1372 | P0: Datalake API Self-Service — monetização imediata via API REST | Open |

### REPO — Extensoes pos-Phase 0

| Issue | Título | Status |
|-------|--------|--------|
| #1289 | REPO-COMMS — Overhaul de Copy/Homepage (posicionamento 'vantagem competitiva') | Closed |
| #1290 | REPO-TIER-COMMAND — Novo tier premium 'SmartLic Command' (R$970/mês) | Open |

### Q2 Wave 4 — Core Features (Jun 2026) — 54 issues novas

Lançados 2026-06-04. Nenhum closed ainda — todos Open. Foco: retenção, revenue visibility, API self-service, UX repositioning, feedback loop.

**DIGEST — Motor de Retenção Semanal (#1410–#1413, #1421)**

| Issue | Título | Status |
|-------|--------|--------|
| #1410 | DIGEST-001: Migration + config — coluna frequency, cron pg_cron, flag DIGEST_ENABLED | Open |
| #1411 | DIGEST-002: Lógica de build do digest — query por setor, top N por tier, fallback | Open |
| #1412 | DIGEST-003: Template HTML + integração Resend — viability badges, CTA, List-Unsubscribe | Open |
| #1413 | DIGEST-004: Endpoint de preferências — PATCH /conta/preferencias para frequency toggle | Open |
| #1421 | DIGEST-005: Métricas + Mixpanel — digest_sent/opened/clicked/unsubscribe | Open |

**FOUNDER — Revenue Dashboard (#1414–#1417, #1422)**

| Issue | Título | Status |
|-------|--------|--------|
| #1414 | FOUNDER-001: SQL queries — MRR, churn 30d, trial-to-paid 30d/90d, D7 retention, ARPA | Open |
| #1415 | FOUNDER-002: Cron diário + cache Redis — computar métricas, invalidar a cada 1h | Open |
| #1416 | FOUNDER-003: Endpoint GET /admin/metrics/revenue — JSON, p95 <500ms | Open |
| #1417 | FOUNDER-004: Frontend /admin/metrics — cards numéricos + gráfico de coortes (Recharts) | Open |
| #1422 | FOUNDER-005: Mixpanel founder_metrics_viewed + permission check admin-only | Open |

**API-SELF — Datalake API Self-Service (#1418–#1425, estende #1372)**

| Issue | Título | Status |
|-------|--------|--------|
| #1372 | P0: Datalake API Self-Service — monetização imediata via API REST | Open |
| #1418 | API-SELF-001: Migration api_keys + modelo Pydantic + rotas CRUD | Open |
| #1419 | API-SELF-002: Middleware require_api_key + rota GET /v1/api/search | Open |
| #1420 | API-SELF-003: Rate limiting por API key via Redis token bucket (respeita tier) | Open |
| #1423 | API-SELF-004: Stripe — 3 products/prices + webhook + metered billing cron | Open |
| #1424 | API-SELF-005: Landing page /api + Swagger UI público + pricing cards | Open |
| #1425 | API-SELF-006: Dashboard de uso no /conta — consumo/mês, gráfico, checkout | Open |

**LIFECYCLE — User Lifecycle State Machine (#1426–#1429, estende #1408)**

| Issue | Título | Status |
|-------|--------|--------|
| #1408 | feat: Implement User Lifecycle State Machine + Login Tracking | Open |
| #1426 | LIFECYCLE-001: Migration — profiles.last_login_at, login_count, tabela login_activity | Open |
| #1427 | LIFECYCLE-002: Auth middleware — atualizar last_login_at + login_activity (Redis write-behind) | Open |
| #1428 | LIFECYCLE-003: SQL function compute_user_lifecycle() + endpoint GET /admin/users/segments | Open |
| #1429 | LIFECYCLE-004: Admin dashboard — lifecycle states, transições/semana, power users, Mixpanel | Open |

**VIAB-UX — Viability Score UX Repositioning (#1430–#1434, #1452–#1453, estende #1405)**

| Issue | Título | Status |
|-------|--------|--------|
| #1405 | feat: Reposition Viability Score as Central UX Element | Open |
| #1430 | VIAB-UX-001: Mudar default sort para confianca — backend schema + frontend SearchForm | Open |
| #1431 | VIAB-UX-002: ViabilityBadge inline em cada linha da listagem principal | Open |
| #1432 | VIAB-UX-003: Tooltip com breakdown dos 4 fatores — Modalidade, Prazo, Valor, Geografia | Open |
| #1433 | VIAB-UX-004: Seção 'Por que esta oportunidade?' — expandable section no card | Open |
| #1434 | VIAB-UX-005: A/B test — feature flag VIABILITY_DEFAULT_SORT + métricas de comparação | Open |
| #1452 | VIAB-UX-005a: Feature flag VIABILITY_DEFAULT_SORT + split 50/50 via hash user_id | Open |
| #1453 | VIAB-UX-005b: Admin dashboard de A/B test — metricas comparativas + significancia estatistica | Open |

**FEEDBACK — Feedback Loop + Sector Affinity (#1435–#1439, estende #1406)**

| Issue | Título | Status |
|-------|--------|--------|
| #1406 | feat: Close the Feedback Loop — Learn from User Behavior | Open |
| #1435 | FEEDBACK-001: Migration user_sector_affinity — tabela + RLS + seed inicial | Open |
| #1436 | FEEDBACK-002: Atualizar affinity no feedback — correct +0.1, false_positive -0.2 por setor | Open |
| #1437 | FEEDBACK-003: Combined score adjustment — fator de afinidade no enrich pipeline | Open |
| #1438 | FEEDBACK-004: Endpoint GET /profile/sector-affinity — transparência de afinidades | Open |
| #1439 | FEEDBACK-005: Frontend — 'Setores que não me interessam' + mute/unmute na /conta/preferencias | Open |

**NO-JARGON — Replace Technical Jargon (#1440–#1443, estende #1407)**

| Issue | Título | Status |
|-------|--------|--------|
| #1407 | fix: Replace Technical Jargon in Customer-Facing UX | Open |
| #1440 | NO-JARGON-001: Substituir 'Cache' → 'Dados recentes' nos 6 componentes de busca | Open |
| #1441 | NO-JARGON-002: Substituir 'GPT-4', 'LLM', 'quota' em componentes visíveis | Open |
| #1442 | NO-JARGON-003: Blog — substituir 'datalake' por 'base de dados' em 15+ artigos | Open |
| #1443 | NO-JARGON-004: Atualizar BANNED_PHRASES + extender validação para blog e search components | Open |

**ENTITY — Entity Tracking (#1444–#1447, estende #1409)**

| Issue | Título | Status |
|-------|--------|--------|
| #1409 | feat: Enable "Follow Organ/Competitor" Entity Tracking | Open |
| #1444 | ENTITY-001: Migration — adicionar tracked_orgaos e tracked_fornecedores ao schema de alertas | Open |
| #1445 | ENTITY-002: Alert matcher — cruzar novos bids com CNPJ dos órgãos/fornecedores trackeados | Open |
| #1446 | ENTITY-003: Frontend — botão 'Seguir' nas páginas de órgão e CNPJ | Open |
| #1447 | ENTITY-004: Limite de entidades por plano + upgrade prompt | Open |

**TIER-COMMAND — SmartLic Command Tier (#1448–#1451, estende #1290)**

| Issue | Título | Status |
|-------|--------|--------|
| #1448 | TIER-COMMAND-001: PlanCapabilities + TierConfig — novo tier 'command' no quota_core.py | Open |
| #1449 | TIER-COMMAND-002: Stripe — novo product/price + webhook handlers | Open |
| #1450 | TIER-COMMAND-003: Feature flags por capability — gate de acesso às funcionalidades Command | Open |
| #1451 | TIER-COMMAND-004: Página de checkout + landing page do tier Command | Open |

**CONV-SUB — CONV Sub-Issues (#1400–#1402)**

| Issue | Título | Status |
|-------|--------|--------|
| #1400 | CONV-003-1: Simulador de Oportunidades — widget interativo para Blog/SEO | Open |
| #1401 | CONV-007-1: 4 landing pages de intenção (comercial/investigativa/jurídica/subcontratação) | Open |
| #1402 | CONV-010-1: Template "Proposta Comercial" — bloco aditivo em entity pages | Open |

**CORE-FEAT — Core Features Avulsas (#1403, #1404)**

| Issue | Título | Status |
|-------|--------|--------|
| #1403 | feat: Founder Revenue Dashboard — MRR, Churn, Activation, Retention | Open |
| #1404 | feat: Activate Daily/Weekly Digest Email — Motor de Retenção Semanal | Open |

---

## Archived Documentation

Obsolete stories and docs moved to `docs/archive/` (Feb 20, 2026):
- `completed/gtm-resilience/` — 25 GTM-RESILIENCE stories
- `completed/gtm-fixes/` — GTM-FIX production fixes
- `completed/gtm-core/` — GTM-003 to GTM-010
- `completed/features/` — STORY-165 to STORY-185
- `completed/ux/` — UX-303, UX-336
- `superseded/` — STORY-156-164, STORY-200-229 (replaced by TD series)
- Sprint, session, review, ceremony, and investigation artifacts

---

## Historico

| Data | Evento |
|------|--------|
| 2026-01-24 | Project initialized |
| 2026-01-25 | MVP v0.1 complete |
| 2026-01-28 | Production deployment v0.2 |
| 2026-02-03 | Multi-sector expansion v0.3 |
| 2026-02-14 | GTM launch phase v0.4 |
| 2026-02-17 | GTM production fixes (37 fixes) |
| 2026-02-20 | GTM Resilience complete v0.5 (25 stories) |
| 2026-02-20 | Documentation cleanup (180+ files archived) |
| 2026-02-22 | Reliability Sprint started (13 stories, 4 sprints) |
| 2026-02-25 | GTM Repricing — R$1.999 → R$397 (STORY-277) |
| 2026-02-26 | Boleto + PIX payment methods (STORY-280) |
| 2026-02-27 | Reliability Sprint complete v0.5.2 (13/13 stories) |
| 2026-05-03 | pSEO Health Sprint complete (10/10 issues, milestone fechado) |
| 2026-05-04 | On-Page CTA & Copy Sprint complete (10/10 issues, milestone fechado) |
| 2026-05-05 | Conversão + Instrumentação completo (CONV-INST, SEC-HMAC, SEC-SECDEF) |
| 2026-05-07 | Reposicionamento B2G Phase 0 — 96% (22/23 REPO issues) |
| 2026-05-08 | Founders Plan live — R$997 one-time, 23 issues shipped em 2 dias |
| 2026-05-08 | ROADMAP v5.1 — sync com tracker (397 issues, velocity ~25/dia) |
| 2026-05-13 | Reposicionamento B2G Phase 0 — 100% (#775 INDEX fechado, milestone completo) |
| 2026-05-16 | EPIC-SUBINTEL lancado — Inteligencia de Cadeia de Fornecimento (12 issues) |
| 2026-05-30 | EPICs PREDINT, COMPINT, B2GOPS, NETINT lancados (~35 issues) |
| 2026-05-31 | CONV-001 a CONV-012 lancados — Conversao pSEO (14 issues) |
| 2026-05-31 | ROADMAP v6.0 — sync completo com tracker (577 issues, 50 open, 527 closed) |
| 2026-06-01 | Q2 Multi-Camada: +13 RPCs closed (PREDINT, COMPINT, NETINT, B2GOPS) |
| 2026-06-02 | Q2 Multi-Camada: +6 RPCs closed + 4 feature flags premium ativados |
| 2026-06-02 | CONV Wave 2-3 expandido: Microtransações + Pós-compra (11 novas issues) |
| 2026-06-02 | Verticais Premium: 6 feature flags ativados + Datalake API Self-Service |
| 2026-06-03 | ROADMAP v6.1 — audit sync: 601 issues (565 closed, 36 open), Q2 69.1% |
| 2026-06-04 | ROADMAP v6.2 — audit sync: 655 issues (567 closed, 88 open). Fix #1339/#1340 states, +4 capabilities, +54 Wave 4 issues. Q2 recalculado: 61.2% (85 issues, não 110) |

---

*Ultima atualizacao: 2026-06-04*
