# ROADMAP — SmartLic

**Versao:** 6.0 | **Atualizado:** 2026-05-31 | **Status:** Intel Reports 87.5%, Reposicionamento 100%, Q2 Multi-Camada em execucao

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
INTEL REPORTS:       [################....] ~87.5% (7/8 issues, 1 open blocker)
UX PREMIUM:          [....................] 0% (issues nao criados — spec em docs/stories/)
Q2 MULTI-CAMADA:     [#####...............] ~25% (5 EPICs, ~50 issues, execucao ativa)
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

10 issues CTA/copy (#619–#627, #651, #652). CTAs inline programmatic pages, TrialCountdown copy, social proof, meta descriptions GSC. Milestone #3 fechado (12 issues total).

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

5 EPICs lanciados 2026-05-16 a 2026-05-31. ~50 issues. Foco: camada de inteligencia B2G profunda alem da busca.

### EPIC-SUBINTEL — Inteligencia de Cadeia de Fornecimento (#1224)

| Issue | Título | Status |
|-------|--------|--------|
| #1224 | EPIC-SUBINTEL — Inteligência de Cadeia de Fornecimento / Subcontratação | Open |
| #1225 | SUBINTEL-002 — RPC subcontract_regional_dependency | Closed |
| #1226 | SUBINTEL-002 — RPC subcontract_regional_dependency | Closed |
| #1227 | SUBINTEL-003 — RPC supplier_growth_anomaly (Wave 0) | Open |
| #1228 | SUBINTEL-010 — Radar de Subcontratação: score + página + narrativa LLM | Open |
| #1229 | SUBINTEL-011 — Score de Oportunidade de Parceria em /fornecedores/[cnpj] | Open |
| #1230 | SUBINTEL-012 — Índice de Dependência Regional: heatmap visual (Wave 1) | Open |
| #1231 | SUBINTEL-020 — Rede de fornecedores recorrentes por órgão (Wave 2) | Open |
| #1232 | SUBINTEL-021 — Matching B2B entre fornecedores opt-in LGPD (Wave 2) | Open |
| #1233 | SUBINTEL-022 — Potenciais subcontratações por edital aberto: bloco aditivo | Open |
| #1235 | SUBINTEL-031 — Novo tier premium "SmartLic Insight" (empacotamento) | Open |

### EPIC-PREDINT — Inteligencia Preditiva de Demanda Governamental (#1260)

| Issue | Título | Status |
|-------|--------|--------|
| #1260 | EPIC-PREDINT — Inteligência Preditiva de Demanda Governamental | Open |
| #1264 | PREDINT-001 — RPC predict_opportunity_window | Closed |
| #1265 | PREDINT-002 — RPC predict_budget_cycle | Closed |
| #1266 | PREDINT-003 — RPC predict_seasonal_calendar | Open |
| #1267 | PREDINT-004 — RPC predict_incumbent_decay | Open |
| #1268 | PREDINT-005 — RPC predict_expansion_organs | Open |
| #1269 | PREDINT-010 — Radar de Recorrência Governamental (página flagship) | Open |
| #1270 | PREDINT-011 — Heatmap Nacional de Oportunidades Futuras | Open |
| #1271 | PREDINT-012 — Calendário Sazonal Interativo (grid UF × setor × mês) | Open |

### EPIC-COMPINT — Inteligencia Concorrencial Profunda (#1261)

| Issue | Título | Status |
|-------|--------|--------|
| #1261 | EPIC-COMPINT — Inteligência Concorrencial Profunda (OSINT B2G) | Open |
| #1272 | COMPINT-001 — RPC competitor_territory_map | Closed |
| #1273 | COMPINT-002 — RPC competitor_win_metrics | Closed |
| #1274 | COMPINT-003 — RPC competitor_shadow_network | Open |
| #1275 | COMPINT-010 — Mapa de Território Competitivo (página flagship) | Open |
| #1276 | COMPINT-011 — Seção 'Inteligência Concorrencial' em /fornecedores/[cnpj] | Open |

### EPIC-NETINT — Camada de Rede / Inteligencia Coletiva B2G (#1263)

| Issue | Título | Status |
|-------|--------|--------|
| #1263 | EPIC-NETINT — Camada de Rede / Inteligência Coletiva B2G | Open |
| #1283 | NETINT-001 — Schema network_events_agg + mecanismo de coleta anonimizada | Open |
| #1284 | NETINT-002 — RPC network_intel_snapshot | Closed |
| #1285 | NETINT-003 — RPC network_orgao_patterns | Open |
| #1286 | NETINT-004 — RPC network_discount_trends | Closed |
| #1287 | NETINT-010 — Feed de Inteligência Coletiva (bloco aditivo na dashboard) | Open |
| #1288 | NETINT-011 — Bloco 'Padrões de Mercado' em páginas de setor (pSEO aditivo) | Open |

### EPIC-B2GOPS — Sistema Operacional B2G (#1262)

| Issue | Título | Status |
|-------|--------|--------|
| #1262 | EPIC-B2GOPS — Sistema Operacional B2G (Terminal do Operador) | Open |
| #1277 | B2GOPS-001 — Schema workspace_watchlists + RPCs | Open |
| #1278 | B2GOPS-002 — Schema workspace_documents + RPCs de gestão documental | Open |
| #1279 | B2GOPS-003 — Schema workspace_timeline + RPCs de timeline operacional | Open |
| #1280 | B2GOPS-010 — Workspace Colaborativo (página flagship /workspace) | Open |
| #1281 | B2GOPS-011 — Alertas Inteligentes (watchlist + contratos + timeline) | Open |
| #1282 | B2GOPS-012 — Centro de Guerra de Pregão (/workspace/centro-guerra/[id]) | Open |
| #1294 | B2GOPS-004 — Schema workspace_war_rooms + RPCs + SSE channel | Open |

### CONV — Conversao pSEO (#1310–#1323)

14 issues criados 2026-05-31. Foco: otimizacao de conversao em paginas programaticas.

| Issue | Título | Prioridade |
|-------|--------|-----------|
| #1310 | CONV-001: pSEO — Caixa de valor agressiva acima da dobra | P0 |
| #1311 | CONV-002: Landing pages transacionais — Fornecedor/CNPJ/Órgão/Contrato | P0 |
| #1312 | CONV-003: Captura contextual — Blog/Perguntas/Glossário com simulador | P0 |
| #1313 | CONV-004: 'Aha moment' pré-cadastro — Insight grátis | P0 |
| #1314 | CONV-005: Monetização de entrada — Microtransações (relatórios avulsos) | P0 |
| #1315 | CONV-006b: Rollout SERP — Reescrever títulos/metadescriptions 74 páginas | P0 |
| #1316 | CONV-007: Trilhas por intenção — 4 clusters de busca | P0 |
| #1317 | CONV-008a: Subcontratação como categoria central — Páginas flagship | P0 |
| #1318 | CONV-009: Instrumentar conversão — Scroll/CTA/Checkout/Abandono | P0 |
| #1319 | CONV-010: Landing pages autônomas — Cada página = proposta comercial | P0 |
| #1320 | CONV-006a: Quick Win SERP — Reescrever 4 piores páginas (deploy 24h) | P0 |
| #1321 | CONV-008b: Subcontratação — Blocos aditivos em páginas existentes | P1 |
| #1322 | CONV-011: Sequência de pós-compra — Email transacional + upsell 0h/48h/7d | P0 |
| #1323 | CONV-012: Infraestrutura de A/B testing para páginas pSEO | P1 |

### REPO — Extensoes pos-Phase 0

| Issue | Título | Status |
|-------|--------|--------|
| #1289 | REPO-COMMS — Overhaul de Copy/Homepage (posicionamento 'vantagem competitiva') | Open |
| #1290 | REPO-TIER-COMMAND — Novo tier premium 'SmartLic Command' (R$970/mês) | Open |

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

---

*Ultima atualizacao: 2026-05-31*
