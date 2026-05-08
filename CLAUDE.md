# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SmartLic** — Plataforma de inteligencia em licitacoes publicas que automatiza a descoberta, analise e qualificacao de oportunidades para empresas B2G (Business-to-Government). Produto da **CONFENGE Avaliacoes e Inteligencia Artificial LTDA**.

**Estagio:** Producao v0.5 — beta com trials pagos, pre-revenue (runway-critical).
**URL:** https://smartlic.tech
**Publico-alvo:** Empresas B2G (todos os portes) + Consultorias/Assessorias de licitacao.
**Diferenciais:** IA de classificacao setorial (GPT-4.1-nano) + Analise de viabilidade 4 fatores.

### O que o SmartLic faz

1. **Busca multi-fonte** — Agrega PNCP + PCP v2 + ComprasGov v3 em uma busca consolidada com dedup
2. **Classificacao IA** — LLM arbiter classifica relevancia setorial (keyword + zero-match classification)
3. **Analise de viabilidade** — 4 fatores (modalidade 30%, timeline 25%, valor 25%, geografia 20%)
4. **Pipeline de oportunidades** — Kanban de editais com drag-and-drop
5. **Relatorios** — Excel estilizado + resumo executivo com IA
6. **Historico** — Buscas salvas, sessoes, analytics

### Tech Stack

**Backend:** FastAPI 0.136, Python 3.12, Pydantic 2.12, httpx, OpenAI SDK 1.109 (GPT-4.1-nano), Supabase (PostgreSQL 17 + Auth + RLS), Redis (cache + circuit breaker + SSE state + ARQ queue + rate limiter + distributed locks), ARQ 0.26+ (async job queue), Stripe 11.4 (billing — 12 webhook events), Resend (email — domain `smartlic.tech` verified), Prometheus + OpenTelemetry + Sentry, openpyxl (Excel), ReportLab (PDF), PyYAML

**Frontend:** Next.js 16.1, React 18.3, TypeScript 5.9, Tailwind CSS 3.4 + CSS variables theme tokens (WCAG AA validated), Framer Motion, Recharts, Supabase SSR (auth), Sentry, Mixpanel, @dnd-kit (pipeline kanban — code-split lazy), Shepherd.js (onboarding tour). ~25 core pages + 10k+ programmatic SEO pages (ISR `revalidate=3600`).

**Infra:** Railway (web + worker + frontend), Supabase Cloud, Redis (Upstash/Railway), GitHub Actions (CI/CD)

**Data Sources:**
- PNCP API: `https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao` (priority 1)
- PCP v2 API: `https://compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos` (priority 2, public, no auth)
- ComprasGov v3: `https://dadosabertos.compras.gov.br` (priority 3, dual-endpoint)
- OpenAI API: GPT-4.1-nano para classificacao + resumos

**20 Setores:** Definidos em `backend/sectors_data.yaml` — cada setor tem keywords, exclusoes, context_required_keywords, e viability_value_range.

## Smart Routing — Auto-Invocação de Skills

**REGRA OBRIGATÓRIA:** Quando o usuário envia uma mensagem sem invocar um `/comando` explícito, analise o conteúdo e invoque o skill correspondente via `Skill` tool antes de responder. Use a tabela abaixo como mapa de decisão.

**Pule o roteamento apenas se:**
- O usuário já digitou `/comando` explicitamente
- É conversa casual sem tarefa acionável (agradecimento, pergunta factual simples)
- O usuário disse "responda diretamente" ou equivalente

**NUNCA pule o roteamento por:**
- Continuação implícita de sessão anterior (ex: "sim", "pode fazer", "continue") — **a tarefa ainda precisa ser roteada**
- O agente "já saber" o que fazer pelo contexto — o Skill tool deve ser invocado mesmo assim

### Tabela de Roteamento

