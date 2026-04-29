# ADR: Organization RBAC Enforcement

**Status:** Accepted
**Date:** 2026-04-28
**Decisão:** User via AskUserQuestion
**Story:** [RBAC-ORG-001](../stories/2026-04/RBAC-ORG-001-enforce-org-role-dependency.story.md)

---

## Context

`organizations` + `organization_members` tables existem. `routes/organizations.py` 8 endpoints. **Roles não enforce** em endpoints (review-report.md Gap-1). Multi-tenant LGPD rachado: member pode invocar admin endpoint, viewer pode invite.

## Decision

### Enum role canonical (3-tier hierárquico)

```
owner > member > viewer
```

- **owner**: full control (invite, update, delete org, role-change)
- **member**: CRUD operations (read, write data; read members)
- **viewer**: read-only access

### Mín role per endpoint cluster

| Endpoint | Mín role | Notes |
|----------|---------|-------|
| `POST /v1/organizations` | none (auth-only) | Creator vira owner self-assigned |
| `POST /v1/organizations/{id}/invite` | **OWNER** | Owner controla membership |
| `POST /v1/organizations/{id}/accept` | invitee (auth-only) | Convidado aceita |
| `PATCH /v1/organizations/{id}` | **OWNER** | Org config update |
| `DELETE /v1/organizations/{id}` | **OWNER** | Destructive op |
| `GET /v1/organizations/{id}/members` | **MEMBER** | viewer também via separate endpoint? — defer |
| `POST /v1/organizations/{id}/leave` | self (auth-only) | Qualquer role exceto único owner |
| `PATCH /v1/organizations/{id}/members/{member_id}` (role-change) | **OWNER** | Promote/demote member |

### Default role on accept invite

**Inviter define** — POST /invite body `{email: "...", role: "member" | "viewer"}`. Owner escolhe role do convidado.

### Self-service "leave"

**Qualquer role pode** exceto único owner:
- Owner com OUTROS owners no org → pode leave
- Owner único + outros members existem → BLOQUEIA leave (deve transfer ownership ou delete org)
- Owner único + zero outros members → leave + auto-delete org (graceful)

## Consequences

### Positivas
- LGPD compliance multi-tenant (security gap fixado)
- Granular control: viewer = read-only para clientes consultoria (cobre GV-014 conditional)
- Inviter define role = flexibilidade owner

### Negativas
- 3-tier adds complexidade vs 2-tier (mais test cases: 24 = 3 roles × 8 endpoints)
- Single-owner constraint pode confundir users esperando multi-owner natural

### Implementação (RBAC-ORG-001)

- FastAPI dependency `require_org_role(min_role: OrgRole)` em `backend/dependencies/org_auth.py`
- Hierarchy: owner=3 > member=2 > viewer=1; check `user.role.rank >= min_role.rank`
- Migration ALTER TYPE `org_role_enum` se diferente atualmente (Phase 0 verify)
- Frontend hide buttons baseado em role (avoid 403 surprise)
- Tests: 24 cases (3 roles × 8 endpoints) + edge (user not in org → 403/404)

## Monitoring

- Audit log de role-change (separate STORY future)
- Sentry alert em 403 spike (signal de UI desync)

## Revision

ADR canonical até policy mudar. Role enum mudanças requerem migration + new ADR.
