"""DATA-CNAE-002 (#710) — non-fatal CNAE warmup guard tests.

Pins the contract that the CNAE warmup never aborts startup:
    * DB raises -> warmup logs warning, returns; CNAE_TO_SETOR unchanged.
    * DB returns rows -> CNAE_TO_SETOR merges them (hardcoded keys preserved).
    * DB returns empty -> CNAE_TO_SETOR unchanged, no error.
    * DB times out -> warmup logs warning, returns; CNAE_TO_SETOR unchanged.

Failure of any of these tests indicates a regression of the PR #679 →
PR #702 revert: a CNAE-warmup error propagating out of `lifespan` would
fail the Railway healthcheck and roll back the deploy.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_warmup_cnae_db_raises_does_not_abort_startup(caplog):
    """AC1/AC3: Supabase exception during warmup must NOT raise.

    Mirrors the PR #702 revert reason: any failure in CNAE warmup must
    log a WARNING and let lifespan continue with the hardcoded baseline.
    """
    from utils import cnae_mapping
    from startup.lifespan import _warmup_cnae_mapping

    baseline_keys = set(cnae_mapping.CNAE_TO_SETOR.keys())
    baseline_engenharia = cnae_mapping.CNAE_TO_SETOR.get("4120")

    mock_sb = MagicMock()
    # Simulate PostgREST PGRST205 (table missing in cache) — must not raise.
    mock_sb.table.return_value.select.return_value.execute.side_effect = \
        RuntimeError("PGRST205: schema cache stale")

    with (
        patch("supabase_client.get_supabase", return_value=mock_sb),
        caplog.at_level("WARNING"),
    ):
        # Must complete without raising
        await _warmup_cnae_mapping()

    # Hardcoded baseline must be untouched
    assert set(cnae_mapping.CNAE_TO_SETOR.keys()) == baseline_keys
    assert cnae_mapping.CNAE_TO_SETOR.get("4120") == baseline_engenharia

    # A WARNING-level operator signal must have been emitted on the
    # DATA-CNAE-002 channel — wording is intentionally loose so refactors
    # don't break the contract (only the level + ticket prefix matter).
    warning_messages = [
        rec.message for rec in caplog.records if rec.levelname == "WARNING"
    ]
    assert any(
        "DATA-CNAE-002" in msg for msg in warning_messages
    ), f"Expected DATA-CNAE-002 WARNING, got: {warning_messages}"


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_warmup_cnae_db_rows_merge_over_baseline():
    """AC1: Successful DB load merges rows into CNAE_TO_SETOR.

    DB rows override hardcoded values for the same key; new keys are added;
    untouched hardcoded keys remain. Critical that this is a MERGE (.update)
    not a REPLACE (= rows) — losing the hardcoded baseline would regress
    callers that depend on legacy CNAEs not yet seeded into the DB.
    """
    from utils import cnae_mapping
    from startup.lifespan import _warmup_cnae_mapping

    baseline_keys = set(cnae_mapping.CNAE_TO_SETOR.keys())
    # Pick a hardcoded key the DB will override
    overridden_key = "4120"
    assert overridden_key in baseline_keys, "test fixture assumes 4120 is hardcoded"

    new_rows = [
        {"codigo_cnae": overridden_key, "setor": "engenharia_civil_test_override"},
        {"codigo_cnae": "9999", "setor": "test_new_sector"},
    ]
    mock_response = MagicMock()
    mock_response.data = new_rows

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.execute.return_value = mock_response

    original_4120 = cnae_mapping.CNAE_TO_SETOR.get(overridden_key)
    try:
        with patch("supabase_client.get_supabase", return_value=mock_sb):
            await _warmup_cnae_mapping()

        # Override applied
        assert cnae_mapping.CNAE_TO_SETOR[overridden_key] == "engenharia_civil_test_override"
        # New key added
        assert cnae_mapping.CNAE_TO_SETOR["9999"] == "test_new_sector"
        # Untouched hardcoded keys preserved (sample one not in new_rows)
        assert "4781" in cnae_mapping.CNAE_TO_SETOR
        assert cnae_mapping.CNAE_TO_SETOR["4781"] == "vestuario"
    finally:
        # Restore baseline so subsequent tests in this file see hardcoded values
        cnae_mapping.CNAE_TO_SETOR[overridden_key] = original_4120
        cnae_mapping.CNAE_TO_SETOR.pop("9999", None)


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_warmup_cnae_empty_table_keeps_baseline(caplog):
    """AC1: Empty DB result preserves hardcoded baseline (no warning, info-level)."""
    from utils import cnae_mapping
    from startup.lifespan import _warmup_cnae_mapping

    baseline_size = len(cnae_mapping.CNAE_TO_SETOR)

    mock_response = MagicMock()
    mock_response.data = []
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.execute.return_value = mock_response

    with (
        patch("supabase_client.get_supabase", return_value=mock_sb),
        caplog.at_level("INFO"),
    ):
        await _warmup_cnae_mapping()

    assert len(cnae_mapping.CNAE_TO_SETOR) == baseline_size


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_warmup_cnae_timeout_does_not_abort_startup(caplog):
    """AC1/AC3: A slow DB query times out without aborting startup.

    Pins the asyncio.wait_for guard — if Supabase hangs, we surrender
    after CNAE_WARMUP_TIMEOUT_S and continue with the hardcoded baseline.
    """
    from utils import cnae_mapping
    from startup.lifespan import _warmup_cnae_mapping

    baseline_size = len(cnae_mapping.CNAE_TO_SETOR)

    def _slow_load():
        # Block long enough to trip the wait_for timeout we set below.
        import time as _t
        _t.sleep(2)
        return {}

    with (
        patch("utils.cnae_mapping.load_cnae_from_db", side_effect=_slow_load),
        patch.dict("os.environ", {"CNAE_WARMUP_TIMEOUT_S": "0.1"}),
        caplog.at_level("WARNING"),
    ):
        await _warmup_cnae_mapping()

    assert len(cnae_mapping.CNAE_TO_SETOR) == baseline_size
    assert any(
        "DATA-CNAE-002" in rec.message
        and ("timed out" in rec.message.lower() or "fallback" in rec.message.lower())
        for rec in caplog.records
    ), f"Expected DATA-CNAE-002 timeout warning, got: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# AC3: /health/ready stays 200 when CNAE warmup fails
# ---------------------------------------------------------------------------

class TestHealthReadyAfterCnaeWarmupFailure:
    """AC3: When the CNAE warmup raises, lifespan still completes and
    /health/ready returns 200 once Redis + Supabase are up.

    This pins the end-to-end contract from the issue: "the underlying
    DB error must NOT crash the readiness check". Since warmup runs
    inside lifespan startup (not on the request path), this is implicit
    — but we exercise the route here to cover the regression that
    triggered the PR #679 revert.
    """

    def test_ready_200_when_cnae_warmup_would_have_raised(self):
        import time
        from fastapi.testclient import TestClient

        # Force any future warmup invocation to raise — proves that even
        # if the guard regresses, the route layer is independent.
        with (
            patch("startup.state.startup_time", time.monotonic()),
            patch(
                "utils.cnae_mapping.load_cnae_from_db",
                side_effect=RuntimeError("simulated DB outage"),
            ),
        ):
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_sb = MagicMock()
            mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
            mock_resp = MagicMock()
            mock_resp.data = [{"id": "x"}]
            with (
                patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
                patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_resp),
                patch("supabase_client.get_supabase", return_value=mock_sb),
            ):
                from main import app
                client = TestClient(app, raise_server_exceptions=False)
                response = client.get("/health/ready")
                assert response.status_code == 200, response.json()
                data = response.json()
                assert data["ready"] is True