| Sinais na mensagem do usuário | Skill a invocar |
|-------------------------------|----------------|
| **Inteligência B2G** | |
| CNPJ + analisar / pesquisar / editais / histórico / oportunidades | `intel-busca` |
| mapear concorrentes / fornecedores / players / quem ganha / market share | `intel-b2g` |
| qualificar leads / scoring / tier / priorizar prospects | `qualify-b2g` |
| cadência / prospecção / sequência de abordagem / follow-up sistemático | `cadencia-b2g` |
| pipeline comercial / funil / forecast / MRR / estágios de venda | `pipeline-b2g` |
| preço / benchmark / valor estimado / quanto custa / margem / P50/P90 | `pricing-b2g` |
| participar edital / go-no-go / dossiê / checklist habilitação / decisão edital | `war-room-b2g` |
| proposta comercial / apresentação / deck / documento de proposta | `proposta-b2g` |
| reter cliente / upsell / churn / health score / renovação | `retention-b2g` |
| monitorar editais / alertas / novos editais do dia / radar | `radar-b2g` |
| relatório executivo / análise profunda CNPJ + editais + mercado | `report-b2g` |
| **Advisory Boards** | |
| copy / texto / mensagem / landing page / email marketing / UX writing | `copymasters` |
| marketing / crescimento / GTM / SEO / conteúdo / CAC / aquisição orgânica | `marketing` |
| cold email / cold outreach / LinkedIn / SDR / abordagem inicial | `outreach` |
| revenue / monetização / pricing / modelo de negócio / unit economics | `turbocash` |
| decisão técnica / arquitetura / trade-off / estratégia produto/tech | `conselho` |
| estratégia empresa / escala / moat / outlier / solo founder / pivot / categoria / obsolescência | `manage` |
| **Desenvolvimento** | |
| bug / erro / quebrou / problema / fix / não funciona | `squad-creator` (args: "bidiq-hotfix") |
| nova feature / implementar / desenvolver / adicionar funcionalidade | `squad-creator` (args: "bidiq-feature-e2e") |
| integrar API / novo cliente / fonte de dados | `squad-creator` (args: "bidiq-api-integration") |
| performance / lento / timeout / otimizar | `squad-creator` (args: "bidiq-performance-audit") |
| próxima issue / o que fazer agora / próximo passo técnico / prioridade | `pick-next-issue` |
| revisar PR / fazer merge / validar PR / governance PR | `review-pr` |
| roadmap / status geral / audit / o que está atrasado / sincronizar | `audit-roadmap` |
| banco de dados / schema / migration / RLS / query / supabase estrutura | `data-engineer` |
| testes / cobertura / QA / suite / validação qualidade | `qa` |
| arquitetura / impacto da mudança / ADR / design sistema | `architect` |
| **Squads aiox (SynkraAI/aiox-squads)** | |
| Lei 14.133 / jurisprudência licitação / impugnação / habilitação edital / acórdão TCU-TCE | `aiox-legal-analyst` |
| componente frontend buscar / SSE / EventSource / Shepherd onboarding / animação buscar-pipeline | `aiox-apex` |
| supplier_contracts / SEO orgânico / blog observatório / sitemap / programmatic SEO | `aiox-seo` |
| pesquisa multi-fonte / deep research / análise setorial B2G / síntese de evidência / PICO | `aiox-deep-research` |
| paralelizar UF/batch/agentes / dispatch agentes / decompor story / wave execução | `aiox-dispatch` |
| memória ecossistema/sessão / aprendizado contínuo / daily sensing / kaizen / Ebbinghaus | `aiox-kaizen-v2` |
| **Meta / Sessão** | |
| beta / usuários reais / feedback / testar com usuário / sessão beta | `beta-team` |
| squad / equipe / time / coordenar agentes / orquestrar | `squad-creator` |
| aios-master / orquestrar tudo / tarefa complexa multi-agente | `aios-master` |
| **Story Lifecycle** | |
| criar story / nova story / story faltante / issue → story / story de bug/incidente | `sm` |
| validar story / story draft review / po review / aprovar story / GO ou NO-GO | `po` |
| **DevOps** | |
| push / subir código / publicar / deploy / enviar para remote / git push | `devops` |

### Exemplos de roteamento automático

