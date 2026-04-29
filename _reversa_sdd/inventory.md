# Inventário Inicial — SmartLic

> Gerado pelo **Reversa Scout** em 2026-04-27
> Fonte: `.reversa/context/surface.json`

## 1. Identidade do Projeto

| Campo | Valor |
|-------|-------|
| Nome | **SmartLic** |
| Vendor | CONFENGE Avaliações e Inteligência Artificial LTDA |
| URL | https://smartlic.tech |
| Estágio | POC avançado (v0.5) — beta com trials, pre-revenue |
| Domínio | Inteligência em licitações públicas (B2G) |

## 2. Linguagens

| Linguagem | Arquivos | Papel |
|-----------|----------|-------|
| Python | 1.036 | Backend FastAPI + jobs + ingestion |
| TypeScript (`.ts/.tsx`) | 1.173 | Frontend Next.js + types |
| JavaScript | 866 | Tooling, scripts, squads, configs |
| SQL | 230 | Migrations Supabase + RPCs |
| YAML | 1.299 | CI/CD, squads AIOX, configs setores |
| Markdown | 3.130 | Docs (docs/, stories, runbooks) |
| JSON | 215 | Manifests, configs, generated types |
| Shell | 43 | start.sh, deploy scripts |
| TOML | 19 | pyproject, railway, ruff |

**Linguagens primárias:** Python (backend) + TypeScript (frontend).

## 3. Frameworks Principais

### Backend (Python 3.12)
- **FastAPI 0.136.0** + Pydantic 2.12.5 + uvicorn 0.41.0 (RUNNER padrão) / gunicorn 23.0.0 (opt-in)
- **httpx 0.28.1** — clientes PNCP, PCP v2, ComprasGov v3
- **OpenAI SDK 1.109.1** — GPT-4.1-nano (classificação + resumos)
- **Supabase 2.28.0** — auth, Postgres 17, RLS
- **Redis 5.3.1** + **arq >=0.26** — cache, circuit breaker, fila assíncrona
- **Stripe 11.4.1** + **Resend 2.x** — billing + email transacional
- **sentry-sdk[fastapi] 2.52.0** + **OpenTelemetry 1.25** + **prometheus_client** — observabilidade
- **openpyxl 3.1.5** + **reportlab 4.4.0** — geração Excel/PDF
- **Google API Client 2.190.0** — OAuth + Sheets export

### Frontend (Next.js 16 + React 18)
- **Next.js 16.1.6** (output `standalone`, App Router) + **React 18.3.1** + **TypeScript 5.9.3**
- **Tailwind CSS 3.4.19** + **framer-motion 12.38.0** + **Recharts 3.7.0**
- **@supabase/ssr 0.8.0** + **@stripe/react-stripe-js 6.2.0** + **@sentry/nextjs 10.49.0**
- **@dnd-kit/core 6.3.1** — drag-and-drop pipeline kanban
- **SWR 2.4.1** + **react-hook-form 7.73.1** + **zod 4.3.6**
- **mixpanel-browser 2.74.0** — product analytics

### Tooling
- Jest 29.7.0 + Playwright 1.58.2 + Storybook 8.6.18 + Lighthouse CI 0.15.0 + Chromatic
- openapi-typescript 7.13.0 — gera `frontend/app/api-types.generated.ts` a partir do schema OpenAPI

## 4. Pontos de Entrada

| Tipo | Caminho | Papel |
|------|---------|-------|
| Backend FastAPI | `backend/main.py` | `app = create_app()` (factory em `startup/app_factory.py`) |
| Backend dispatcher | `backend/start.sh` | `PROCESS_TYPE=web` (uvicorn/gunicorn) ou `=worker` (ARQ) |
| Backend worker | `backend/job_queue.py` | ARQ `WorkerSettings` |
| Frontend root | `frontend/app/layout.tsx` | Next.js App Router root layout |
| Frontend middleware | `frontend/middleware.ts` | Auth + security headers |
| Frontend config | `frontend/next.config.js` | Standalone output + Sentry wrapper |
| Landing | `frontend/app/page.tsx` | Marketing/SEO |

## 5. Configuração e Infra

- `.env.example` (exaustivo — LLM, Supabase, Redis, Stripe, Resend, Sentry, Mixpanel, OAuth)
- `docker-compose.yml` — desenvolvimento local (backend + frontend stub)
- `railway.toml` (root) + `backend/railway.toml` + `backend/railway-worker.toml` + `frontend` (via dashboard)
- `vercel.json` (legado/não usado — deploy é Railway)
- `.pre-commit-config.yaml`
- `.mcp.json` — MCPs habilitados (Playwright, EXA, Context7, Apify, Railway, Canva, Gmail/GCal/GDrive, Notion)

### Deploy
- **Railway monorepo** com 3 services: `bidiq-backend` (web), worker (PROCESS_TYPE=worker), `bidiq-frontend`
- Auto-deploy via push `main` → GitHub Actions (`deploy.yml`) → migrations push automático

## 6. CI/CD (35 workflows)

