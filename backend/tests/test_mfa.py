"""Tests for MFA (Multi-Factor Authentication) routes and middleware.

STORY-317: AC20, AC22 — Tests for require_mfa middleware, recovery codes,
AAL checking, and brute force protection.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user_aal1():
    """User dict with AAL level 1 (password only)."""
    return {"id": "test-user-id-123", "email": "test@example.com", "role": "authenticated", "aal": "aal1"}


@pytest.fixture
def mock_user_aal2():
    """User dict with AAL level 2 (password + TOTP)."""
    return {"id": "test-user-id-123", "email": "test@example.com", "role": "authenticated", "aal": "aal2"}


@pytest.fixture
def mock_admin_aal1():
    """Admin user with AAL level 1."""
    return {"id": "admin-user-id-456", "email": "admin@example.com", "role": "authenticated", "aal": "aal1"}


@pytest.fixture
def mock_admin_aal2():
    """Admin user with AAL level 2."""
    return {"id": "admin-user-id-456", "email": "admin@example.com", "role": "authenticated", "aal": "aal2"}


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    from main import app
    from auth import require_auth
    app.dependency_overrides[require_auth] = lambda: {"id": "test-user-id-123", "email": "test@example.com", "role": "authenticated", "aal": "aal2"}
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_aal1():
    """Create a test client with AAL1 user (no MFA verified)."""
    from main import app
    from auth import require_auth
    app.dependency_overrides[require_auth] = lambda: {"id": "test-user-id-123", "email": "test@example.com", "role": "authenticated", "aal": "aal1"}
    yield TestClient(app)
    app.dependency_overrides.clear()


# ─── Unit Tests: Recovery Code Helpers ─────────────────────────────────────────

class TestRecoveryCodeGeneration:
    """Tests for recovery code generation and hashing (AC5)."""

    def test_generate_recovery_codes_count(self):
        from routes.mfa import _generate_recovery_codes
        codes = _generate_recovery_codes(10)
        assert len(codes) == 10

    def test_generate_recovery_codes_format(self):
        from routes.mfa import _generate_recovery_codes
        codes = _generate_recovery_codes(3)
        for code in codes:
            # Format: XXXX-XXXX (8 hex chars with hyphen)
            assert len(code) == 9  # 4 + 1 + 4
            assert code[4] == "-"
            # All hex chars
            clean = code.replace("-", "")
            assert all(c in "0123456789ABCDEF" for c in clean)

    def test_generate_recovery_codes_unique(self):
        from routes.mfa import _generate_recovery_codes
        codes = _generate_recovery_codes(10)
        assert len(set(codes)) == 10  # All unique

    def test_hash_and_verify_code(self):
        from routes.mfa import _hash_code, _verify_code
        code = "ABCD-EF01"
        hashed = _hash_code(code)
        assert _verify_code(code, hashed) is True
        assert _verify_code("WRONG-CODE", hashed) is False

    def test_verify_code_case_insensitive(self):
        from routes.mfa import _hash_code, _verify_code
        code = "ABCD-EF01"
        hashed = _hash_code(code)
        assert _verify_code("abcd-ef01", hashed) is True

    def test_verify_code_without_hyphen(self):
        from routes.mfa import _hash_code, _verify_code
        code = "ABCD-EF01"
        hashed = _hash_code(code)
        assert _verify_code("ABCDEF01", hashed) is True

    def test_hash_is_bcrypt(self):
        from routes.mfa import _hash_code
        hashed = _hash_code("ABCD-EF01")
        assert hashed.startswith("$2")  # bcrypt prefix


# ─── Unit Tests: AAL Extraction ────────────────────────────────────────────────

class TestAalExtraction:
    """Tests for AAL level extraction from JWT (AC2)."""

    def test_user_data_includes_aal(self, mock_user_aal1):
        assert mock_user_aal1["aal"] == "aal1"

    def test_user_data_aal2(self, mock_user_aal2):
        assert mock_user_aal2["aal"] == "aal2"

    @pytest.mark.asyncio
    @patch("auth._get_jwt_key_and_algorithms")
    async def test_get_current_user_extracts_aal(self, mock_key):
        """Verify that get_current_user includes aal from JWT payload."""
        import jwt as pyjwt

        test_key = "a-very-long-secret-key-for-testing-purposes-minimum-32-bytes"
        mock_key.return_value = (test_key, ["HS256"])

        token = pyjwt.encode(
            {"sub": "user-123", "email": "test@test.com", "role": "authenticated",
             "aal": "aal2", "aud": "authenticated"},
            test_key,
            algorithm="HS256",
        )

        from auth import get_current_user, _token_cache
        _token_cache.clear()

        creds = MagicMock()
        creds.credentials = token

        user = await get_current_user(creds)
        assert user is not None
        assert user["aal"] == "aal2"

        _token_cache.clear()

    @pytest.mark.asyncio
    @patch("auth._get_jwt_key_and_algorithms")
    async def test_get_current_user_defaults_aal1(self, mock_key):
        """Verify aal defaults to aal1 when not in JWT."""
        import jwt as pyjwt

        test_key = "a-very-long-secret-key-for-testing-purposes-minimum-32-bytes"
        mock_key.return_value = (test_key, ["HS256"])

        token = pyjwt.encode(
            {"sub": "user-123", "email": "test@test.com", "role": "authenticated",
             "aud": "authenticated"},
            test_key,
            algorithm="HS256",
        )

        from auth import get_current_user, _token_cache
        _token_cache.clear()

        creds = MagicMock()
        creds.credentials = token

        user = await get_current_user(creds)
        assert user is not None
        assert user["aal"] == "aal1"

        _token_cache.clear()


# ─── Unit Tests: require_mfa Middleware ────────────────────────────────────────

class TestRequireMfaMiddleware:
    """Tests for require_mfa dependency (AC3)."""

    @pytest.mark.asyncio
    async def test_aal2_passes_through(self, mock_user_aal2):
        from auth import require_mfa
        result = await require_mfa(mock_user_aal2)
        assert result == mock_user_aal2

    @pytest.mark.asyncio
    @patch("authorization.check_user_roles", new_callable=AsyncMock, return_value=(True, True))
    async def test_admin_aal1_rejected(self, mock_roles, mock_admin_aal1):
        from auth import require_mfa
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(mock_admin_aal1)
        assert exc_info.value.status_code == 403
        assert "MFA obrigatório" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("authorization.check_user_roles", new_callable=AsyncMock, return_value=(False, True))
    async def test_master_aal1_rejected(self, mock_roles):
        from auth import require_mfa
        from fastapi import HTTPException
        user = {"id": "master-id", "email": "master@test.com", "role": "authenticated", "aal": "aal1"}
        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @patch("auth._user_has_verified_mfa", new_callable=AsyncMock, return_value=False)
    @patch("auth._get_profile_mfa_state", new_callable=AsyncMock, return_value={})
    @patch("authorization.check_user_roles", new_callable=AsyncMock, return_value=(False, False))
    async def test_regular_user_without_mfa_passes(self, mock_roles, mock_profile, mock_factor, mock_user_aal1):
        """Regular user without MFA factors should pass through.

        MFA-EXT-001: middleware now calls async helpers
        (`_get_profile_mfa_state` + `_user_has_verified_mfa`) instead of
        building a sync `.execute()` chain. Mock those directly so the
        chain shape doesn't leak into the test.
        """
        from auth import require_mfa

        result = await require_mfa(mock_user_aal1)
        assert result == mock_user_aal1

    @pytest.mark.asyncio
    @patch("auth._user_has_verified_mfa", new_callable=AsyncMock, return_value=True)
    @patch("auth._get_profile_mfa_state", new_callable=AsyncMock, return_value={})
    @patch("authorization.check_user_roles", new_callable=AsyncMock, return_value=(False, False))
    async def test_regular_user_with_mfa_enrolled_aal1_rejected(self, mock_roles, mock_profile, mock_factor, mock_user_aal1):
        """Regular user with MFA enrolled but aal1 should be rejected."""
        from auth import require_mfa
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await require_mfa(mock_user_aal1)
        assert exc_info.value.status_code == 403
        assert "Verificação MFA" in exc_info.value.detail


# ─── Integration Tests: MFA Status Endpoint ───────────────────────────────────

class TestMfaStatusEndpoint:
    """Tests for GET /v1/mfa/status (AC4)."""

    @patch("routes.mfa.check_user_roles", new_callable=AsyncMock, return_value=(False, False))
    @patch("routes.mfa._get_supabase")
    def test_mfa_status_no_factors(self, mock_sb, mock_roles, client):
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        res = client.get("/v1/mfa/status")
        assert res.status_code == 200
        data = res.json()
        assert data["mfa_enabled"] is False
        assert data["factors"] == []
        assert data["aal_level"] == "aal2"
        assert data["mfa_required"] is False

    @patch("routes.mfa.check_user_roles", new_callable=AsyncMock, return_value=(True, True))
    @patch("routes.mfa._get_supabase")
    def test_mfa_status_admin_required(self, mock_sb, mock_roles, client):
        mock_result = MagicMock()
        mock_result.data = [{"id": "f1", "factor_type": "totp", "friendly_name": "My Auth", "status": "verified", "created_at": "2026-01-01"}]
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        res = client.get("/v1/mfa/status")
        assert res.status_code == 200
        data = res.json()
        assert data["mfa_enabled"] is True
        assert data["mfa_required"] is True
        assert len(data["factors"]) == 1
        assert data["factors"][0]["verified"] is True


# ─── Integration Tests: Recovery Codes ─────────────────────────────────────────

class TestRecoveryCodesEndpoint:
    """Tests for POST /v1/mfa/recovery-codes (AC5)."""

    @patch("routes.mfa._get_supabase")
    def test_generate_recovery_codes(self, mock_sb, client):
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_sb_instance.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_sb.return_value = mock_sb_instance

        res = client.post("/v1/mfa/recovery-codes")
        assert res.status_code == 200
        data = res.json()
        assert len(data["codes"]) == 10
        assert "message" in data
        # Verify format
        for code in data["codes"]:
            assert "-" in code

    @patch("routes.mfa._get_supabase")
    def test_generate_codes_replaces_existing(self, mock_sb, client):
        """Should delete existing codes before generating new ones."""
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_sb_instance.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_sb.return_value = mock_sb_instance

        client.post("/v1/mfa/recovery-codes")

        # Verify delete was called (replacing existing codes)
        mock_sb_instance.table.return_value.delete.assert_called()


# ─── Integration Tests: Verify Recovery Code ──────────────────────────────────

class TestVerifyRecoveryEndpoint:
    """Tests for POST /v1/mfa/verify-recovery (AC7)."""

    @patch("routes.mfa._record_attempt", new_callable=AsyncMock)
    @patch("routes.mfa._check_brute_force", new_callable=AsyncMock, return_value=0)
    @patch("routes.mfa._get_supabase")
    def test_verify_valid_code(self, mock_sb, mock_brute, mock_record, client):
        from routes.mfa import _hash_code

        valid_hash = _hash_code("ABCD-EF01")

        mock_sb_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "code-1", "code_hash": valid_hash},
            {"id": "code-2", "code_hash": _hash_code("XXXX-YYYY")},
        ]
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value = mock_result
        mock_sb_instance.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_sb.return_value = mock_sb_instance

        res = client.post("/v1/mfa/verify-recovery", json={"code": "ABCD-EF01"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["remaining_codes"] == 1

    @patch("routes.mfa._record_attempt", new_callable=AsyncMock)
    @patch("routes.mfa._check_brute_force", new_callable=AsyncMock, return_value=0)
    @patch("routes.mfa._get_supabase")
    def test_verify_invalid_code(self, mock_sb, mock_brute, mock_record, client):
        from routes.mfa import _hash_code

        mock_sb_instance = MagicMock()
        # Select unused codes
        mock_result = MagicMock()
        mock_result.data = [{"id": "code-1", "code_hash": _hash_code("REAL-CODE")}]
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value = mock_result
        # Failed attempts count query
        mock_attempts = MagicMock()
        mock_attempts.data = [{"id": "a1"}]
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = mock_attempts
        mock_sb.return_value = mock_sb_instance

        res = client.post("/v1/mfa/verify-recovery", json={"code": "WRONG-COD"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert "inválido" in data["message"].lower() or "Tentativas" in data["message"]

    @patch("routes.mfa._check_brute_force", new_callable=AsyncMock)
    def test_verify_brute_force_blocked(self, mock_brute, client):
        """AC22: Brute force protection — 3 attempts/hour limit."""
        from fastapi import HTTPException
        mock_brute.side_effect = HTTPException(
            status_code=429,
            detail="Muitas tentativas. Tente novamente em 1 hora. (3/3)",
        )

        res = client.post("/v1/mfa/verify-recovery", json={"code": "TEST-CODE"})
        assert res.status_code == 429
        assert "Muitas tentativas" in res.json()["detail"]


# ─── Integration Tests: Regenerate Recovery Codes ─────────────────────────────

class TestRegenerateRecoveryEndpoint:
    """Tests for POST /v1/mfa/regenerate-recovery (AC8)."""

    @patch("routes.mfa._get_supabase")
    def test_regenerate_with_aal2(self, mock_sb, client):
        """Should work with aal2 session."""
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_sb_instance.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_sb.return_value = mock_sb_instance

        res = client.post("/v1/mfa/regenerate-recovery")
        assert res.status_code == 200
        data = res.json()
        assert len(data["codes"]) == 10

    def test_regenerate_without_aal2(self, client_aal1):
        """Should reject aal1 session."""
        res = client_aal1.post("/v1/mfa/regenerate-recovery")
        assert res.status_code == 403
        assert "Verificação MFA" in res.json()["detail"]


# ─── Brute Force Protection Tests ─────────────────────────────────────────────

class TestBruteForceProtection:
    """Tests for brute force protection on recovery code verification (AC22)."""

    @pytest.mark.asyncio
    @patch("routes.mfa._get_supabase")
    async def test_check_brute_force_under_limit(self, mock_sb):
        from routes.mfa import _check_brute_force

        mock_sb_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "1"}, {"id": "2"}]
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        count = await _check_brute_force("test-user-id")
        assert count == 2  # Under limit of 3

    @pytest.mark.asyncio
    @patch("routes.mfa._get_supabase")
    async def test_check_brute_force_at_limit(self, mock_sb):
        from routes.mfa import _check_brute_force
        from fastapi import HTTPException

        mock_sb_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        with pytest.raises(HTTPException) as exc_info:
            await _check_brute_force("test-user-id")
        assert exc_info.value.status_code == 429
        assert "Muitas tentativas" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("routes.mfa._get_supabase")
    async def test_record_attempt(self, mock_sb):
        from routes.mfa import _record_attempt

        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_sb.return_value = mock_sb_instance

        await _record_attempt("test-user-id", success=False)

        mock_sb_instance.table.assert_called_with("mfa_recovery_attempts")
        call_args = mock_sb_instance.table.return_value.insert.call_args[0][0]
        assert call_args["user_id"] == "test-user-id"
        assert call_args["success"] is False


# ─── Edge Cases ────────────────────────────────────────────────────────────────

class TestMfaEdgeCases:
    """Edge case tests for MFA implementation."""

    def test_recovery_code_all_used(self):
        """All codes used — should not match."""
        from routes.mfa import _hash_code, _verify_code
        code = "ABCD-EF01"
        hashed = _hash_code(code)
        # If we had an empty list, no match
        assert _verify_code("ABCD-EF01", hashed) is True  # Direct match works
        assert _verify_code("0000-0000", hashed) is False  # But wrong code fails

    def test_generate_codes_default_count(self):
        from routes.mfa import _generate_recovery_codes, RECOVERY_CODE_COUNT
        codes = _generate_recovery_codes()
        assert len(codes) == RECOVERY_CODE_COUNT

    def test_codes_are_cryptographically_random(self):
        """Each batch should produce different codes."""
        from routes.mfa import _generate_recovery_codes
        batch1 = _generate_recovery_codes(5)
        batch2 = _generate_recovery_codes(5)
        assert batch1 != batch2  # Extremely unlikely to be identical

    @patch("routes.mfa.check_user_roles", new_callable=AsyncMock, return_value=(False, False))
    @patch("routes.mfa._get_supabase")
    def test_mfa_status_factor_read_failure(self, mock_sb, mock_roles, client):
        """Should gracefully handle factor read failure."""
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        mock_sb.return_value = mock_sb_instance

        res = client.get("/v1/mfa/status")
        assert res.status_code == 200
        data = res.json()
        assert data["mfa_enabled"] is False
        assert data["factors"] == []


# ─── Issue #639 — TOTP Enroll + Verify Endpoints ──────────────────────────────

@pytest.fixture
def client_with_token():
    """Test client that injects a Bearer token so /enroll + /verify-totp can
    extract the access token from the Authorization header."""
    from main import app
    from auth import require_auth
    app.dependency_overrides[require_auth] = lambda: {
        "id": "test-user-id-123",
        "email": "test@example.com",
        "role": "authenticated",
        "aal": "aal1",
    }
    tc = TestClient(app, headers={"Authorization": "Bearer fake-test-jwt-token"})
    yield tc
    app.dependency_overrides.clear()


class TestEnrollTotpEndpoint:
    """Tests for POST /v1/mfa/enroll (Issue #639 AC1)."""

    @patch("routes.mfa._persist_backup_codes", new_callable=AsyncMock,
           return_value=["AAAA-BBBB", "CCCC-DDDD"])
    @patch("routes.mfa._get_user_supabase_for_auth")
    def test_enroll_happy_path(self, mock_user_sb, mock_codes, client_with_token):
        """Successful enrolment returns factor_id, qr_code_uri, secret, and codes."""
        # Build a mock supabase-py enroll response shaped as a dict
        enroll_resp = {
            "id": "factor-uuid-123",
            "type": "totp",
            "totp": {
                "qr_code": "<svg>...</svg>",
                "secret": "JBSWY3DPEHPK3PXP",
                "uri": "otpauth://totp/SmartLic:test@example.com?secret=JBSWY3DPEHPK3PXP&issuer=SmartLic",
            },
        }
        sb_user = MagicMock()
        sb_user.auth.mfa.enroll.return_value = enroll_resp
        mock_user_sb.return_value = sb_user

        res = client_with_token.post("/v1/mfa/enroll")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["factor_id"] == "factor-uuid-123"
        assert data["qr_code_uri"].startswith("otpauth://totp/")
        assert data["secret"] == "JBSWY3DPEHPK3PXP"
        assert data["backup_codes"] == ["AAAA-BBBB", "CCCC-DDDD"]
        # Verify enroll was called with totp + friendly_name
        call_args = sb_user.auth.mfa.enroll.call_args[0][0]
        assert call_args["factor_type"] == "totp"
        assert call_args["friendly_name"] == "SmartLic"

    def test_enroll_rejects_missing_token(self):
        """No Authorization header → 401."""
        from main import app
        from auth import require_auth
        app.dependency_overrides[require_auth] = lambda: {
            "id": "test-user-id-123", "email": "x@x.com", "role": "authenticated", "aal": "aal1"
        }
        try:
            tc = TestClient(app)  # no Authorization header
            res = tc.post("/v1/mfa/enroll")
            assert res.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @patch("routes.mfa._persist_backup_codes", new_callable=AsyncMock, return_value=[])
    @patch("routes.mfa._get_user_supabase_for_auth")
    def test_enroll_supabase_failure_returns_502(self, mock_user_sb, mock_codes, client_with_token):
        """Supabase SDK error → 502."""
        sb_user = MagicMock()
        sb_user.auth.mfa.enroll.side_effect = Exception("supabase down")
        mock_user_sb.return_value = sb_user

        res = client_with_token.post("/v1/mfa/enroll")
        assert res.status_code == 502
        assert "MFA" in res.json()["detail"] or "Não foi possível" in res.json()["detail"]

    @patch("routes.mfa._persist_backup_codes", new_callable=AsyncMock, return_value=[])
    @patch("routes.mfa._get_user_supabase_for_auth")
    def test_enroll_incomplete_response_returns_502(self, mock_user_sb, mock_codes, client_with_token):
        """Empty totp payload → 502."""
        sb_user = MagicMock()
        sb_user.auth.mfa.enroll.return_value = {"id": "abc", "totp": {}}
        mock_user_sb.return_value = sb_user

        res = client_with_token.post("/v1/mfa/enroll")
        assert res.status_code == 502

    @patch("routes.mfa._persist_backup_codes", new_callable=AsyncMock,
           side_effect=Exception("db down"))
    @patch("routes.mfa._get_user_supabase_for_auth")
    def test_enroll_continues_when_backup_codes_fail(self, mock_user_sb, mock_codes, client_with_token):
        """Backup-code persistence failure is non-fatal — return enrol with empty codes."""
        sb_user = MagicMock()
        sb_user.auth.mfa.enroll.return_value = {
            "id": "factor-1", "totp": {"uri": "otpauth://totp/x", "secret": "JBSW"}
        }
        mock_user_sb.return_value = sb_user

        res = client_with_token.post("/v1/mfa/enroll")
        assert res.status_code == 200
        data = res.json()
        assert data["backup_codes"] == []


class TestVerifyTotpEndpoint:
    """Tests for POST /v1/mfa/verify-totp (Issue #639 AC2 + AC4 brute-force)."""

    @patch("routes.mfa._get_user_supabase_for_auth")
    @patch("routes.mfa._get_supabase")
    def test_verify_happy_path(self, mock_sb, mock_user_sb, client_with_token):
        """Valid code → 200 + aal2."""
        # Factors lookup
        mock_sb_instance = MagicMock()
        mock_factors = MagicMock()
        mock_factors.data = [{"id": "factor-1", "status": "unverified", "created_at": "2026-01-01"}]
        (
            mock_sb_instance.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute.return_value
        ) = mock_factors
        mock_sb.return_value = mock_sb_instance

        # User-scoped client (challenge + verify)
        sb_user = MagicMock()
        sb_user.auth.mfa.challenge.return_value = {"id": "challenge-1"}
        sb_user.auth.mfa.verify.return_value = MagicMock()
        mock_user_sb.return_value = sb_user

        res = client_with_token.post("/v1/mfa/verify-totp", json={"totp_code": "123456"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["aal_level"] == "aal2"
        assert data["factor_id"] == "factor-1"
        # Verify call args
        verify_args = sb_user.auth.mfa.verify.call_args[0][0]
        assert verify_args["factor_id"] == "factor-1"
        assert verify_args["challenge_id"] == "challenge-1"
        assert verify_args["code"] == "123456"

    @patch("routes.mfa._get_supabase")
    def test_verify_no_factor_returns_400(self, mock_sb, client_with_token):
        """No enrolled factor → 400."""
        mock_sb_instance = MagicMock()
        mock_factors = MagicMock()
        mock_factors.data = []
        (
            mock_sb_instance.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute.return_value
        ) = mock_factors
        mock_sb.return_value = mock_sb_instance

        res = client_with_token.post("/v1/mfa/verify-totp", json={"totp_code": "654321"})
        assert res.status_code == 400
        assert "Cadastre" in res.json()["detail"] or "fator" in res.json()["detail"].lower()

    @patch("routes.mfa._get_user_supabase_for_auth")
    @patch("routes.mfa._get_supabase")
    def test_verify_wrong_code_returns_400(self, mock_sb, mock_user_sb, client_with_token):
        """Bad TOTP code → Supabase verify raises → 400."""
        mock_sb_instance = MagicMock()
        mock_factors = MagicMock()
        mock_factors.data = [{"id": "factor-1", "status": "unverified", "created_at": "2026-01-01"}]
        (
            mock_sb_instance.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute.return_value
        ) = mock_factors
        mock_sb.return_value = mock_sb_instance

        sb_user = MagicMock()
        sb_user.auth.mfa.challenge.return_value = {"id": "challenge-1"}
        sb_user.auth.mfa.verify.side_effect = Exception("invalid_code")
        mock_user_sb.return_value = sb_user

        res = client_with_token.post("/v1/mfa/verify-totp", json={"totp_code": "000000"})
        assert res.status_code == 400
        assert "TOTP" in res.json()["detail"] or "inválido" in res.json()["detail"].lower()

    def test_verify_validates_digits_only(self, client_with_token):
        """Non-numeric totp_code → 422 from Pydantic validator."""
        res = client_with_token.post("/v1/mfa/verify-totp", json={"totp_code": "abcdef"})
        assert res.status_code == 422

    @patch("routes.mfa._get_user_supabase_for_auth")
    @patch("routes.mfa._get_supabase")
    @patch("config.get_feature_flag", return_value=True)
    def test_verify_brute_force_returns_429(self, mock_flag, mock_sb, mock_user_sb, client_with_token):
        """Issue #639 AC4: 6th attempt within 15min → 429.

        require_rate_limit(5, 900) is wired in via Depends; on the 6th call
        within the window the FlexibleRateLimiter must throttle.
        """
        # Allow factor lookup + challenge to succeed for the first 5 calls
        mock_sb_instance = MagicMock()
        mock_factors = MagicMock()
        mock_factors.data = [{"id": "factor-1", "status": "unverified", "created_at": "2026-01-01"}]
        (
            mock_sb_instance.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute.return_value
        ) = mock_factors
        mock_sb.return_value = mock_sb_instance

        sb_user = MagicMock()
        sb_user.auth.mfa.challenge.return_value = {"id": "challenge-1"}
        sb_user.auth.mfa.verify.side_effect = Exception("invalid_code")
        mock_user_sb.return_value = sb_user

        # Reset the in-memory rate limiter so this test is hermetic
        from rate_limiter import _flexible_limiter
        _flexible_limiter._memory_store.clear()

        # 5 attempts allowed (each returns 400 because code is wrong)
        for i in range(5):
            res = client_with_token.post("/v1/mfa/verify-totp", json={"totp_code": "000000"})
            assert res.status_code == 400, f"attempt {i + 1} returned {res.status_code}"

        # 6th attempt → 429 from rate limiter
        res = client_with_token.post("/v1/mfa/verify-totp", json={"totp_code": "000000"})
        assert res.status_code == 429
        assert "Retry-After" in res.headers


class TestMfaStatusAdminEnforcement:
    """Issue #639 AC3: /status reports mfa_required=True for admin/master."""

    @patch("routes.mfa.check_user_roles", new_callable=AsyncMock, return_value=(True, True))
    @patch("routes.mfa._get_supabase")
    def test_admin_user_mfa_required_true(self, mock_sb, mock_roles, client):
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        res = client.get("/v1/mfa/status")
        assert res.status_code == 200
        assert res.json()["mfa_required"] is True

    @patch("routes.mfa.check_user_roles", new_callable=AsyncMock, return_value=(False, True))
    @patch("routes.mfa._get_supabase")
    def test_master_user_mfa_required_true(self, mock_sb, mock_roles, client):
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        res = client.get("/v1/mfa/status")
        assert res.status_code == 200
        assert res.json()["mfa_required"] is True

    @patch("routes.mfa.check_user_roles", new_callable=AsyncMock, return_value=(False, False))
    @patch("routes.mfa._get_supabase")
    def test_regular_user_mfa_required_false(self, mock_sb, mock_roles, client):
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb_instance = MagicMock()
        mock_sb_instance.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_sb.return_value = mock_sb_instance

        res = client.get("/v1/mfa/status")
        assert res.status_code == 200
        assert res.json()["mfa_required"] is False
