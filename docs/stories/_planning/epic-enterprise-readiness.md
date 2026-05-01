# Epic: Enterprise Readiness — Producao Monetizada Confiavel

## Metadata
- **ID:** EPIC-ENT-001
- **Data:** 2026-02-25
- **Origem:** Brownfield Discovery Assessment (`docs/prd/technical-debt-assessment.md`)
- **QA Gate:** APPROVED
- **Esforco Total:** ~15 horas (~2 dias de trabalho)
- **Investimento:** R$ 2.250 (base R$150/h)
- **ROI:** 33:1 a 67:1 (risco evitado: R$75-155K)

## Objetivo

Executar os 21 fixes (7 Tier 1 + 14 Tier 2) identificados no Technical Debt Assessment para colocar o SmartLic em **posicao de producao monetizada, confiavel e enterprise-grade** em todos os 6 core flows:

1. Busca multi-fonte (PNCP + PCP v2 + ComprasGov)
2. Billing/Subscription (Stripe + trial)
3. Auth + Onboarding
4. Pipeline (Kanban)
5. Relatorios (Excel + IA)
6. Dashboard/Analytics

## Criterios de Sucesso do Epic

- [ ] Todos os 6 core flows enterprise-ready (conforme assessment)
- [ ] Backend test suite: 5131+ passing, 0 failures
- [ ] Frontend test suite: 2681+ passing, 0 failures
- [ ] Stripe webhook flow: checkout, cancel, payment failure funcionais
- [ ] Signup flow: email com metadata, Google OAuth, re-signup — todos ok
- [ ] Nenhuma pagina protegida expoe raw `error.message`
- [ ] UX Enterprise Score: 4.0+/5 (de 3.7/5 atual)
- [ ] Schema reproducivel 100% a partir de migrations (disaster recovery)

## Stories

| ID | Titulo | Prioridade | Esforco | Dependencia | Area |
|----|--------|-----------|---------|-------------|------|
| STORY-261 | Database Schema Integrity — Missing Columns | P0 | 1.5h | Nenhuma | Database |
| STORY-262 | Signup Trigger Fix — handle_new_user | P0 | 1.5h | STORY-261 | Database |
| STORY-263 | Trial Stats Bug Fix — pipeline_items | P0 | 0.5h | Nenhuma | Backend |
| STORY-264 | Database FK & RLS Hardening | P1 | 3h | STORY-261 | Database |
| STORY-265 | JSONB Storage Governance | P1 | 2h | Nenhuma | Database |
| STORY-266 | Backend Alignment — Python & Branding | P1 | 0.75h | Nenhuma | Backend |
| STORY-267 | Enterprise UX Polish — Error Handling & A11y | P1 | 5h | Nenhuma | Frontend |

## Execution Phases

### Phase A: Blocking Fixes (Dia 1 manha — 3h)
```
STORY-261 (DB columns) ──────────> STORY-262 (trigger — depende de 261)
STORY-263 (trial stats) ─────────> Paralelo com 261
```

### Phase B: Stability Fixes (Dia 1 tarde + Dia 2 — 12h)
```
STORY-264 (FK/RLS) ──────────────> Depende de Phase A
STORY-265 (JSONB) ───────────────> Independente
STORY-266 (Backend alignment) ───> Independente
STORY-267 (UX polish) ──────────-> Independente
```
Stories 264-267 podem ser executadas em paralelo.

### Phase C: Verificacao Final
- Full test suites (backend + frontend)
- Manual testing: signup, billing, error states
- Verificacao 404 acentos, error boundaries

## Documentos de Referencia

- `docs/prd/technical-debt-assessment.md` — Assessment final
- `docs/reports/TECHNICAL-DEBT-REPORT.md` — Relatorio executivo
- `docs/reviews/qa-review.md` — Test requirements e acceptance criteria
- `docs/reviews/db-specialist-review.md` — Validacao DB
- `docs/reviews/ux-specialist-review.md` — Validacao UX
- `docs/architecture/system-architecture.md` — Arquitetura do sistema

---

*Criado por @pm durante Fase 10 do SmartLic Brownfield Discovery.*
