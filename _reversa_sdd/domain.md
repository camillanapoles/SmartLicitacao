# Conhecimento de Domínio — SmartLic

> Gerado pelo **Reversa Detective** em 2026-04-27 · Fonte: git history (2.817 commits), ADRs existentes, código analisado pelo Archaeologist
> Escala de confiança: 🟢 CONFIRMADO · 🟡 INFERIDO · 🔴 LACUNA

---

## 1. Arqueologia Git — Cronologia de Decisões

### Eras do projeto (heurística por padrão de mensagem)

| Era | Marco | Tema dominante |
|-----|-------|----------------|
| 🟢 v0.1 — POC | Commits iniciais | PNCP single-source, filtro keyword, Excel básico |
| 🟢 v0.2 — Multi-source | `adr-multi-source-consolidation.md` + STORY-CRIT-054 | PNCP + PCP v2 + ComprasGov v3, dedup engine, circuit breakers |
| 🟢 v0.3 — LLM enrichment | `llm-arbiter.md` ADR + GPT-4.1-nano integration | Zero-match classification, viability scoring, summaries ARQ |
| 🟢 v0.4 — Billing/Trial | STORY-264/277/319 | Stripe checkout + 14-day trial sem cartão, plan enforcement, paywall |
| 🟢 v0.5 — DataLake | `20260326000000_datalake_raw_bids.sql` + STORY-OBS-001 | Layer 1 ETL PNCP→Supabase, eliminou pre-warming cache |
| 🟢 v0.5+ — SEO programático | EPIC-SEO-PROG, ~18 routers `/v1/*_publicos`, observatório, sitemaps dinâmicos | Vacuum aquisição B2B inbound |
| 🟢 2026-04 — Hardening | EPIC-BTS-2026Q2 (drift sweep), incidents 4/26 + 4/27 | Backend resilience, negative cache, AbortSignal timeouts, time budget waterfall |

### Padrões de commit

- Conventional commits (`feat`, `fix`, `chore`, `docs`, `test`, `hotfix`, `incident`)
- Story-driven prefixes: `STORY-XXX`, `CRIT-XXX`, `DEBT-XXX`, `GTM-XXX`, `EPIC-XXX`, `SEN-FE-XXX`, `SEO-PROG-XXX`, `MON-FN-XXX`
- Session naming: `docs(session): <name>-<date>` — handoffs documentados em `docs/sessions/YYYY-MM/`
- Squad/agent metadata em commit body via `Co-Authored-By: Claude ...`

### Incidentes capturados em git (memory + commits)

| Data | Incidente | Resolução | Commit |
|------|-----------|-----------|--------|
| 2026-04-26 | Backend wedge — cache 502 + AbortSignal timeouts | hotfix #515 (negative cache + abort) | `053eb785` |
| 2026-04-26 | SEN-FE-001 sitemap.ts ISR/cache antipattern | fix #508 alinhamento `revalidate` | `cb7ab63a` |
| 2026-04-27 | P0 wedge Stage 1+2 — perfil-b2g + fornecedor budget | PR #529 multi-stage hotfix | `22ca3d06` |
| 2026-04-27 | Healthcheck path /health → /health/live | infra fix (Railway probe) | `fc31ce2f` |
| 2026-04-23 | Railway rootDirectory leading-slash bug | dashboard manual (MCP gap) | (memory) |
| 2026-04-22 | GH Actions billing CRIT-080 (incorretamente atribuído) | repo público, queue normal saturação | `9e9c8cdd` |
| Pre-2026-Q2 | jemalloc + Sentry + cryptography SIGSEGV | revert + redeploy | (CLAUDE.md) |
| Pre-2026-Q2 | PNCP API breaking change (max tamanhoPagina 500→50) | reduzido em config + canary STORY-4.5 | (CLAUDE.md) |

### ADRs explícitos no repo

| ADR | Decisão | Status |
|-----|---------|--------|
| `ADR-TD004-trigger-consolidation.md` | Consolidação de triggers DB para reduzir overhead | implemented |
| `ADR-TD004-webhook-rls-security.md` | RLS strategy para webhook endpoints | implemented |
| `adr-multi-source-consolidation.md` | Multi-source PNCP+PCP+ComprasGov dedup engine | implemented v0.2 |
| `adr-plan-capabilities.md` | Capability-based plan enforcement (allow_pipeline, allow_excel_premium, etc.) | implemented |
| `ADR-003-shepherd-vs-intro-onboarding.md` | Shepherd.js > Intro.js para onboarding tour | implemented |

