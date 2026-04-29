# RBAC-ORG-001: Enforce Organization Roles em 8 Endpoints `routes/organizations.py`

**Priority:** P1
**Effort:** S-M (2-3 dias)
**Squad:** @dev + @architect
**Status:** Ready
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

- [ ] Confirmar `organization_members.role` enum atual via psql
- [ ] Se diferente de Q1: `ALTER TYPE org_role_enum` migration + paired down.sql

### AC2: FastAPI dependency `require_org_role`

- [ ] `backend/dependencies/org_auth.py` (novo):
  ```python
  from enum import Enum
  class OrgRole(str, Enum):
      OWNER = "owner"
      MEMBER = "member"
      VIEWER = "viewer"
  
  async def require_org_role(min_role: OrgRole):
      async def dependency(
          org_id: UUID,
          user_id: UUID = Depends(require_auth),
          sb = Depends(get_supabase),
      ) -> OrgRole:
          # SELECT role FROM organization_members WHERE org_id=$1 AND user_id=$2
          # If role rank < min_role rank → HTTP 403
          ...
      return dependency
  ```
- [ ] Hierarchy: owner > member > viewer

### AC3: Apply em 8 endpoints

- [ ] `POST /v1/organizations` — create (no role required, owner self-assigned)
- [ ] `POST /v1/organizations/{id}/invite` — `require_org_role(OrgRole.OWNER)`
- [ ] `POST /v1/organizations/{id}/accept` — invitee (auth-only, no role check)
- [ ] `PATCH /v1/organizations/{id}` — `require_org_role(OrgRole.OWNER)`
- [ ] `DELETE /v1/organizations/{id}` — `require_org_role(OrgRole.OWNER)`
- [ ] `GET /v1/organizations/{id}/members` — `require_org_role(OrgRole.MEMBER)`
- [ ] `POST /v1/organizations/{id}/leave` — self (auth-only)
- [ ] `PATCH /v1/organizations/{id}/members/{member_id}` (role update) — `require_org_role(OrgRole.OWNER)`

### AC4: Tests cross-product

- [ ] `test_rbac_org.py`: 3 roles × 8 endpoints = 24 cases
- [ ] Each case: setup user with role X, call endpoint Y, assert status (200 if allowed, 403 if not)
- [ ] Edge: user not in org → 403/404

### AC5: Frontend handle 403

- [ ] `frontend/app/organizations/page.tsx` (se existir) graceful 403 message
- [ ] Hide UI buttons baseado em role (avoid 403 surprises)

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

## Dev Notes

- `routes/organizations.py` (Module 13 Reversa code-analysis)
- `auth.py:require_auth` pattern de dependency injection
- RLS policies em `organization_members` mantêm 2ª camada defense (mesmo se dependency falha, RLS bloqueia)

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