- *"preciso analisar o CNPJ 12345 para ver seus editais"* → invoca `intel-busca`
- *"como faço para abordar esse lead?"* → invoca `cadencia-b2g`
- *"qual o preço médio dos contratos de limpeza em SC?"* → invoca `pricing-b2g`
- *"o login está quebrado"* → invoca `squad-creator` com args `bidiq-hotfix`
- *"qual a próxima coisa para fazer no produto?"* → invoca `pick-next-issue`
- *"preciso escrever o email de trial expiring"* → invoca `copymasters`

---

## Behavioral Rules

### NEVER

- Implement without showing options first (always 1, 2, 3 format)
- Delete/remove content without asking first
- Delete anything created in the last 7 days without explicit approval
- Change something that was already working
- Pretend work is done when it isn't
- Process batch without validating one first
- Add features that weren't requested
- Use mock data when real data exists in database
- Explain/justify when receiving criticism (just fix)
- Trust AI/subagent output without verification
- Create from scratch when similar exists in squads/

### ALWAYS

- Present options as "1. X, 2. Y, 3. Z" format
- Use AskUserQuestion tool for clarifications
- Check squads/ and existing components before creating new
- Read COMPLETE schema before proposing database changes
- Investigate root cause when error persists
- Commit before moving to next task
- Create handoff in `docs/sessions/YYYY-MM/` at end of session
- **Use CLI tools (Supabase, Railway, gh) instead of web dashboards when possible**
- **Before writing any `.story.md` file: invoke `Skill(skill: "sm")` first** — mesmo em continuação de sessão
- **Before running any story GO/NO-GO verdict: invoke `Skill(skill: "po")` first**
- **Before any `git push` or `gh pr`: invoke `Skill(skill: "devops")` first**

## Web Search & Industry Validation

**IMPORTANT:** Proactively use web search (WebSearch tool) to validate decisions against industry best practices. This applies to:

### When to Search

- **Before architectural decisions** — Search for current best practices (e.g., "FastAPI circuit breaker pattern 2026", "Next.js SSE best practices")
- **Before adding dependencies** — Verify the package is actively maintained, check for security advisories, compare alternatives
- **When debugging unfamiliar errors** — Search for the specific error message + stack trace patterns
- **Before implementing complex patterns** — Validate approach against industry standards (e.g., "SWR cache invalidation patterns", "Stripe webhook idempotency")
- **When user asks about industry trends** — Search for current state-of-the-art
- **Before database schema changes** — Search for established patterns (e.g., "PostgreSQL RLS best practices", "Supabase migration patterns")
- **When writing prompts for LLMs** — Search for prompt engineering best practices specific to the task

### How to Search Effectively

- Include the current year (2026) in queries for up-to-date results
- Use specific technology names + the pattern being implemented
- Cross-reference at least 2 sources before recommending an approach
- Prefer official docs > well-known blogs > Stack Overflow
- If a searched best practice contradicts this CLAUDE.md, flag it to the user

### When NOT to Search

- For project-specific conventions already documented here
- For trivial changes (typo fixes, variable renames)
- When the user has given explicit, detailed instructions

## CLI Tools Policy

**ALWAYS prefer CLI over web dashboards.** CLIs are faster, scriptable, and keep context in the terminal.

### Supabase CLI

```bash
export SUPABASE_ACCESS_TOKEN=$(grep SUPABASE_ACCESS_TOKEN .env | cut -d '=' -f2)
npx supabase projects list                    # List projects
npx supabase db push                          # Apply migrations
npx supabase db pull                          # Pull remote schema
npx supabase db diff                          # Show schema diff
npx supabase migration new <name>             # Create migration file
npx supabase link --project-ref fqqyovlzdzimiwfofdjk  # Link project
```

### Railway CLI

```bash
# Already authenticated as tiago.sasaki@gmail.com
railway status                                # Current project status
railway logs --tail                           # Stream logs
railway run <command>                         # Run command in Railway env
railway up                                    # Deploy current directory
railway variables                             # List env variables
railway variables set KEY=value               # Set env variable
```

**Railway hard timeout: ~120s** — requests exceeding this are killed by Railway proxy. All backend routes must complete within this limit; use route-level timeout middleware (60s) to return 503 before Railway's 120s proxy kill.

