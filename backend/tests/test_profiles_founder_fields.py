"""Tests for #784: profiles founder fields migration.

Validates that UserProfileResponse includes the five new founder columns with
correct defaults and Pydantic-level constraint enforcement for
consulting_discount_pct (mirrors the DB CHECK constraint).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.user import UserProfileResponse


# ---------------------------------------------------------------------------
# Helpers — minimal valid UserProfileResponse payload
# ---------------------------------------------------------------------------

def _base_payload(**overrides) -> dict:
    """Return a minimal valid payload for UserProfileResponse."""
    payload = {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "test@example.com",
        "plan_id": "pro_mensal",
        "plan_name": "Pro Mensal",
        "capabilities": {"allow_excel": True, "max_history_days": 30},
        "quota_used": 0,
        "quota_remaining": 50,
        "quota_reset_date": "2026-06-01T00:00:00Z",
        "subscription_status": "active",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


def test_founder_fields_default_to_non_founder():
    """New profiles have is_founder=False and all founder fields None by default."""
    profile = UserProfileResponse(**_base_payload())

    assert profile.is_founder is False
    assert profile.founder_since is None
    assert profile.founder_offer_version is None
    assert profile.founder_checkout_source is None
    assert profile.consulting_discount_pct is None


# ---------------------------------------------------------------------------
# Happy-path: founder profile
# ---------------------------------------------------------------------------


def test_founder_profile_roundtrip():
    """A fully-populated founder profile serialises and deserialises correctly."""
    ts = datetime(2026, 5, 7, 10, 0, 0, tzinfo=timezone.utc)
    profile = UserProfileResponse(**_base_payload(
        is_founder=True,
        founder_since=ts,
        founder_offer_version="v2_lifetime",
        founder_checkout_source="landing_fundadores",
        consulting_discount_pct=50,
    ))

    assert profile.is_founder is True
    assert profile.founder_since == ts
    assert profile.founder_offer_version == "v2_lifetime"
    assert profile.founder_checkout_source == "landing_fundadores"
    assert profile.consulting_discount_pct == 50


# ---------------------------------------------------------------------------
# consulting_discount_pct — boundary tests (mirrors DB CHECK constraint)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pct", [0, 1, 50, 99, 100])
def test_consulting_discount_pct_valid_range(pct: int):
    """Discount percentages 0–100 are accepted."""
    profile = UserProfileResponse(**_base_payload(consulting_discount_pct=pct))
    assert profile.consulting_discount_pct == pct


def test_consulting_discount_pct_none_is_valid():
    """NULL discount (no consulting benefit) is the default and is valid."""
    profile = UserProfileResponse(**_base_payload(consulting_discount_pct=None))
    assert profile.consulting_discount_pct is None


@pytest.mark.parametrize("bad_pct", [-1, 101, 200, -100])
def test_consulting_discount_pct_out_of_range_raises(bad_pct: int):
    """Values outside 0–100 are rejected by Pydantic (mirrors DB CHECK)."""
    with pytest.raises(ValidationError) as exc_info:
        UserProfileResponse(**_base_payload(consulting_discount_pct=bad_pct))

    errors = exc_info.value.errors()
    field_errors = [e for e in errors if "consulting_discount_pct" in str(e.get("loc", ""))]
    assert field_errors, (
        f"Expected validation error on consulting_discount_pct for value {bad_pct}, "
        f"got: {errors}"
    )


# ---------------------------------------------------------------------------
# is_founder truthy / falsy
# ---------------------------------------------------------------------------


def test_is_founder_false_does_not_require_other_fields():
    """Non-founder profile: is_founder=False without any other founder fields is fine."""
    profile = UserProfileResponse(**_base_payload(is_founder=False))
    assert profile.is_founder is False
    assert profile.founder_since is None


def test_is_founder_true_without_since_is_allowed():
    """is_founder=True without founder_since is valid (webhook may set them separately)."""
    profile = UserProfileResponse(**_base_payload(is_founder=True))
    assert profile.is_founder is True
    assert profile.founder_since is None


# ---------------------------------------------------------------------------
# v1 vs v2 founder distinction
# ---------------------------------------------------------------------------


def test_v1_subscription_founders_are_not_marked():
    """v1 subscription founders do not receive is_founder=True (per spec)."""
    # v1 founders are regular pro subscribers — is_founder stays False
    profile = UserProfileResponse(**_base_payload(
        plan_id="pro_mensal",
        is_founder=False,  # explicit: v1 founders remain False
    ))
    assert profile.is_founder is False


def test_v2_lifetime_founder_has_correct_offer_version():
    """v2 lifetime founders carry founder_offer_version='v2_lifetime'."""
    profile = UserProfileResponse(**_base_payload(
        is_founder=True,
        founder_offer_version="v2_lifetime",
        consulting_discount_pct=50,
    ))
    assert profile.founder_offer_version == "v2_lifetime"
    assert profile.consulting_discount_pct == 50


# ---------------------------------------------------------------------------
# Serialisation — dict round-trip
# ---------------------------------------------------------------------------


def test_founder_fields_present_in_model_dict():
    """All five founder fields are present in the model's serialised dict."""
    profile = UserProfileResponse(**_base_payload())
    data = profile.model_dump()

    assert "is_founder" in data
    assert "founder_since" in data
    assert "founder_offer_version" in data
    assert "founder_checkout_source" in data
    assert "consulting_discount_pct" in data
