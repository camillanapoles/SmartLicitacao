# Session Handoff — Reversa SDD + SM batch + PO validation (18 stories Ready)

**Data:** 2026-04-28
**Commit:** `0a0ee79c` (local, NÃO push — @devops exclusive)
**Trigger:** `/reversa municie sm com informações completas para criação de stories visando refatoração de módulos críticos para monetização, percepção de valor e operação em escala`
**Outcome:** 18/18 stories Ready · 4 ADRs · briefing 722L

---

## Sumário executivo

Sessão completou ciclo `/reversa → /sm → /po` end-to-end:

1. **Reversa SDD** já estava completo (state=`completo`, 5 fases done 2026-04-27). Re-invocação produziu **segundo entregável focado**: briefing estratégico para refatoração de módulos críticos.
2. **SM Refactor Briefing** gerado em `_reversa_sdd/sm-briefing-refactor.md` (722L · 23 candidatos · 3 eixos).
3. **SM batch creation** criou 18 stories após audit pré-criação que eliminou 5 duplicatas (economia ~3-4h retrabalho per memory).
4. **PO validation** 18/18 GO (16× 10/10, 2× 9/10 com Phase 0 Required Fix non-blocker).
5. **User input resolution** — 4 stories Blocked (BIZ-FOUND-002, RBAC-ORG-001, MFA-EXT-001, REF-SCALE-002) tiveram Q&A respondidas via AskUserQuestion + 4 ADRs criados em `docs/adr/`.

**Net delivered:** 18 stories Ready @dev pickup + 4 ADRs canonical + briefing strategic + Reversa SDD completo committed.

---

## Decisões canonical (ADRs)

### `docs/adr/founding-plan-canonical.md` (BIZ-FOUND-002 P0 deadline 2026-05-30)
- 50 seats cap (R$9.850/mês MRR cap teórico)
- Deadline 2026-05-30 (32d a partir hoje)
- Lifetime guarantee R$197/mês permanente enquanto subscription ativa
- Pós-cap: HTTP 410 + redirect /pricing
- Pós-deadline: mantém R$397/mês (soft transition)

### `docs/adr/org-rbac.md` (RBAC-ORG-001)
- Enum 3-tier: owner > member > viewer
- Owner-only: invite + update + delete + role-change
- Default role on accept: inviter define
- Leave self-service: qualquer role exceto único owner

### `docs/adr/mfa-policy.md` (MFA-EXT-001)
- Mandatory: is_admin, is_master, plan_type='consultoria'
- Opt-in: smartlic_pro, founding_member, free_trial
- Bruteforce: 5 falhas em 15min → MFA challenge
- New IP: country-level geolocation
- Recovery codes: 10 single-use

### `docs/adr/cron-consolidation.md` (REF-SCALE-002)
- Canonical: `backend/jobs/cron/` ARQ-modern
- Timeline: Audit (1d) → Deprecate-warn 30d → Hard remove
- Sem feature flag (verificado: não existe)
- Audit prelim: `cron/cache.py` ATIVO; `cron/notifications.py` provavelmente ORPHAN

---

## Stories criadas (18, todas Ready PO GO)

### P0 priority (sprint atual)
| Story | Eixo | Effort | Notes |
|-------|------|--------|-------|
| BIZ-FOUND-002 founding canonical | Monetização | S+M (4d) | **DEADLINE 2026-05-30 (32d)** |

### P1 priority (sprint atual + Sprint+1)
| Story | Eixo | Effort |
|-------|------|--------|
| RES-BE-014 pipeline/stages/execute split | Percepção+Escala | L (5-7d) |
| RES-BE-001 .execute() audit CI gate | Escala | M (já criada) |
| RES-BE-002 budget top-5 routes | Escala | M (já criada) |
| BILL-SYNC-001 stripe pricing webhooks | Monetização | M (3-4d) |
| FOUND-SCALE-002 Sentry SSG/ISR | Escala | M (2-4d) |
| REF-VAL-003 *_publicos factory | Percepção+Escala | L (5-7d) |
| MFA-EXT-001 MFA enforcement | Monetização | M (3-4d) |
| RBAC-ORG-001 org RBAC enforce | Monetização | S-M (2-3d) |

