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

### Inc-1: 15 vs 20 setores 🔴

**Source A** (`CLAUDE.md`): "**15 Setores:** Definidos em `backend/sectors_data.yaml`"
**Source B** (`.reversa/context/modules.json`): "20 setores configurados"
**Source C** (`code-analysis.md` Module 3): "20 setores configurados"

**Resolução**: Inspecionar `backend/sectors_data.yaml` real. Atualizar CLAUDE.md ou code-analysis.

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

### Gap-7: 15 vs 20 setores 🔴

Ver Inc-1 acima.

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
