# Epic: Resolucao de Debitos Tecnicos v2 — SmartLic v0.5

## Metadados
- **ID:** EPIC-DEBT-V2
- **Owner:** @architect + @pm
- **Status:** PLANNED
- **Prioridade:** Alta
- **Esforco Total:** ~196h
- **Custo Estimado:** R$29.400 (R$150/h)
- **Timeline:** 12 semanas (6 sprints de 2 semanas)
- **Data:** 2026-03-30
- **Fonte:** `docs/prd/technical-debt-assessment.md` (FINAL v2.0, 45 debitos, 8 fases de auditoria)
- **Supersedes:** `epic-technical-debt.md` (v1.0, 54 items — assessment re-validado, 6 debitos removidos como ja resolvidos)

---

## Objetivo

Resolver os 45 debitos tecnicos identificados na auditoria formal do SmartLic v0.5, conduzida em 8 fases por @architect, @data-engineer, @ux-design-expert e @qa. O objetivo e reduzir riscos de producao, acelerar a velocidade de desenvolvimento em ate 30%, melhorar acessibilidade para conformidade WCAG 2.1 AA, e preparar a plataforma para crescimento comercial pos-trial.

**Justificativa de negocio:**
- Custo de resolver: R$29.400
- Custo de NAO resolver (risco acumulado 12 meses): R$180.000 — R$350.000
- ROI estimado: 6:1 a 12:1
- Cada semana de atraso aumenta risco de instabilidade e reduz velocidade de entrega de features

---

## Escopo

### Incluido
- 45 debitos identificados: 15 backend/sistema, 12 database, 18 frontend/UX
- 2 criticos (P0), 8 altos (P1), 16 medios (P2), 19 baixos (P3)
- 6 sprints de resolucao + backlog oportunistico
- Decomposicao de 5 modulos monoliticos (>2000 LOC cada)
- Rollback scripts para tabelas criticas do banco
- Auditoria de acessibilidade expandida (5 → 15 paginas)
- Feature flag governance unificada backend + frontend
- Landing page RSC islands (LCP de 3.5s → <2.5s)

### Fora de Escopo
- Novas funcionalidades de produto (features)
- Migracoes de infraestrutura (Railway → outro provider)
- Reescrita completa de modulos (apenas decomposicao)
- Squash de migrations (desaconselhado pelo @data-engineer)
- Resolucao do SIGSEGV de forma definitiva (requer upstream fix do cryptography)
- Areas de observacao futura identificadas pelo @qa (monitoring calibracao, worker health check, rate limiting calibracao)

---

## Criterios de Sucesso

| Metrica | Baseline Atual | Meta |
|---------|---------------|------|
| Maior arquivo backend (LOC) | 4.105 (filter/core.py) | < 1.500 |
| Modulos > 2.000 LOC | 5 | <= 2 |
| Paginas auditadas WCAG | 5 / 22 | 15 / 22 |
| Landing page LCP (mobile 4G) | ~3.5s | < 2.5s |
| Feature flags com teste on/off | ~80% | 100% |
| Testes backend | 5.131+ | 5.300+ |
| Testes frontend | 2.681+ | 2.750+ |
| Tabelas criticas com rollback | 0 / 5 | 5 / 5 |
| JSONB Size Governance | ~93% | 100% |
| Cognitive load score (busca) | 7/10 (alto) | 4/10 (medio) |

---

## Stories

