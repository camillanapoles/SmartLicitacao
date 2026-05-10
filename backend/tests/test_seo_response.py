"""Tests for `backend/utils/seo_response.apply_seo_empty_response` (Issue #1036).

Covers the four documented branches:

1. empty + historical → 200 mark + ``X-Robots-Tag``/``X-Coverage-Status`` set
2. empty + current    → same shape (NEVER 404 for a transient gap)
3. non-empty           → payload passthrough + ``X-Coverage-Status: full``
4. response=None       → payload mutated, no header side effects
"""

from datetime import date

import pytest
from fastapi import Response

from utils.seo_response import apply_seo_empty_response


def _make_response() -> Response:
    """Fresh `fastapi.Response` for each test (headers are mutable)."""
    return Response()


class TestApplySeoEmptyResponse:
    def test_empty_historical_marks_payload_and_sets_headers(self):
        response = _make_response()
        payload: dict = {"total_editais": 0, "valor_total": 0.0}

        result = apply_seo_empty_response(
            payload,
            is_empty=True,
            is_historical=True,
            period_label="abril/2026",
            coverage_window=(date(2026, 4, 1), date(2026, 4, 30)),
            response=response,
        )

        # Payload mutated in-place.
        assert result is payload
        assert result["is_empty_period"] is True
        assert result["period_label"] == "abril/2026"
        assert result["coverage_window"] == {
            "start": "2026-04-01",
            "end": "2026-04-30",
        }
        # Headers reflect noindex + sitemap-gating signal.
        assert "noindex" in response.headers["X-Robots-Tag"]
        assert "follow" in response.headers["X-Robots-Tag"]
        assert response.headers["X-Coverage-Status"] == "empty"

    def test_empty_current_period_never_404s(self):
        """Programmatic SEO routes never 404 on a transient data gap.

        The helper applies the same noindex+is_empty_period shape regardless
        of whether the period is current or historical; the route layer
        (e.g. observatorio's behavior toggle) decides if it ALSO 404s.
        """
        response = _make_response()
        payload = {"total_editais": 0}

        result = apply_seo_empty_response(
            payload,
            is_empty=True,
            is_historical=False,  # current month
            period_label="maio/2026",
            response=response,
        )

        assert result["is_empty_period"] is True
        assert result["period_label"] == "maio/2026"
        # No coverage_window provided → key absent (caller didn't supply it).
        assert "coverage_window" not in result
        assert "noindex" in response.headers["X-Robots-Tag"]
        assert response.headers["X-Coverage-Status"] == "empty"

    def test_non_empty_passthrough_sets_full_coverage(self):
        response = _make_response()
        payload = {"total_editais": 42, "valor_total": 1234.56}

        result = apply_seo_empty_response(
            payload,
            is_empty=False,
            is_historical=False,
            period_label="abril/2026",
            response=response,
        )

        # Payload unchanged.
        assert result == {"total_editais": 42, "valor_total": 1234.56}
        assert "is_empty_period" not in result
        assert "period_label" not in result
        # No noindex header on a healthy page.
        assert "X-Robots-Tag" not in response.headers
        assert response.headers["X-Coverage-Status"] == "full"

    def test_no_response_object_only_mutates_payload(self):
        """When ``response`` is None, headers cannot be set — verify no
        AttributeError, payload is still marked correctly."""
        payload = {"total_editais": 0}

        result = apply_seo_empty_response(
            payload,
            is_empty=True,
            is_historical=True,
            period_label="abril/2026",
            response=None,
        )

        assert result["is_empty_period"] is True
        assert result["period_label"] == "abril/2026"

    def test_caller_default_false_is_force_overridden(self):
        """``is_empty_period`` is force-set when ``is_empty=True``.

        Important for observatorio.py: ``_generate_relatorio`` returns a
        payload with ``is_empty_period: False`` (Pydantic default); the
        helper must override it, not honor the upstream default.
        Other annotation keys (``period_label``) honor caller pre-population
        via ``setdefault``.
        """
        response = _make_response()
        payload = {
            "total_editais": 0,
            "is_empty_period": False,  # Pydantic default leaked in
            "period_label": "custom-label",
        }

        result = apply_seo_empty_response(
            payload,
            is_empty=True,
            is_historical=True,
            period_label="should-be-ignored",
            response=response,
        )

        assert result["is_empty_period"] is True
        assert result["period_label"] == "custom-label"
        assert response.headers["X-Coverage-Status"] == "empty"


@pytest.mark.parametrize("is_historical", [True, False])
def test_empty_branches_share_response_shape(is_historical: bool):
    """Smoke test: empty payload always renders is_empty_period regardless
    of historical vs current — the 404 routing decision lives at the route
    layer, not in this helper."""
    response = _make_response()
    payload = {"total_editais": 0}

    result = apply_seo_empty_response(
        payload,
        is_empty=True,
        is_historical=is_historical,
        period_label="qualquer/2026",
        response=response,
    )

    assert result["is_empty_period"] is True
    assert response.headers["X-Coverage-Status"] == "empty"