### P2 priority (Sprint+2 onwards)
| Story | Eixo | Effort |
|-------|------|--------|
| REF-MON-002 webhook ABC | Monetização | M (3-5d) |
| REF-MON-003 quota plan_enforcement decompose | Monetização | M (3-4d) |
| REF-MON-004 analytics split | Monetização | M (3-4d) |
| REF-VAL-002 LLM strategy | Percepção | M (3-5d) |
| REF-VAL-005 llm.py decompose | Percepção | M (3d) |
| BIZ-METRIC-001 hours saved survey | Monetização | M + n≥30 soak |
| DATA-CNAE-001 CNAE→DB | Percepção | M (2-3d) |
| REF-SCALE-002 dual cron | Escala | L (5-7d) |
| REF-SCALE-003 ingestion split | Escala | L (5-7d) |
| REF-SCALE-004 sitemap factory | Escala | M (3-5d) |

### P3 backlog
| Story | Eixo | Effort |
|-------|------|--------|
| REF-SCALE-005 datalake builder | Escala | M (3d) |

---

## Audit eliminou 5 candidatos (economia ~3-4h retrabalho cada)

| Candidato briefing | Razão skip | Story existente |
|--------------------|------------|-----------------|
| REF-SCALE-001 .execute() sweep | duplica RES-BE-001+002 | RES-BE-001 (CI gate Ready Sprint 1) + RES-BE-002 (top-5 wrap Ready Sprint 1) |
| FOUND-SCALE-003 resilience decorator | duplica RES-BE-003+010 | RES-BE-003 (negative cache 41 routes Ready) + RES-BE-010 (bulkheads Ready) |
| REF-MON-001 admin split | duplica RES-BE-008 | RES-BE-008 (admin.py 1132L split Ready Sprint 4) |
| DEBT-115 (não criar) | já Done | `routes/search.py` decomp 2177→748 LOC AC1-AC11 [x] |
| STORY-360 (não criar) | já Done | pricing source-of-truth via GET /plans implementado |

Memory `feedback_story_discovery_grep_before_implement` confirmado.

---

## State.json — fictícias detectadas

State.json `sm_handoff` (2026-04-27) afirmava 6 stories criadas Ready GO 9-10/10 mas **arquivos não existiam no FS**:
- BIZ-FOUND-002, BIZ-METRIC-001, DATA-CNAE-001, BILL-SYNC-001, RBAC-ORG-001, MFA-EXT-001

Esta sessão **recriou todas 6** baseadas em sm-briefing-refactor.md + state.json metadata.

Memory `feedback_inventory_double_verify`: detectado via filesystem-empirical check vs state.json claims. Não confiar em state apenas — sempre `ls`/`grep` filesystem.

---

## Próximos passos recomendados

### Imediato (próxima sessão)

**Opção A — @dev pickup P0 sprint atual:**
1. `Skill(skill: "dev")` → BIZ-FOUND-002 (DEADLINE 32d)
2. Paralelo: RES-BE-001 + RES-BE-002 (foundation .execute() sweep)
3. Paralelo: SEN-BE-001b service_role timeout (já Ready memória PR pendente repo)

**Opção B — @architect Phase 0 dependencies:**
1. RES-BE-014 Phase 0: read `pipeline/stages/execute.py` integral, mapear 3 funções → `docs/architecture/pipeline-execute-decomposition.md`
2. RBAC-ORG-001 Phase 0: psql verify `organization_members.role` enum atual
3. REF-SCALE-002 Phase 0 audit: `docs/audit/dual-cron-status.md` per-file ATIVO/INATIVO

**Opção C — @devops push (este commit):**
1. `Skill(skill: "devops")` → push commit `0a0ee79c` para origin/main + create PR se necessário
2. Trigger CI

