# RBAC-ORG-001: Enforce Organization Roles em 8 Endpoints `routes/organizations.py`

**Priority:** P1
**Effort:** S-M (2-3 dias)
**Squad:** @dev + @architect
**Status:** InProgress
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/) ou [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 2 (após user input)
**Dependências bloqueadoras:** GV-014 Ready conditional (consultoria-client-readonly) · ADR enum decision (USER)

---

## Contexto

`organizations` + `organization_members` tables existem. `routes/organizations.py` 8 endpoints (Reversa code-analysis Module 13). **Mas roles (owner/member/viewer?) não enforce** em endpoints (review-report.md Gap-1).

GV-014 Ready conditional Sprint 3 trata read-only consultoria mas NÃO enforce enum granular. Multi-tenant LGPD rachado: member pode invocar admin endpoint (e.g., delete org), viewer pode invite (no enforcement).

---

## User Input — RESPONDIDO 2026-04-28

| # | Pergunta | Resposta |
|---|----------|----------|
| Q1 | Enum role | **owner / member / viewer** (3-tier) |
| Q2 | Endpoints OWNER mín | **invite + update + delete + role-change** |
| Q3 | Default role accept invite | **Inviter define** (POST /invite body inclui role: "member" ou "viewer") |
| Q4 | Self-service leave | **Qualquer role exceto único owner** (owner leave só se houver outro owner OU org=1 member auto-delete) |

Hierarchy: owner > member > viewer. Detalhes em ADR `docs/adr/org-rbac.md` (criado).

---

## Acceptance Criteria (pós-input)

### AC1: Enum confirmation + migration (se needed)

- [x] Confirmar `organization_members.role` enum atual via psql
- [x] DB usa TEXT CHECK constraint (não PG enum). `ALTER TYPE org_role_enum` não aplicável.
  - Old CHECK: `('owner', 'admin', 'member')` — Migration `20260501000000` swaps `admin`→`viewer`.
  - Zero admin rows em prod na data de implementação (2026-05-01).
  - `supabase/migrations/20260501000000_rbac_org_001_role_viewer.sql` + paired `.down.sql`

### AC2: FastAPI dependency `require_org_role`

- [x] `backend/dependencies/org_auth.py` criado com `OrgRole` enum + factory `require_org_role`
- [x] Hierarchy: owner (3) > member (2) > viewer (1) via `_ROLE_RANK` dict
- [x] Uses `_run_with_budget(asyncio.to_thread(_query), budget=10s)` (RES-BE-016 pattern)
- [x] 403 para não-membro (empty data) e para rank insuficiente

### AC3: Apply em 8 endpoints

**NOTA @po:** 5 endpoints da AC3 original (PATCH /{id}, DELETE /{id}, GET /{id}/members,
POST /{id}/leave, PATCH /{id}/members/{id}) não existem em `routes/organizations.py`.
Implementação aplicada nos 8 endpoints EXISTENTES. AC3 precisa ser corrigida por @po.

- [x] `GET /v1/organizations/me` — auth-only (sem role check)
- [x] `POST /v1/organizations` — auth-only (owner self-assigned)
- [x] `GET /v1/organizations/{id}` — `require_org_role(OrgRole.MEMBER)`
- [x] `POST /v1/organizations/{id}/invite` — `require_org_role(OrgRole.OWNER)`
- [x] `POST /v1/organizations/{id}/accept` — auth-only (invitee)
- [x] `DELETE /v1/organizations/{id}/members/{uid}` — `require_org_role(OrgRole.OWNER)`
- [x] `GET /v1/organizations/{id}/dashboard` — `require_org_role(OrgRole.OWNER)`
- [x] `PUT /v1/organizations/{id}/logo` — `require_org_role(OrgRole.OWNER)`

### AC4: Tests cross-product

- [x] `backend/tests/test_rbac_org.py`: 29 cases (24 matrix + 5 non-member edge)
- [x] Each case: mock auth + mock dep supabase with role X, assert status
- [x] Edge: user not in org → 403 (5 endpoints × 1 non-member case)
- [x] `backend/tests/test_organizations.py`: 11 existing tests updated for new dep mock

### AC5: Frontend handle 403

- [x] `frontend/hooks/useOrganization.ts`: 403 → mensagem "Acesso negado: sua função não permite..."
- [x] `frontend/app/conta/equipe/page.tsx`: `isOwnerOrAdmin` = `role === "owner"` (botões invite/remove ocultos)
- [x] Types atualizados: `"owner" | "member" | "viewer"` (removido `"admin"`)
- [x] `ROLE_LABELS/COLORS` atualizados com `viewer`

---

## Scope

**IN:** dependency + apply 8 endpoints + tests + frontend handle 403
**OUT:** Audit log de actions (separate STORY) · super-admin override (separate)

---

## Definition of Done

- [ ] User Q1-Q5 respondidas em ADR `docs/adr/org-rbac.md`
- [ ] Dependency funcional + 24 test cases pass
- [ ] Suite passa
- [ ] @po validation GO

---

## File List

| File | Action | Notes |
|------|--------|-------|
| `backend/dependencies/org_auth.py` | NEW | OrgRole enum + require_org_role factory |
| `backend/routes/organizations.py` | MOD | Imports + 5 endpoints get require_org_role Depends |
| `backend/services/organization_service.py` | MOD | 4× `not in ("owner", "admin")` → `!= "owner"` |
| `supabase/migrations/20260501000000_rbac_org_001_role_viewer.sql` | NEW | CHECK admin→viewer + RLS update |
| `supabase/migrations/20260501000000_rbac_org_001_role_viewer.down.sql` | NEW | Rollback migration |
| `backend/tests/test_rbac_org.py` | NEW | 29 RBAC test cases |
| `backend/tests/test_organizations.py` | MOD | 11 tests updated for new dep mock |
| `frontend/hooks/useOrganization.ts` | MOD | Role types + 403 graceful message |
| `frontend/app/conta/equipe/page.tsx` | MOD | Role types, ROLE_LABELS/COLORS, isOwnerOrAdmin→owner |

## Dev Notes

- `routes/organizations.py` (Module 13 Reversa code-analysis)
- `auth.py:require_auth` pattern de dependency injection
- RLS policies em `organization_members` mantêm 2ª camada defense (mesmo se dependency falha, RLS bloqueia)
- AC3 mismatch: story lista 5 endpoints inexistentes — scope aplicado aos 8 existentes; @po deve corrigir AC3

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| Existing user (member) perde acesso pós-deploy | Migration: ensure existing all members have valid role; default 'member' |
| Owner role único (single-owner constraint) viola flow multi-owner futuro | Q5 confirma: para agora, single owner; multi-owner = future story |

**Rollback:** revert dependency apply em routes; volta ao estado pré-RBAC (insecure mas funcional).

---

## Dependencies

**Entrada:** User Q1-Q5
**Saída:** habilita GV-014 (consultoria-client-readonly) full enforcement

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO
**Score:** 9/10

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Enforce org roles em 8 endpoints explícito. |
| 2 | Complete description | ✗ | Q1-Q4 respondidos, mas Phase 0 verify enum atual via psql ainda Required Fix antes de migration AC1 (defensivo). |
| 3 | Testable acceptance criteria | ✓ | 5 ACs com 24 test cases (3 roles × 8 endpoints). |
| 4 | Well-defined scope | ✓ | OUT exclude audit log + super-admin override. |
| 5 | Dependencies mapped | ✓ | GV-014 Ready conditional + ADR criado. |
| 6 | Complexity estimate | ✓ | S-M (2-3d). |
| 7 | Business value | ✓ | LGPD multi-tenant security gap. |
| 8 | Risks documented | ✓ | Migration phase: ensure existing members default 'member'. |
| 9 | Criteria of Done | ✓ | 4 itens. |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD ou EPIC-RES-BE. |

### Required Fix (não-blocker para Ready)

- [ ] Phase 0 @architect verify enum `organization_members.role` atual via psql ANTES de PR 1 commit 1. Se diferir de `owner|member|viewer`, atualizar AC1 migration.

Status: Blocked → Ready (com gate em Phase 0 conforme RES-BE-005 padrão).

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada — recria fictícia state.json sm_handoff. Bloqueada user input Q1-Q5. Origem: `_reversa_sdd/sm-briefing-refactor.md` + sm-briefing.md sec.2.3 + review-report.md Gap-1. | @sm (River) |
| 2026-04-28 | 1.1 | User input Q1-Q4 respondidas: enum owner/member/viewer, owner=invite+update+delete+role-change, default=inviter define, leave=qualquer role exceto único owner. ADR `docs/adr/org-rbac.md` criado. PO validation: GO (9/10) com Phase 0 enum verify Required Fix. Status: Blocked → Ready. | @po (Pax) |
| 2026-05-01 | 1.2 | Implementação @dev. Phase 0 confirmado: TEXT CHECK (não PG enum), zero admin rows. Migration 20260501000000 criada. `backend/dependencies/org_auth.py` + dependency aplicada em 5 endpoints. Service admin→owner. 29 testes novos + 11 existentes atualizados. Frontend types + 403 graceful. AC3 mismatch documentado (5 endpoints inexistentes). Status: Ready → InProgress. | @dev (Dex) |