### ADRs retroativos inferidos (não-formalizados)

| Decisão | Evidência | Inferência |
|---------|-----------|-----------|
| 🟡 ARQ vs Celery | `arq>=0.27` em requirements, sem Celery | Escolha por async-native (Redis Streams) e leveza |
| 🟡 Supabase vs Firebase | RLS + PostgreSQL → Supabase | Privilege of SQL + Postgres ecosystem |
| 🟡 Stripe vs PagSeguro/Mercado Pago | Stripe SDK + 12 webhook events | Padronização internacional + Brazil tax handling via subscription |
| 🟡 Next.js 16 + React 18 | Aggressive RSC adoption visible em `rsc-migration-plan.md` | Bet em RSC para SEO programmatic (4146 pages) |
| 🟡 Resend vs SendGrid | `resend` em deps + `tiago@smartlic.tech` verified | Developer-friendly + cheaper for low volume |
| 🟡 GPT-4.1-nano vs Claude/Gemini | OpenAI SDK + low-cost tier | Cost optimization (~$0.10/1M tokens classification) |
| 🟡 Pydantic v2 strict (não Marshmallow/dataclasses) | Annotation-driven + JSON Schema → OpenAPI codegen | Strong-typed boundary contracts + STORY-2.1 |
| 🟡 Shepherd.js vs intro.js | ADR-003 explicit | Better UX flexibility + customization |

---

## 2. Regras de Negócio Implícitas

### Regras de Filtro/Classificação (extraídas de `filter.py` + `llm_arbiter`)

1. **Density tiers de matching keyword:**
   - `>5%` density → "keyword" source (alta confiança)
   - `2-5%` → "llm_standard" (LLM arbiter classifica)
   - `1-2%` → "llm_conservative" (LLM mais restritivo)
   - `0%` (zero match) → "llm_zero_match" (GPT-4.1-nano YES/NO)
   - `<1% sem LLM` → fallback PENDING_REVIEW se flag, senão REJECT

2. **Filtro fail-fast pipeline (order matters):**
   1. UF check (mais barato)
   2. Value range
   3. Keyword density
   4. LLM zero-match classification
   5. Status/date validation
   6. Viability scoring (post-filter)

3. **Auto-relaxation cascade (relaxation_level):**
   - 0 = filtro normal
   - 1 = sem floor mínimo (allow low-match)
   - 2 = sem density (allow keyword=0)
   - 3 = top by value (acima R$ X estimado)

4. **Viability 4-fator scoring (post-filter):**
   - Modalidade fit (30%)
   - Timeline (data_encerramento) (25%)
   - Valor estimado dentro range setor (25%)
   - Geografia (UF user vs UF bid) (20%)
   - Output: HIGH | MEDIUM | LOW

5. **SLA classificação:**
   - Precisão ≥85%, Recall ≥70% (15 samples/sector benchmark)
   - **NÃO zero FN/FP** — texto governamental ambíguo torna impossível

### Regras de Quota/Plan

1. **Trial 14d sem cartão** (STORY-264/277/319):
   - `profiles.plan_type='free_trial'` + `trial_expires_at = signup + 14d`
   - Quota: capabilities por plano em `plan_capabilities` table
   - Pipeline limit: 5 itens (trial only)
   - Após expiry: read-only mode (pipeline visível, busca bloqueada)

2. **Subscription gap grace period**: 3 dias (`SUBSCRIPTION_GRACE_DAYS`)
   - Stripe webhook fail ou network → não-rebaixa imediato
   - Hard expiry só após gap

3. **"Fail to last known plan"** (CLAUDE.md):
   - Erro DB → mantém plan atual cacheado (frontend localStorage 1h TTL)
   - **Nunca cai para `free_trial`** em transient error (UX downgrade prevention)

4. **Master/Admin bypass** (`profiles.is_admin=True` ou `is_master=True`):
   - Pula trial_expires_at, quota check, pipeline limit
   - **NÃO usar admin para validar paywall** (memory `reference_admin_bypass_paywall.md`)

5. **Atomic quota (`check_and_increment_quota_atomic`)**:
   - Single SQL UPDATE com WHERE clause (race-safe)
   - Returns (allowed, current_count, limit) tuple

### Regras de Cache (search results)

1. **3 estados por idade:**
   - Fresh 0-6h → serve direto
   - Stale 6-24h → serve + dispara SWR background revalidation
   - Expired >24h → não serve

2. **Cache populated on-demand** (warming deprecated 2026-04-18)

