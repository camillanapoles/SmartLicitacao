# Review Report — Especificações SmartLic

> Gerado pelo **Reversa Reviewer** em 2026-04-27
> Revisão cruzada das specs (`specs/01-05`) + domain.md + architecture.md + data-master.md + flowcharts/* + user-stories.md

---

## 1. Coverage Map

| Módulo | Code Analysis | Flowchart | Spec SDD | OpenAPI | Stories | Coverage |
|--------|--------------|-----------|----------|---------|---------|----------|
| 1. search | ✅ | ✅ | ✅ 01 | ✅ | ✅ US-001 | 🟢 100% |
| 2. ingestion-datalake | ✅ | ✅ | ✅ 05 | (RPC) | ✅ US-028 | 🟢 100% |
| 3. filter-llm-viability | ✅ | ✅ | parte 01 | parte 01 | parte US-001 | 🟢 90% |
| 4. cache (LEGACY) | ✅ | parte 01 | parte 01 | — | — | 🟢 80% (deprecated context) |
| 5. billing-quota | ✅ | ✅ | ✅ 02 | ✅ | ✅ US-005, US-013 | 🟢 100% |
| 6. auth-oauth | ✅ | ✅ | ✅ 03 | ✅ | ✅ US-005 (signup) | 🟢 100% |
| 7. pipeline-kanban | ✅ | ✅ | ✅ 04 | ✅ | ✅ US-002 | 🟢 100% |
| 8. jobs+cron | ✅ | ✅ | ⏭ deferred | (interno) | ✅ US-028, US-029 | 🟡 80% |
| 9. routes (registration) | ✅ | ✅ | implícita | ✅ openapi | — | 🟢 90% |
| 10. schemas+contracts | ✅ | ✅ | implícita | ✅ openapi | — | 🟢 90% |
| 11. messages+feedback | ✅ | ✅ | ⏭ deferred | ✅ | ✅ US-008, US-009 | 🟡 85% |
| 12. onboarding+analytics | ✅ | ✅ | ⏭ deferred | ✅ | ✅ US-006, US-007 | 🟡 85% |
| 13. admin | ✅ | (em routes.md) | ⏭ deferred | ✅ | ✅ US-014–023 | 🟡 80% |
| 14. exports | ✅ | ✅ | ⏭ deferred | ✅ | ✅ US-004 | 🟡 85% |
| 15. observatory+seo | ✅ | ✅ | ⏭ deferred | ✅ | ✅ US-024–027 | 🟡 80% |
| 16. design-system | ✅ | ✅ (combined) | inline | — | — | 🟢 75% |
| 17. email-templates | ✅ | ✅ (combined) | ⏭ deferred | (interno) | parte US-005 | 🟡 70% |
| 18. tests+migrations | ✅ | ✅ (combined) | (interno) | (CI) | — | 🟡 70% |

**Cobertura geral: ~85% completo (alvo `doc_level=completo`).** Specs SDD formais para 5/18 módulos críticos; restantes têm cobertura via code-analysis + flowchart + user-stories.

## 2. Inconsistências Detectadas

### Inc-1: 15 vs 20 setores 🟢 RESOLVIDO

**Source A** (`CLAUDE.md`): "**15 Setores:** Definidos em `backend/sectors_data.yaml`" *(era 15 quando este report foi gerado — já corrigido para 20 Setores)*
**Source B** (`.reversa/context/modules.json`): "20 setores configurados"
**Source C** (`code-analysis.md` Module 3): "20 setores configurados"

**Resolução (PR #798 — 2026-05-07)**: Auditoria empírica confirmou `len(yaml.safe_load(open('backend/sectors_data.yaml'))['sectors']) == 20`. Os 20 IDs são: vestuario, alimentos, informatica, mobiliario, papelaria, engenharia, software_desenvolvimento, software_licencas, servicos_prediais, produtos_limpeza, medicamentos, equipamentos_medicos, insumos_hospitalares, vigilancia, transporte_servicos, frota_veicular, manutencao_predial, engenharia_rodoviaria, materiais_eletricos, materiais_hidraulicos. CLAUDE.md já reflete "**20 Setores**" corretamente. Sem ação residual.

### Inc-2: Cache warming deprecation context 🟢

**Source A** (CLAUDE.md): "Cache warming jobs deprecated 2026-04-18 (STORY-CIG-BE-cache-warming-deprecate)"
**Source B** (memory): "DataLake Supabase 50k bids + 2M contratos é fonte primária"
**Source C** (code-analysis Module 4): cache warming/refresh ARQ jobs deprecated

**Resolução**: Consistente. Cache warming/refresh deprecated, passive SWR + DataLake-first ativo. Sem ação.

### Inc-3: Backend modules pipeline path 🟡

**Source A** (Archaeologist Module 1): `backend/pipeline/stages/execute.py` 1240 LOC
**Source B** (file system): existe em `backend/pipeline/` mas Module 7 (pipeline-kanban) refere-se a `routes/pipeline.py` + `frontend/app/pipeline/`

**Resolução**: Naming colision — `backend/pipeline/` é sub-pkg do search pipeline (stages, budget, cache_manager); `routes/pipeline.py` é o kanban CRUD; `frontend/app/pipeline/` é a UI kanban. Documentar disambiguation.

### Inc-4: 49 vs 187 endpoints 🟡

**Source A** (CLAUDE.md): "49 endpoints"
**Source B** (Archaeologist Module 9): "65 routers → 187 endpoints"

**Resolução**: CLAUDE.md outdated. Atualizar.

### Inc-5: ARQ functions count discrepancy 🟡

**Source A** (Archaeologist Module 8): "7 functions ARQ + 19 cron loops + 9 ARQ cron"
**Source B** (`jobs/queue/config.py`): WorkerSettings.functions inclui 7 base + ingestion conditional + monitoring → 7-15 dependendo de feature flags

**Resolução**: Documentar como "7 base functions + N ingestion functions condicional".

## 3. Gaps de Documentação (lacunas para validar com user)

### Gap-1: Multi-tenant RBAC 🔴

- `organizations` + `organization_members` exist
- `routes/organizations.py` 8 endpoints
- **Mas**: roles (`owner`, `member`, `viewer`?) não-enforce em endpoints
- **Lacuna**: RBAC granular não-documentado em código nem ADR

**Pergunta ao user**: Existe algum doc operacional sobre roles em organizações? Ou MVP não-implementou enforcement?

### Gap-2: Founding plan details 🔴

- `POST /v1/founding/checkout` exists
- `founding_leads` + `founding` plan_type exist
- **Lacuna**: pricing? deadline? cap (early-adopter limitada)?

**Pergunta ao user**: Founding tem cap de signups? Pricing lifetime fixo?

### Gap-3: Partner program 🔴

- `partners`, `partner_referrals` tables
- `routes/partners.py` admin endpoints
- **Lacuna**: commission %? payout cycle? attribution rules (last-click? first-touch?)?

**Pergunta ao user**: Existe contrato/spec do partner program?

### Gap-4: MFA enforcement policy 🔴

- 4 endpoints MFA
- **Lacuna**: quando MFA é obrigatório? Para admin? Após N login attempts?

**Pergunta ao user**: MFA é opcional ou enforceável em planos enterprise?

### Gap-5: HMAC webhook verify Resend 🔴

- Memory `reference_trial_email_log_delivery_status_null.md`: "HMAC verify ainda não implementado"
- `POST /v1/trial-emails/webhook` aceita sem verify

**Recomendação**: Implementar STORY antes de prod scale (security hole atual).

### Gap-6: Estimated hours saved magic constant 🟡

- `analytics/summary` retorna `estimated_hours_saved = total_searches * 2.5h`
- **Lacuna**: 2.5h baseado em quê? Survey? Estimativa?

**Pergunta ao user**: É possível medir empiricamente para validar/atualizar?

### Gap-7: 15 vs 20 setores 🟢 RESOLVIDO (PR #798 — 2026-05-07)

Ver Inc-1 acima. Auditoria empírica confirmou 20 setores em `backend/sectors_data.yaml`. CLAUDE.md já correto.

### Gap-8: CNAE→Setor mapping completeness 🟡

- `utils/cnae_mapping.py` hardcoded
- **Lacuna**: cobertura completa? Quais CNAEs caem em "diversos"?

**Pergunta ao user**: Existe spreadsheet de cobertura CNAE? Atualização frequência?

### Gap-9: Pricing source-of-truth canonical 🟡

- CLAUDE.md: "Source of truth: `plan_billing_periods` table"
- Mas tabela é Stripe-synced — quando sync corre?

**Pergunta ao user**: Sync `plan_billing_periods` ↔ Stripe é manual ou automático? Frequência?

### Gap-10: Service-role statement_timeout 🔴

- Memory: "service_role: NULL (sem timeout)"
- **Identified mas não-fixed em prod**

**Recomendação**: Set `statement_timeout=60s` em service_role (PR alteration).

## 4. Confiança Final por Categoria

| Categoria | Confidence | Justification |
|-----------|-----------|---------------|
| Backend architecture | 🟢 90% | 18 módulos analisados, code-analysis exaustivo |
| Frontend architecture | 🟡 75% | Páginas mapeadas, components partial; sem deep-dive em hooks/state |
| Database schema | 🟢 85% | 48 tables identificadas; RLS policies não-exhaustively documentadas |
| API contracts | 🟢 90% | 187 endpoints mapeados; OpenAPI gerado por response_model |
| Business rules | 🟢 80% | filter density tiers, time budget, plan capabilities, state machines bem-documentados |
| Integration points | 🟢 85% | 13 SaaS deps identificados, failure modes documentados |
| Tests coverage | 🟡 70% | Counts confirmed; coverage map por módulo não-feito |
| RBAC | 🟡 65% | Admin/master definido; org RBAC vagulously |
| Email lifecycle | 🟢 80% | Trial 6-step + dunning bem-documentado |
| Observability | 🟢 85% | Sentry + Mixpanel + Prometheus + OTel + pg_cron monitor |

**Confiança global: 🟢 80% — projeto bem-coberto. Lacunas restantes são item-by-item para user validation.**

## 5. Recomendações de próximos passos

### Imediato (este sprint)

1. **Resolve Inc-1 e Inc-4**: atualize CLAUDE.md com counts corretos
2. **Implementa HMAC verify** Resend webhook (Gap-5)
3. **Set statement_timeout=60s** em service_role (Gap-10)
4. **Documente RBAC organizations** (Gap-1)

### Sprint+1

5. **Adicione spec SDD formal** para módulos 8-15 deferred (templates já criados)
6. **Capture screenshots** admin pages + onboarding wizard + SEO programmatic samples
7. **Document founding + partner program** specs (Gap-2, Gap-3)
8. **Audit RLS policies** completas (export `pg_policy`)

### Backlog

9. **CNAE→Setor mapping migration** para tabela DB (versionável)
10. **Empirical validation** estimated_hours_saved (Gap-6)
11. **MFA enforcement policy** decision (Gap-4)

## 6. Arquivos gerados nesta análise

```
_reversa_sdd/
├── inventory.md                 (Scout — pre-existente)
├── dependencies.md              (Scout — pre-existente)
├── code-analysis.md             (Archaeologist — 18 módulos completos)
├── data-dictionary.md           (Archaeologist — DTOs por módulo)
├── domain.md                    (Detective — git, regras, state machines, RBAC)
├── architecture.md              (Architect — C4 L1/L2/L3, ERD, integrações, Spec Impact Matrix)
├── data-master.md               (Data Master — schema completo + RLS + RPCs + pg_cron)
├── visor-ui-inventory.md        (Visor — 226 screenshots + estados UI)
├── openapi-summary.md           (Writer — 187 endpoints inventory)
├── user-stories.md              (Writer — 30 user stories extraídas)
├── code-spec-matrix.md          (Writer — rastreabilidade bidirecional)
├── review-report.md             (Reviewer — este arquivo)
├── specs/
│   ├── 01-search-pipeline.spec.md
│   ├── 02-billing-quota.spec.md
│   ├── 03-auth-oauth.spec.md
│   ├── 04-pipeline-kanban.spec.md
│   └── 05-ingestion-datalake.spec.md
└── flowcharts/
    ├── search.md
    ├── ingestion-datalake.md
    ├── filter-llm-viability.md
    ├── billing-quota.md
    ├── auth-oauth.md
    ├── pipeline-kanban.md
    ├── jobs-cron.md
    ├── routes.md
    ├── schemas-contracts.md
    ├── messages-feedback.md
    ├── onboarding-analytics.md
    ├── exports.md
    ├── observatory-seo.md
    └── design-emails-tests.md
```

## 7. Sign-off

Análise inicial **completa** sob `doc_level=completo`. Cobertura ~85% global. Lacunas concentradas em: detalhes de programa (founding, partner), RBAC org granular, RLS export, e item-by-item validation com user.

Ready para handoff:
- ✅ Onboarding novo dev
- ✅ Migration planning
- ✅ Audit/security review
- ✅ Refactoring com Spec Impact Matrix

**Next iteration suggested**: deep-dive em 1-2 specs deferred + screenshots admin + RLS audit (separate session).

---

## 8. Refresh — 2026-04-29 a 2026-05-01

> Atualização diferencial: 15 commits, 11 PRs mergeados, 8 stories novas, 6 sessões.

### 8.1 Gaps Resolvidos

| Gap | Resolução | Evidência |
|-----|-----------|-----------|
| Gap-10 (service_role timeout NULL) | PR #545 + migration 20260427213410 `ALTER ROLE service_role SET statement_timeout=60s` | RESOLVED |
| Gap-3 (partner program) | ADR decisions 2026-04-29: 20% lifetime, Pix dia 5, last-click 30d, auto self-service | RESOLVED |
| Gap-2 (founding plan) | ADR `docs/adr/founding-plan-canonical.md`: 50 seats, deadline 2026-05-30, lifetime guarantee, HTTP 410 post-cap | RESOLVED |
| SWEEP-001 parcial | PR #579 + PR #535 — sitemap + top-tier routes cobertos com `_run_with_budget` | MITIGATED |
| GSC-001 | PR `baa481f8` + `SYS-019` next.config.js: `s-maxage=86400` em sub-sitemaps | RESOLVED |
| DATA-DRIFT-001 (Paulo paywall) | Commit `d6665926` — paywall consolidation `user_subscriptions.expires_at` canonical | RESOLVED |

### 8.2 Gaps Novos Detectados

| Gap | Descrição | Severidade |
|-----|-----------|-----------|
| CRIT-084 | uvicorn sem worker timeout (RUNNER=uvicorn + no `--worker-timeout`); worker trava indefinidamente sob saturation | 🔴 P0 |
| POOL-LEAK-001 | `asyncio.wait_for(asyncio.to_thread(...))` cancel — cleanup inline bloqueia event loop até `statement_timeout=15s`; ticks de 14-48s confirmados em logs Railway | 🔴 P0 |
| Gap-14 (sweep incompleto) | 11 rotas long-tail SEO programmatic ainda sem `_run_with_budget` pós PR #555+549 | 🔴 P0 |

### 8.3 Score 2026-05-01

| Dimensão | Score | Delta |
|----------|-------|-------|
| Documentation coverage | 🟢 86% | +4 (Gap-2/3 resolvidos, incidents documentados) |
| Operational reliability | 🟡 78% | +23 (SWEEP-001 + GSC-001 RESOLVED + CI gate) |
| Architectural consistency | 🟢 88% | +8 (8 novos patterns architecture.md §9-10) |
| Test/CI gates | 🟡 82% | +12 (audit-execute-without-budget.yml + load test) |
| RBAC/Security | 🟡 75% | +10 (DATA-DRIFT-001 + service_role timeout) |
| **Composite** | 🟢 **84%** | **+12** (de 72%) |

### 8.4 Cross-Check Empírico

- 9 claims verificados; 1 corrigido: `OBS-001 file = backend/middleware/bot_detection.py` (não `bot_rate_limit.py` — rename forçado por collision com `middleware.py` pós PR #562)
- Inconsistência Gap-7 (15 vs 20 setores em CLAUDE.md) resolvida via PR #798 (2026-05-07) — auditoria empírica confirmou 20 setores

---

## 9. Refresh — 2026-05-01 a 2026-05-02

> Atualização diferencial: ~63 commits, 12+ PRs, 9 stories novas (CONV-CTA/CONV-INST epicycle), 2 sessões.

### 9.1 PRs / Stories Shipped

| PR / Commit | Story | Descrição | Status |
|-------------|-------|-----------|--------|
| PR #603/#600 | RES-BE-015 | Sweep `_run_with_budget` em 15 rotas long-tail SEO (11 originais + 4 f6b7acb2 callsites + audit script + CI gate + load test) | ✅ InReview / Done |
| PR #622 | CTR-OPT-001 | Rewrite title/meta dos 6 top blog posts GSC | ✅ Done |
| PR #602 | MON-FN-005 | `/health/ready` usa `sb_execute_direct` + 5s timeout; Mixpanel startup assertion | ✅ InReview |
| commits 285f29d7+45a0fa66 | RES-BE-016 | Wrap sync helpers remanescentes em async handlers (CRIT-084 partial) | InProgress |
| PR #595 | SEO-026 | Fix robots.txt RFC 9309 prefix-match para `/alertas-publicos` | ✅ Done |
| PR #592 | TD-BE-014 | `PNCPRateLimitError` carrega `retry_after`; levantado em exhaustion 429 | ✅ Done |
| PR #591 | SEN-BE-002 | Strip `top_result_*` columns de `search_sessions` queries | ✅ Done |
| PR #589 | RES-BE-018a | MFA bare `.execute()` fix | ✅ Done |
| commit 047e0a6b | DEBT-OBS-001 | `is_historical` usa last-day boundary (não 30d-from-start) | ✅ Done |
| commit 7cf341ed | — | UUID v4 validation em `authorization.get_admin_ids` (security hardening) | ✅ Done |
| PR #546 | SEO-PROG-007 | `robots.ts` dynamic route handler (replacement for `robots.txt` static) | ✅ Done |
| SEO-PROG-008 | SEO-PROG-008 | `getBackendUrl` helper + chain audit + CI gate (BACKEND_URL scope-limited lint) | ✅ Done |
| baa481f8+SYS-019 | SEO-016 | GSC sub-sitemap cache-control fix — `s-maxage=86400` via next.config.js | ✅ Done (close-out confirmado 2026-05-01) |

### 9.2 Novos Epicycles / Stories

| Story | Epicycle | Descrição | Status |
|-------|----------|-----------|--------|
| CONV-CTA-001 | EPIC-CONV-DIAG-2026-04-30 | CTA trial em `/contratos/[setor]/[uf]` e páginas orgão | InReview |
| CONV-CTA-002 | EPIC-CONV-DIAG-2026-04-30 | Audit e CTA em templates programáticos (W2 — gated em CONV-CTA-001 7-14d sinal) | Draft (NO-GO @po — AC ausentes por design) |
| CONV-INST-001 | EPIC-CONV-DIAG-2026-04-30 | Mixpanel page-load + traffic source tracking | InReview |
| CONV-INST-002 | EPIC-CONV-DIAG-2026-04-30 | Mixpanel signup form lifecycle events | InReview |
| CONV-INST-003 | EPIC-CONV-DIAG-2026-04-30 | Email confirmation lifecycle events | InReview |
| CONV-INST-005 | EPIC-CONV-DIAG-2026-04-30 | MS Clarity trial onboarding tagging | Ready |
| RES-BE-015 | EPIC-RES-BE-2026-Q2 | Sweep 15 rotas long-tail SEO com `_run_with_budget` (escopo expandido) | InReview |
| RES-BE-017 | EPIC-RES-BE-2026-Q2 | Pool leak — mitigação `asyncio.wait_for` + `asyncio.to_thread` cleanup inline | Ready (Sprint 2) |
| SEO-016 | EPIC-SEO-PROG-2026-Q2 | GSC sub-sitemap cache-control override | Done |

### 9.3 Gaps Resolvidos (neste período)

| Gap | Resolução | Evidência |
|-----|-----------|-----------|
| Gap-14 (sweep incompleto) | RES-BE-015 Done — 15 rotas cobertas (11 originais + 4 f6b7acb2 callsites) | PR #603/#600 merged |
| GSC-001 confirmado | SEO-016 close-out: curl prod Googlebot → `cache-control: s-maxage=86400` em `/sitemap/{0,4}.xml` | baa481f8 + SYS-019 |
| SEN-BE-002 | `top_result_*` columns stripped de `search_sessions` queries | PR #591 |
| Robots alertas (SEO-026) | RFC 9309 prefix-match fix libera `/alertas-publicos/*` no robots.txt | PR #595 |

### 9.4 Gaps Persistentes / Abertos

| Gap | Descrição | Story | Status |
|-----|-----------|-------|--------|
| CRIT-084 | Worker sem timeout — uvicorn RUNNER não recicla worker travado | RES-BE-016 | InProgress (commits parciais; middleware AC4 merged PR #588) |
| POOL-LEAK-001 | Pool leak root cause — `asyncio.wait_for` + thread cleanup inline | RES-BE-017 | Ready (Sprint 2) |
| Gap-7 (setores) | Auditoria empírica confirmou 20 setores em `sectors_data.yaml`. CLAUDE.md já reflete "20 Setores". | PR #798 | ✅ RESOLVIDO 2026-05-07 |
| CONV-DIAG (CRO) | Instrumentação completa SEO → trial não finalizada (CONV-INST- stories InReview) | CONV-INST-001/002/003/005 | InReview |

### 9.5 Score 2026-05-02

| Dimensão | Score | Delta |
|----------|-------|-------|
| Documentation coverage | 🟢 87% | +1 (CONV epicycle documentado, SEO-016 fechado) |
| Operational reliability | 🟡 82% | +4 (RES-BE-015 done elimina classe wedge; RES-BE-016 partial; MON-FN-005 health hardening) |
| Architectural consistency | 🟢 89% | +1 (getBackendUrl pattern codificado em CI gate) |
| Test/CI gates | 🟢 84% | +2 (audit-execute CI gate + load test bundled em RES-BE-015) |
| RBAC/Security | 🟡 77% | +2 (UUID v4 validation auth + MFA bare execute fix) |
| **Composite** | 🟢 **84%** | ≈ estável (+0; reliability +4 vs coverage +1; outras marginais) |

**Nota:** composite mantido estável porque CRIT-084 e POOL-LEAK-001 ainda abertos compensam as melhorias de reliability.