**Backend:** `backend-ci.yml`, `backend-tests.yml`, `backend-tests-external.yml`, `contract-tests.yml`, `dep-scan.yml`, `mutation-testing.yml`
**Frontend:** `frontend-tests.yml`, `chromatic.yml`, `lighthouse.yml`, `e2e.yml`
**API contract:** `api-types-check.yml` (OpenAPI drift gate)
**Database:** `migration-check.yml`, `migration-gate.yml`, `migration-validate.yml`, `db-backup.yml`
**Deploy:** `deploy.yml`
**Quality:** `codeql.yml`, `editorial-lint.yml`, `pr-validation.yml`
**Operação:** `cleanup.yml`, `dependabot-auto-merge.yml`, `handle-new-user-guard.yml`
**Carga/SEO:** `k6-load-test.yml`, `load-test.yml`, `indexnow.yml`
**Ingestão:** `ingest-licitaja.yml`, `data-parity-nightly.yml`, `integration-external.yml`, `billing-check.yml`

## 7. Banco de Dados

- **PostgreSQL 17 (Supabase Cloud)** — Auth + RLS + extensions inferidas: `pg_trgm`, `pg_cron`, `tsvector` (FTS pt-BR)
- **Migrations primárias:** `supabase/migrations/` — **183 arquivos** `.sql` (inclui `.down.sql` pareados pós STORY-6.2)
- **Migrations legadas:** `backend/migrations/` — 11 arquivos (audit trail apenas)
- Tabelas-chave inferidas de CLAUDE.md: `pncp_raw_bids` (~50K rows + 400d retenção), `supplier_contracts` (~2M+ rows), `search_results_cache`, `search_sessions`, `profiles`, `plan_billing_periods`, `ingestion_checkpoints`, `ingestion_runs`, `cron_job_health`

> Análise detalhada será feita pelo **reversa-data-master** na Fase 2.

## 8. Cobertura de Testes

| Suite | Framework | Arquivos |
|-------|-----------|----------|
| Backend unit/integration | pytest (timeout 30s, thread method) | 467 |
| Frontend unit | Jest + RTL + jest-axe | 376 |
| E2E | Playwright (60+ flows) | 41 |
| Storybook | Storybook 8 + Chromatic | (componentes) |
| Load | k6 + Locust | (configs em `.github/workflows/load-test.yml` + `tests/load/`) |
| Mutation | (workflow `mutation-testing.yml`) | — |

CLAUDE.md afirma: **5.131+ backend passing / 0 failures** + **2.681+ frontend passing / 0 failures**.

## 9. Integrações Externas

| Categoria | Integração |
|-----------|------------|
| Dados públicos | PNCP, PCP v2 (Portal de Compras Públicas), ComprasGov v3 |
| LLM | OpenAI (GPT-4.1-nano) |
| Auth/DB/Storage | Supabase Cloud |
| Cache/Queue | Redis (Upstash ou Railway) |
| Billing | Stripe |
| Email | Resend |
| Observabilidade | Sentry (org `confenge`, projects `smartlic-backend` + `smartlic-frontend`), Mixpanel, OpenTelemetry, Prometheus |
| Marketing/SEO | Google Search Console, IndexNow, next-sitemap, Lighthouse CI |
| Hosting | Railway (web + worker + frontend) |
| OAuth | Google (Sheets export) |

## 10. Ecossistema de Frameworks de Agentes

O repositório contém múltiplos frameworks de orquestração de IA convivendo (não fazem parte do produto, mas afetam o footprint):
- **AIOX** (`.aiox-core/`) — squads, agents, tasks, workflows
- **AIOS legacy** (`.aios-core/`) — versão anterior
- **Reversa** (`.claude/skills/reversa*`, `.agents/skills/reversa*`) — engenharia reversa (este framework)
- **Synapse** (`.synapse/`) — métricas, lessons learned
- **Squads** (`squads/`) — 21+ squads especializados (aiox-apex, aiox-seo, prod-hotfix, etc.)

## 11. Módulos Identificados (alto nível)

`search`, `ingestion`, `datalake`, `filter`, `llm-arbiter`, `viability`, `consolidation`, `pipeline-kanban`, `billing`, `auth`, `quota`, `cache`, `jobs`, `webhooks`, `routes`, `schemas`, `contracts`, `services`, `source-config`, `templates-email`, `messages`, `feedback`, `onboarding`, `analytics`, `admin`, `exports-excel-sheets-pdf`, `observatory`, `seo-programmatic`, `design-system`, `tests`, `migrations`

A Fase 2 (Escavação) terá uma tarefa de Archaeologist por módulo principal — `.reversa/plan.md` será atualizado.

## 12. Métricas Brutas

| Métrica | Valor |
|---------|-------|
| Total de arquivos indexados (excl. caches) | ~8.128 |
| Workflows de CI | 35 |
| Frontend routes (App Router top-level) | 56 |
| Backend route modules | 19 |
| Backend endpoints (inferido CLAUDE.md) | 49 |
| Migrations Supabase | 183 |
| Sectores B2G configurados | 15 (`backend/sectors_data.yaml`) |