3. **Hash determinístico** (`compute_search_hash`):
   - Inclui setor_id, ufs (sorted), status, modalidades (sorted), modo_busca, dates (ISO normalized), termos, valor range, esferas, municipios, exclusion_terms
   - Date normalization: 4 formatos aceitos

4. **Per-key degradation**: chaves com falha consecutiva entram em backoff exponencial

### Regras de Pipeline Kanban

1. **5-stage state machine**: `descoberta → analise → preparando → enviada → resultado`
2. **Optimistic locking** (STORY-307): version no UPDATE, 0 rows affected → 409 Conflict
3. **Trial 5-item cap** (STORY-446): countdown blocking insert se ≥5
4. **Read-only mode trial expired** (STORY-265 AC15): drag desabilitado mas leitura permitida (incentivo conversão)

### Regras de Search (state machine)

1. **11 estados** (`SearchState`): CREATED → VALIDATING → PREPARING → EXECUTING → FILTERING → ENRICHING → GENERATING → PERSISTING → COMPLETED | FAILED | RATE_LIMITED | TIMED_OUT
2. **Transições inválidas** rejeitadas com log CRITICAL
3. **Persistência fire-and-forget** (`asyncio.create_task` não-bloqueante) em `search_state_transitions` (append-only) + `search_sessions` (mutável)

### Regras de Time Budget (STORY-4.4)

```
Railway proxy(120s) > Gunicorn(110s) > Pipeline(100s) > Consolidation(90s) > PerSource(70s) > PerUF(25s) > httpx(10c+15r)
```

- Invariante assertado em `tests/test_timeout_invariants.py`
- LLM skipa se elapsed > 90s (`is_simplified=True`)

### Regras de Webhook (Stripe)

1. **12 webhook events** handled (checkout, subscription created/updated/deleted, invoice succeeded/failed, customer updated, etc.)
2. **Idempotência via `events_processed`** table — exact_id check
3. **30s timeout** (`WEBHOOK_DB_TIMEOUT_S`)
4. **Signature gating** (`stripe.Webhook.construct_event`)
5. **`profiles.plan_type` sync mandatory** em todos webhooks

### Regras de Ingestão DataLake (Layer 1)

1. **400 dias retention** (`pncp_raw_bids`) — STORY-OBS-001
2. **Schedule**: full daily 5 UTC, incremental 11/17/23 UTC, purge 7 UTC
3. **Scope**: 27 UFs × 6 modalidades, 10d window full, 3d incremental
4. **PNCP max tamanhoPagina = 50** (era 500 pre-Feb 2026)
5. **Concurrency**: 5 UFs parallel, 2s delay, max 50 pages per (UF, mod)
6. **Content_hash dedup**: upsert via `upsert_pncp_raw_bids` RPC, 500 rows/batch
7. **Checkpoint resumable** via `ingestion_checkpoints` + `ingestion_runs` audit

---

## 3. Máquinas de Estado

### Search lifecycle

```
CREATED ──► VALIDATING ──► PREPARING ──► EXECUTING ──► FILTERING ──► ENRICHING ──► GENERATING ──► PERSISTING ──► COMPLETED
   │             │              │               │             │              │              │
   │             ▼              ▼               ▼             ▼              ▼              ▼
   ▼          FAILED         FAILED          FAILED        FAILED         FAILED         FAILED
RATE_LIMITED ◄─────────────────────────────────────────────────────────────────────────────────► TIMED_OUT
```

Transições inválidas (e.g., COMPLETED → EXECUTING) rejeitadas. Estados terminais: `COMPLETED, FAILED, RATE_LIMITED, TIMED_OUT`.

### Pipeline kanban

```
descoberta ──► analise ──► preparando ──► enviada ──► resultado
     ▲                                          │
     └──────────── reverse drag ────────────────┘ (qualquer direção)
```

Frontend permite drag livre (não enforce sequence). Backend valida `stage ∈ VALID_STAGES`.

### Trial lifecycle

```
signup ──► trial_active (14d) ──► [day 0/3/7/10/13 emails]
                │
                ▼
       trial_expired ──► [grace 3d] ──► hard_expired (read-only)
                │
                ▼
       converted (paid) ──► subscription_active ──► [renewal] ──► active
                                  │
                                  ▼
                           subscription_canceled ──► [grace 3d] ──► expired
```

### Subscription (Stripe-driven)

```
trialing ──► active ──► past_due ──► unpaid (cancel_at_period_end)
   │           │           │              │
   │           │           ▼              ▼
   │           │      grace 3d        canceled
   │           ▼
   ▼      canceled
incomplete_expired
```

### Conversation (messages)