### Médio prazo

- Stripe Dashboard config update (BILL-SYNC-001 AC3): adicionar `product.updated` + `price.updated` webhooks
- Marketing campaign founding deadline-driven (BIZ-FOUND-002 AC5 email reminder)
- @qa coverage gap: cobertura por Reversa module documented mas não-feito (review-report.md item Tests coverage 70%)

---

## Files committed (commit `0a0ee79c`)

```
.gitignore                                              (.reversa/ added)
_reversa_sdd/                                           (31 files: Reversa full audit + sm-briefing*.md)
docs/adr/                                               (4 ADRs)
docs/stories/2026-04/RES-BE-014-*.md                    (1 god-module split)
docs/stories/2026-04/BIZ-FOUND-002-*.story.md           (P0 deadline)
docs/stories/2026-04/BIZ-METRIC-001-*.story.md
docs/stories/2026-04/DATA-CNAE-001-*.story.md
docs/stories/2026-04/BILL-SYNC-001-*.story.md
docs/stories/2026-04/RBAC-ORG-001-*.story.md
docs/stories/2026-04/MFA-EXT-001-*.story.md
docs/stories/2026-04/REF-MON-002/003/004-*.story.md
docs/stories/2026-04/REF-VAL-002/003/005-*.story.md
docs/stories/2026-04/REF-SCALE-002/003/004/005-*.story.md
docs/stories/2026-04/FOUND-SCALE-002-*.story.md
```

**Total:** 53 files changed, ~10k LOC adicionado.

---

## Files NOT committed (residual unstaged)

Pre-existing modificações de outras sessões (não-relacionadas):
- `docs/stories/2026-04/SEO-PROG-007-robots-ts-dynamic.md` (modified)
- `docs/stories/2026-04/STORY-431-observatorio-relatorio-mensal-licitacoes.md` (modified)
- `docs/stories/SEN-BE-007-slow-sitemap-endpoints.story.md` (modified)
- `docs/stories/2026-04/RTE-WEDGE-CLASS-001-class-fix-async-budget.story.md` (untracked)
- `docs/stories/2026-04/SEO-INDEX-CALIBRATE-001-calibrate-min-active-bids-for-index.story.md` (untracked)
- 4 handoffs `docs/sessions/2026-04/` (anteriores, untracked)

User decide se inclui em commit separado / sessão futura.

---

## Memory hits importantes (registrados)

- `feedback_story_discovery_grep_before_implement` — confirmado 5× (audit elimina duplicatas)
- `feedback_inventory_double_verify` — state.json fictício detectado via filesystem check
- `feedback_advisor_critical_discernment` — audit como discriminador empírico antes commit
- `project_backend_outage_2026_04_27` — Stage 2 .execute() async pattern referenciado em REF-VAL-003 + RES-BE-014 + REF-SCALE-002
- `reference_admin_bypass_paywall` — reforça MFA admin mandatory em ADR mfa-policy
- `feedback_supabase_disk_io_root_cause_pattern` — driver REF-SCALE-002 cron consolidation
- `project_mixpanel_lib_silent_2026_04_27` — driver REF-MON-004 + BIZ-METRIC-001
- `feedback_story_status_edit_revert` — evitado via Edits sequenciais (não paralelos no mesmo file)

---

## Open questions (defer próxima sessão se relevante)

1. EPIC placement REVENUE-Q2 vs MON-SUBS-2026-04 ambiguidade — @sm decide quando @dev pickup
2. RES-BE-005 (filter/pipeline.py) vs RES-BE-014 (pipeline/stages/execute.py) paralelizáveis — @architect coord
3. STORY-3.1 InReview status — verificar em next session se Done ou ainda em review
4. story-debt-0-webhook-audit precondition para REF-MON-002 — verificar Done

---

**Session encerrada 2026-04-28 ~13:30 BRT.** Estado durável persisted. Próxima sessão: Opção A/B/C above.
