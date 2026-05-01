# Spec: Auth & OAuth

> Spec executável (SDD) gerada pelo **Reversa Writer** em 2026-04-27
> Confiança: 🟢 CONFIRMADO

## Component
- **ID**: `auth-oauth`
- **Path**: `backend/auth.py`, `backend/authorization.py`, `backend/oauth.py`, `backend/routes/auth_*.py`, `frontend/middleware.ts`, `frontend/app/{login,signup,auth,recuperar-senha}/`, `frontend/app/api/auth/`

## Purpose

Autenticação Supabase JWT (HS256→ES256 transition, JWKS dinâmico) com cache 2-tier. OAuth Google para Sheets export (Fernet-encrypted refresh tokens). Authorization roles (admin/master). Frontend middleware Next.js com CSP enforcing + 8 protected routes. MFA recovery codes.

## Invariants

1. **3-strategy JWT validation cascade**: JWKS ES256 (preferred) > PEM static > HS256 (legacy fallback)
2. **Cache 2-tier**: L1 LRU 60s (1000 entries) + L2 Redis 5min
3. **CSRF state em OAuth** — random URL-safe token, persistido em Redis 10min, validado no callback
4. **Refresh token Fernet AES-256** — never stored plaintext
5. **Defense-in-depth roles** — env `ADMIN_USER_IDS` whitelist + DB `profiles.is_admin/is_master` flag fallback
6. **Frontend middleware CSP hash-based** — bloqueia inline scripts não-listados

## Functional Requirements

- **FR-1**: `require_auth(token)` valida JWT, retorna user dict `{id, email, plan_type, role, ...}`
- **FR-2**: `POST /v1/auth/signup` cria user + envia welcome email + telemetry signup_completed
- **FR-3**: `GET /v1/auth/check-email`, `/v1/auth/check-phone` — public availability check
- **FR-4**: `POST /v1/auth/validate-signup-email` — pre-signup validation
- **FR-5**: `POST /v1/auth/resend-confirmation` — magic link resend
- **FR-6**: `GET /v1/auth/status` — current session info
- **FR-7**: OAuth Google flow: `GET /api/auth/google` (redirect to authorize) → `GET /api/auth/google/callback` (exchange code for tokens, encrypt refresh, save) → `DELETE /api/auth/google` (revoke)
- **FR-8**: MFA `GET /mfa/status` + `POST /mfa/{recovery-codes,verify-recovery,regenerate-recovery}`
- **FR-9**: `check_user_roles(user_id)` retorna `(is_admin, is_master)`
- **FR-10**: `has_master_access(user_id)` async helper

## Non-Functional Requirements

- **NFR-1**: JWT validation p95 <50ms (cache hit), <200ms (JWKS fetch)
- **NFR-2**: Cache invalidation manual via admin endpoint (signature change)
- **NFR-3**: OAuth callback p95 <2s (Google API roundtrip)
- **NFR-4**: 0 plaintext refresh tokens em DB ou logs

## Constraints

- **CON-1**: Supabase Auth gerencia password hashing (bcrypt) e SCA
- **CON-2**: Frontend middleware aplicado a 8 protected routes (`/buscar`, `/dashboard`, `/historico`, `/pipeline`, `/conta`, `/admin/*`, `/onboarding`, `/mensagens`)
- **CON-3**: Fernet key (`OAUTH_FERNET_KEY`) rotation NÃO implementado — rotacionar invalida todos refresh tokens
- **CON-4**: HS256 fallback supportado para legacy tokens; ES256 preferred

## Acceptance Criteria

- AC-1: JWT válido HS256 ou ES256 retorna user dict em <200ms
- AC-2: JWT inválido retorna 401 com `{error: "invalid_token"}`
- AC-3: OAuth flow completo: `/api/auth/google` → consent → callback → DB `user_oauth_tokens` row encrypted
- AC-4: Frontend `/buscar` sem auth redireciona para `/login?redirect=/buscar`
- AC-5: Admin endpoint sem `is_admin=true` retorna 403
- AC-6: MFA recovery code funcional para reset

## Errors

| Code | HTTP | Trigger |
|------|------|---------|
| `invalid_token` | 401 | JWT validation failed |
| `expired_token` | 401 | exp < now |
| `oauth_state_invalid` | 403 | CSRF state mismatch |
| `oauth_exchange_failed` | 502 | Google API error |
| `email_already_exists` | 409 | signup conflict |
| `mfa_recovery_invalid` | 401 | code wrong |
| `admin_required` | 403 | role missing |

## Code traceability

- `backend/auth.py:require_auth` — main auth dependency (FR-1)
- `backend/auth.py:_validate_jwt_3strategy` — JWKS > PEM > HS256
- `backend/auth.py:_get_jwks_client` cached
- `backend/authorization.py:check_user_roles, has_master_access, get_admin_ids, ErrorCode`
- `backend/oauth.py` — OAuth flow + Fernet
- `backend/routes/auth_check.py:126` — check-email, check-phone
- `backend/routes/auth_email.py:150` — validate-signup-email, resend-confirmation, status
- `backend/routes/auth_signup.py:293` — POST signup
- `backend/routes/auth_oauth.py:280` — Google OAuth 3 endpoints
- `backend/routes/mfa.py` — 4 endpoints
- `frontend/middleware.ts` — CSP + auth guard

## Dependencies

- `PyJWT`, `PyJWKClient` (cached JWKS)
- `cryptography.fernet` (refresh token encryption)
- `google-auth`, `google-auth-oauthlib` (OAuth flow)
- Supabase Auth (token issuer)
- Redis (state CSRF + cache L2)
- `user_oauth_tokens` table