```
[*] ──► open ──► awaiting_support ──► awaiting_user ──► awaiting_support ──► closed
```

Re-open: `closed → awaiting_support` se user posta nova mensagem.

### Cache entry

```
fresh (0-6h) ──► stale (6-24h) ──► expired (>24h)
                      │
                      ├──► serve + SWR revalidate ──► back to fresh
                      ▼
                  per-key degradation if revalidate fails
```

---

## 4. Matriz de Permissões (RBAC)

### Roles

| Role | Source | Bypass |
|------|--------|--------|
| **anonymous** | sem JWT | rotas públicas (observatório, sitemaps, calculadora, lead_capture, blog stats) |
| **trial active** | `plan_type='free_trial' AND trial_expires_at > now` | quota mensal por plan_capabilities |
| **trial expired** | `plan_type='free_trial' AND trial_expires_at < now` | quota=0; pipeline read-only |
| **paid (monthly/semestral/annual)** | `plan_type IN ('smartlic_pro', 'smartlic_consultoria', ...) AND subscription_status='active'` | quota normal por plano |
| **founding** | `plan_type='founding'` | early adopter discount lifetime |
| **master** | `profiles.is_master=true` | quota ilimitada, capabilities full |
| **admin** | `profiles.is_admin=true OR user_id IN ADMIN_USER_IDS env` | quota ilimitada + admin endpoints + cache eviction + reconciliation trigger |

### Capability matrix (plan_capabilities table)

| Capability | trial | smartlic_pro | smartlic_consultoria | master | admin |
|-----------|-------|--------------|----------------------|--------|-------|
| `allow_search` | ✅ (5/mês) | ✅ (50/mês) | ✅ (200/mês) | ✅ ∞ | ✅ ∞ |
| `allow_excel_premium` | ❌ (limited preview) | ✅ | ✅ | ✅ | ✅ |
| `allow_pipeline` | ✅ (5 itens) | ✅ (∞) | ✅ (∞) | ✅ | ✅ |
| `allow_pipeline_write` | ✅ enquanto trial active | ✅ | ✅ | ✅ | ✅ |
| `allow_alerts` | ✅ (basic) | ✅ (advanced) | ✅ | ✅ | ✅ |
| `allow_google_sheets` | ❌ | ✅ | ✅ | ✅ | ✅ |
| `allow_pdf_export` | ✅ (com watermark) | ✅ | ✅ | ✅ | ✅ |
| `allow_share_analise` | ❌ | ✅ | ✅ | ✅ | ✅ |
| `allow_organizations` | ❌ | ❌ | ✅ (multi-seat) | ✅ | ✅ |
| `allow_partner_program` | ❌ | ❌ | ❌ | ❌ | ✅ (admin manage) |
| `allow_admin_*` | ❌ | ❌ | ❌ | ❌ | ✅ |

### Endpoint matrix por role (sample)

| Endpoint | anon | trial active | trial expired | paid | master | admin |
|----------|------|-------------|---------------|------|--------|-------|
| `POST /v1/buscar` | ❌ | ✅ (quota) | ❌ (403 trial_expired) | ✅ | ✅ | ✅ |
| `GET /v1/pipeline` | ❌ | ✅ | ✅ (read-only) | ✅ | ✅ | ✅ |
| `POST /v1/pipeline` | ❌ | ✅ (cap 5) | ❌ (require_active_plan) | ✅ | ✅ | ✅ |
| `GET /v1/observatorio/*` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /v1/admin/users` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `POST /v1/admin/users/{id}/assign-plan` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `GET /v1/admin/cache/metrics` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `POST /v1/founding/checkout` | ✅ (signup com link) | ✅ | ✅ | ❌ (já é paid) | ✅ | ✅ |
| `POST /v1/share/analise` | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| `GET /v1/share/analise/{hash}` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /webhooks/stripe` | (signature gated) | — | — | — | — | — |
| `GET /v1/auth/check-email` | ✅ | — | — | — | — | — |
| `POST /v1/feedback` | ❌ | ✅ (rate limit) | ❌ | ✅ | ✅ | ✅ |
| `GET /v1/admin/feedback/patterns` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

### Defense-in-depth

- **RLS**: ativado em todas tables (Supabase Auth integration)
- **Service-role bypass**: backend usa `SUPABASE_SERVICE_ROLE_KEY` para admin client → RLS bypassed
- **Defesa**: `.eq("user_id", user_id)` explícito em queries (ISSUE-021 fix)
- **Token validation**: 3-strategy fallback (JWKS ES256 > PEM > HS256)
- **Cache 2-tier auth**: L1 LRU 60s + L2 Redis 5min
- **Rate limiting**: Redis token bucket per-user
- **Admin lookup**: env `ADMIN_USER_IDS` whitelist + `profiles.is_admin` flag fallback