**CRITICAL — Railway Deploy Rules:**
- **NEVER run `railway up` from inside `backend/` or `frontend/`** — always from project root. Running from a subdirectory uploads wrong structure → `Could not find root directory` build failure.
- **Prefer GitHub auto-deploy over `railway up`** — push to `main` triggers deploys automatically with correct monorepo structure.
- **If deploy is stuck SKIPPED:** Commits that don't touch files inside `backend/` or `frontend/` are skipped by Railway watch patterns. To force a rebuild, bump the cache bust in `backend/Dockerfile` (`LABEL build.timestamp` + `ARG CACHEBUST`).
- **`railway up` from root may fail with 413 Payload Too Large** if repo exceeds ~300MB. Use `.railwayignore` to exclude `docs/`, `data/`, `scripts/`, `frontend/` (for backend deploy) or just rely on GitHub auto-deploy.
- **Monorepo config:** `RAILWAY_SERVICE_ROOT_DIRECTORY=backend` (backend), `=frontend` (frontend). Each service has its own `railway.toml` + `Dockerfile`.

### Troubleshooting: Deploy Falha Silenciosamente (CRIT-080)

**PRIMEIRO PASSO:** Verificar GitHub Actions billing **antes de qualquer outra investigação**.

```bash
gh api /repos/{owner}/{repo}/actions/runs --jq '.workflow_runs[:5] | .[] | {status, conclusion, name}'
# Se status="queued" e conclusion=null em múltiplos runs → billing issue
```

- **Sintoma:** Commits em `main` não triggeram deploy; Railway roda versão antiga.
- **Causa:** GitHub Actions com pagamento pendente ou spending limit excedido.
- **Fix:** GitHub Settings > Billing & plans > Actions > resolver pagamento.
- **Deploy de emergência:** `railway redeploy --service bidiq-backend -y` (bypassa Actions).
- **Lição CRIT-080:** `jemalloc LD_PRELOAD` + `Sentry StarletteIntegration` + `cryptography>=46` causam SIGSEGV em POST requests (auth → TLS handshake). GET requests funcionam; POST crasham.

### GitHub CLI

```bash
gh pr list / gh pr create / gh pr view <number>
gh issue list / gh issue create
gh api repos/{owner}/{repo}/...               # Direct API access
```

## Development Commands

### BidIQ Development Squads

```bash
/bidiq                  # Development hub
/bidiq backend          # Squad: team-bidiq-backend (architect, dev, data-engineer, qa)
/bidiq frontend         # Squad: team-bidiq-frontend (ux-design-expert, dev, qa)
/bidiq feature          # Squad: team-bidiq-feature (pm, architect, dev, qa, devops)
```

Resources: `docs/guides/bidiq-development-guide.md`, `.aios-core/development/agent-teams/team-bidiq-*.yaml`

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000            # Dev server

# Tests (IMPORTANT: see Anti-Hang Rules in Testing Strategy)
pytest -k "test_name"               # Specific test (fast, preferred)
pytest tests/test_foo.py            # Single file (safe)
python scripts/run_tests_safe.py    # Full suite — Windows safe (subprocess isolation per file)
python scripts/run_tests_safe.py --parallel 4  # Full suite parallel (4 workers)
pytest --timeout=30                 # Full suite direct (Linux CI — use signal method)
pytest --cov                        # Coverage (threshold: 70%)
pytest tests/integration/           # Integration only
ruff check . && mypy .              # Linting
```

### Frontend

```bash
cd frontend && npm install
npm run dev                         # Dev server at localhost:3000
npm run build && npm start          # Production

# Tests
npm test                            # Run all (must pass 100%)
npm run test:coverage               # Coverage (threshold: 60%)
npm run test:ci                     # CI mode
npm run lint