| ID | Titulo | Sprint | Esforco | Prioridade | Status |
|----|--------|--------|---------|------------|--------|
| [DEBT-200](story-DEBT-200-quick-wins-sprint1.md) | Quick Wins — Acessibilidade, Cleanup e Governanca DB | Sprint 1 | 14h | P2-P3 | PLANNED |
| [DEBT-201](story-DEBT-201-filter-decomposition.md) | Decomposicao do Monolito filter/core.py (4.105 LOC) | Sprint 2 | 22h | P0 | PLANNED |
| [DEBT-202](story-DEBT-202-frontend-structural.md) | Frontend Estrutural — Landing RSC + useSearchOrchestration + ViabilityBadge | Sprint 3 | 26h | P0-P1 | PLANNED |
| [DEBT-203](story-DEBT-203-resilience-cache-rollback.md) | Resiliencia — Cache Decomposition + DB Rollback Scripts | Sprint 4 | 26h | P1 | PLANNED |
| [DEBT-204](story-DEBT-204-backend-wave2-banners.md) | Backend Wave 2 + Banner System — pncp_client + cron/jobs + BannerStack | Sprint 5 | 30h | P1-P2 | PLANNED |
| [DEBT-205](story-DEBT-205-a11y-feature-flags.md) | Acessibilidade Avancada + Feature Flag Governance | Sprint 6 | 28h | P2 | PLANNED |
| [DEBT-206](story-DEBT-206-security-sigsegv.md) | Seguranca — Monitoramento cryptography/SIGSEGV | Sprint 6 | 4h | P0 | PLANNED |
| [DEBT-207](story-DEBT-207-backlog-db-governance.md) | Backlog Oportunistico — Database Governance e Naming | Backlog | 16.5h | P3 | PLANNED |
| [DEBT-208](story-DEBT-208-backlog-backend-cleanup.md) | Backlog Oportunistico — Backend Schema e Migrations | Backlog | 6h | P2-P3 | PLANNED |
| [DEBT-209](story-DEBT-209-backlog-frontend-polish.md) | Backlog Oportunistico — Frontend Polish e Design System | Backlog | 17h | P3 | PLANNED |
| [DEBT-210](story-DEBT-210-backlog-db-performance.md) | Backlog Oportunistico — Database Performance Optimization | Backlog | 10h | P2-P3 | PLANNED |

**Esforco total stories: ~199.5h** (inclui margem para testes e integracao)

---

## Riscos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Regressao em filter/core.py (283 testes) | Media | Alto | Facade pattern + backward-compat imports |
| Regressao em search_cache.py (186 testes) | Media | Alto | Helper de mock centralizado antes de decompor |
| Regressao em useSearchOrchestration (618 LOC) | Media | Alto | Snapshot tests de props + E2E search-flow |
| Landing RSC hydration quebrada | Baixa | Medio | Branch separada + Lighthouse CI |
| Rollback scripts corrompem dados | Baixa | Critico | Testar em staging com dados sinteticos |
| Combinacoes de feature flags nao testadas | Alta | Medio | Criar test_feature_flag_matrix.py |
| Cryptography CVE na faixa 46.x | Baixa | Alto | Monitoramento periodico de CVEs |

---

## Dependencias

### Externas
- Supabase PITR (verificar se disponivel no plano atual — impacta criticidade de rollback scripts)
- Next.js 16 RSC behavior (consultar docs antes de converter landing page)
- cryptography upstream fix para >=47.0

### Internas (cadeia de resolucao)
- DEBT-SYS-007 bloqueia DEBT-SYS-001 (resolver duplicacao filter_*.py antes de decompor)
- DEBT-FE-004 bloqueia DEBT-FE-003 (consolidar banners antes de adicionar aria-live)
- DEBT-FE-013 depende de todos os debitos a11y anteriores
- DEBT-SYS-009 + DEBT-FE-008 devem ser resolvidos juntos (feature flag governance unificada)

---

## Timeline Visual

```
Semana  1-2   Sprint 1: Quick Wins (14h) .............. DEBT-200
Semana  3-4   Sprint 2: Filter Decomposition (22h) .... DEBT-201
Semana  5-6   Sprint 3: Frontend Structural (26h) ..... DEBT-202
Semana  7-8   Sprint 4: Resiliencia (26h) ............. DEBT-203
Semana  9-10  Sprint 5: Backend Wave 2 (30h) .......... DEBT-204
Semana 11-12  Sprint 6: A11y + Governance (28h+4h) .... DEBT-205 + DEBT-206
Continuo      Backlog Oportunistico (~50h) ............. DEBT-207 a DEBT-210
```

---

## Referencias

- [Assessment Tecnico Completo](../prd/technical-debt-assessment.md) — Inventario detalhado dos 45 debitos
- [Relatorio Executivo](../reports/TECHNICAL-DEBT-REPORT.md) — Sumario para stakeholders
- [QA Review](../reviews/qa-review.md) — Gate de qualidade com analise de risco de regressao

---

*Criado por @pm (Morgan) — Phase 10, Brownfield Discovery Workflow. 2026-03-30.*