### Lacunas RBAC

- 🔴 `is_admin` boolean — não há RBAC granular (cache_admin, user_admin, billing_admin separados). Compliance LGPD pode exigir auditoria por escopo.
- 🟡 Plan enforcement parcialmente client-side (`localStorage` 1h TTL) — defesa secundária, não primária.
- 🟡 Master role propriedade vaga (memory): "QA/diagnose de signup bug NÃO usar admin para validar paywall behavior" indica risco de bypass invalidando testing.
- 🔴 Multi-tenant (organizations) RBAC ainda vagulously definido — `org_id`, `org_role` ('owner', 'member', 'viewer'?) não-documentado.

---

## 5. Glossário de Domínio

| Termo | Significado |
|-------|-------------|
| **PNCP** | Portal Nacional de Contratações Públicas — fonte primária federal Brasil |
| **PCP v2** | Portal de Compras Públicas v2 (compras.api...) — secondary source pública |
| **ComprasGov v3** | dadosabertos.compras.gov.br — terciária, dual-endpoint legacy + Lei 14.133 |
| **Lei 14.133** | Lei de Licitações 2021 — substituiu Lei 8.666/93 |
| **Edital** | Documento publicação de licitação |
| **Modalidade** | Tipo de licitação (Pregão, Concorrência, Tomada de Preços, Convite, Concurso, Leilão, etc.); IntEnum 1-12 |
| **Esfera** | Federal, Estadual, Municipal, Distrital |
| **CNPJ** | Cadastro Nacional Pessoa Jurídica (14 dígitos) |
| **CNAE** | Classificação Nacional de Atividades Econômicas (5 dígitos) |
| **B2G** | Business-to-Government |
| **Setor** | Categoria de atuação (15 setores em `sectors_data.yaml`); ex: Limpeza, Uniformes, TI |
| **Viabilidade** | Score 4-fator HIGH/MEDIUM/LOW |
| **Pipeline** | Funil kanban de oportunidades user-tracked |
| **Trial** | 14 dias gratis sem cartão |
| **DataLake** | Layer 1 ETL: PNCP raw bids + supplier_contracts em Supabase |
| **SWR** | Stale-While-Revalidate (cache pattern) |
| **ARQ** | Async Redis Queue — Python lib (não confundir com IBM ARQ) |
| **ARQ Worker** | Processo separado `PROCESS_TYPE=worker` que consome jobs |
| **SSE** | Server-Sent Events — streaming progress updates |
| **Time budget waterfall** | Layered timeouts decrescentes para previnir Railway proxy kill |
| **Zero-match** | Bid com 0% keyword density — classificado pelo LLM YES/NO |
| **Density** | % de keywords matched do total tokens em `objeto` |
| **Floor** | Min match count threshold para inclusion |
| **Relaxation cascade** | 4 níveis de filtro mais permissivo se 0 results |
| **Auto-search** | First-analysis automática pós-onboarding (GTM-004) |
| **Founding** | Plano early-adopter com lifetime discount |

---

## 6. Lacunas (require user validation)

- 🔴 **Multi-tenant (organizations)**: roles (`owner`, `member`, `viewer`?), `org_id` propagation em pipeline_items/searches/messages — não-documentado
- 🔴 **MFA flow**: 4 endpoints (`/mfa/{status, recovery-codes, verify-recovery, regenerate-recovery}`) mas trigger/enforce policy não-clara
- 🔴 **Founding plan**: `POST /founding/checkout` separate route — pricing? deadline? cap?
- 🔴 **Partner program**: dashboard + admin endpoints existem; commission %, payout cycle, attribution rules?
- 🔴 **CNAE→Setor mapping**: hardcoded em `utils/cnae_mapping.py`; cobertura completa? fallback "diversos"?
- 🟡 **`estimated_hours_saved`**: constante 2.5h/search — base empírica? 
- 🟡 **15 vs 20 setores**: CLAUDE.md menciona 15 setores; modules.json menciona 20. Inconsistência?
- 🔴 **Webhook HMAC verify gap** (Resend `/trial-emails/webhook`) — security hole?
- 🔴 **Admin role granularity**: all-or-nothing — compliance concern?
- 🟡 **Pricing R$397/297/...**: source of truth `plan_billing_periods` table sync com Stripe — quando sync corre?