# E2E (Playwright)
npm run test:e2e                    # Headless
npm run test:e2e:headed             # Debug mode
```

### Pydantic -> TypeScript Type Sync (STORY-2.1 EPIC-TD-2026Q2)

Whenever you change `backend/schemas/*.py` or add/modify `response_model=` on a route, regenerate the frontend types:

```bash
# Terminal 1: run backend locally
cd backend && uvicorn main:app --port 8000

# Terminal 2: regenerate and commit
npm --prefix frontend run generate:api-types
git add frontend/app/api-types.generated.ts
```

- **Source of truth:** `frontend/app/api-types.generated.ts` (auto-generated by `openapi-typescript`, DO NOT edit by hand).
- **Re-export surface:** `frontend/app/types.ts` maps generated schemas to UI-facing names (e.g. `BuscaResult`, `LicitacaoItem`, `Resumo`). Always prefer importing from here; drop down to `components["schemas"]["X"]` only for types that aren't re-exported yet.
- **CI gate:** `.github/workflows/api-types-check.yml` extracts the OpenAPI schema directly from FastAPI (no running backend needed in CI) and fails the PR if the committed generated file drifts from what the backend would produce.
- **Coverage:** every endpoint exposed to the frontend MUST declare `response_model=` on its route decorator so the schema ends up in the OpenAPI output — otherwise CI passes but the frontend stays loosely typed (`{[k: string]: unknown}`).

### Manual Testing (Playwright MCP)

**Production URL:** `https://smartlic.tech`

| Role | Email | Password Source |
|------|-------|----------------|
| Admin | `tiago.sasaki@gmail.com` | env var `SEED_ADMIN_PASSWORD` |
| Master | `marinalvabaron@gmail.com` | env var `SEED_MASTER_PASSWORD` |

### Environment Setup

1. Copy `.env.example` to `.env`
2. Add `OPENAI_API_KEY=sk-...`
3. Configure optional vars (see `.env.example`)

## Key Architecture Patterns

**3-layer data architecture:** Ingestion ETL (pncp_raw_bids 1.5M rows, 400d retention) → Search Pipeline (datalake RPC <100ms p95, SSE async) → Results Cache (L1 InMemoryCache 4h + L2 Supabase 24h, SWR reactive). LLM classification tiers (keyword > llm_standard > llm_zero_match). ARQ background jobs for summaries/Excel.

Full details: `.claude/rules/architecture-patterns.md` (loads with `backend/**` or `frontend/**`). Module tables + route maps: `.claude/rules/architecture-detail.md` (same paths).

## Critical Implementation Notes

Full details in `.claude/rules/critical-impl-notes.md` (loads with `backend/**` or `supabase/**`). Covers: ingestion pipeline (27 UFs × 6 modalidades, 400d retention), pg_cron monitoring, PNCP/PCP/ComprasGov API quirks (tamanhoPagina=50 hard limit), filtering pipeline order, LLM integration, cache strategy, billing/auth, Railway runner history (CRIT-083→084→RES-BE-016), time budget waterfall (pipeline 100s > per_source 70s > per_uf 25s), resilience CI gates.

## Testing Strategy

**Stats:** 454 backend test files (5131+ passing), 376 frontend test files (2681+ passing), 60 E2E tests. Zero-failure policy — fix all failures, never treat as pre-existing.

Full patterns in `.claude/rules/testing-strategy.md` (loads with test files). Key: mock auth via `dependency_overrides`, patch `supabase_client.get_supabase` for cache, never `asyncio.get_event_loop().run_until_complete()` in tests (hangs).

## AIOS Framework & Agents

This project uses the AIOS Framework for AI-orchestrated development. Full agent, task, workflow, and script documentation is in `.claude/rules/aios-framework.md` (loads with `docs/stories/**`, `.aios-core/**`).

**Quick Reference:**
- Agents: `@dev`, `@qa`, `@architect`, `@pm`, `@devops`, `@data-engineer`, `@ux-design-expert`, `@analyst`, `@sm`, `@po`, `@aios-master`
- Invoke via `Skill` tool: `Skill(skill: "dev", args: "implement X")`
- **PROACTIVE RULE:** When the user describes a task, AUTOMATICALLY select and follow the matching BidIQ workflow without waiting for explicit invocation
- **This project is BROWNFIELD** — use brownfield and BidIQ-specific workflows

## Common Development Recipes

For step-by-step procedures (adding filters, modifying Excel, changing LLM prompts, syncing sectors), see `.claude/rules/dev-recipes.md` (loads with `backend/**`, `frontend/**`).

## Security Notes

Supabase Auth with RLS on all tables. Input validation via Pydantic (backend) and form validation (frontend). CORS configurable via `CORS_ORIGINS`. API keys in env vars only (never commit). Log sanitization via `log_sanitizer.py`. Redis token bucket rate limiting. Stripe webhook signature verification. Admin endpoints require `is_admin` or `is_master` role check.

## Important Files

| Category | Files |
|----------|-------|
| **Docs** | `PRD.md`, `ROADMAP.md`, `CHANGELOG.md`, `docs/founders-policy.md`, `docs/summaries/gtm-resilience-summary.md`, `docs/summaries/gtm-fixes-summary.md` |
| **Copy** | `docs/copywriting-guidelines.md` |
| **Config** | `.env.example`, `backend/requirements.txt`, `frontend/package.json`, `backend/sectors_data.yaml`, `backend/config.py` |
| **Database** | `supabase/migrations/` (~183 migrations, 48 tables, 13+ RPCs — source of truth, paired `.down.sql` mandatory STORY-6.2), `backend/migrations/` (12 legacy Alembic — audit only, do NOT add new) |
| **Ingestion** | `backend/ingestion/` (config, crawler, transformer, loader, checkpoint, scheduler), `backend/datalake_query.py` |
| **AIOS** | `.aios-core/development/agents/` (11), `.aios-core/development/tasks/` (115+), `.aios-core/development/workflows/` (7) |

## Git Workflow

**Branches:** `main` (production), `feature/*`, `fix/*`

**Commits:** Use conventional commits: `feat(backend):`, `fix(frontend):`, `docs:`, `chore:`

**Before Committing:** Run tests (pytest / npm test), check linting, update docs.

### Migration Policy (STORY-6.3 EPIC-TD-2026Q2)

| Directory | Role | Policy |
|-----------|------|--------|
| `supabase/migrations/` | **Source of truth** for all SQL schema (tables, indexes, RLS, pg_cron schedules) | New migrations go here. Applied via `npx supabase db push` and CI auto-apply (CRIT-050). Every new `.sql` must have a paired `.down.sql` rollback script (STORY-6.2). |
| `backend/migrations/` | **Legacy** Python/Alembic scripts | Historical audit trail only. Do NOT add new migrations here. Kept for reference; not executed by CI. |

**Rule for devs:** All schema changes → `supabase/migrations/YYYYMMDDHHMMSS_description.sql` + paired `YYYYMMDDHHMMSS_description.down.sql`. See `supabase/migrations/README.md` for templates and conventions.

### Migration CI Flow (CRIT-050)

Three-layer defense against unapplied migrations (prevents CRIT-039/CRIT-045 recurrence):

1. **PR Warning** (`migration-gate.yml`) — Runs on PRs touching `supabase/migrations/`. Lists pending migrations and posts a WARNING comment. Also enforces down.sql pairing (STORY-6.2 — blocks if missing). Does NOT block merge for pending-migration warnings.
2. **Push Alert** (`migration-check.yml`) — Runs on push to main + daily schedule. Blocks (exit 1) if unapplied migrations detected.
3. **Auto-Apply on Deploy** (`deploy.yml`) — After backend deploys, runs `supabase db push --include-all` automatically. Sends `NOTIFY pgrst, 'reload schema'` for immediate PostgREST cache refresh. Verifies no PGRST205 errors via smoke test. If push fails, marks deploy as DEGRADED (does not rollback).

**Required Secrets:** `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`, `SUPABASE_DB_URL` (for NOTIFY pgrst)

## Resilience CI Gates (EPIC-RES-BE-2026-Q2)

Two deterministic gates from 2026-04-27→30 outage: (1) `audit-execute-without-budget.yml` — blocks PRs with `.execute()` outside `_run_with_budget`; (2) `audit-prod-env.yml` — daily drift check for debug flags in Railway prod. Full details in `.claude/rules/critical-impl-notes.md`.
