"""Centralized empty-period response helper for programmatic SEO routes.

Issue #1036 — extracted from `routes/observatorio.py::_apply_empty_period_response`
so all SEO public endpoints (`*_publicos.py`, `observatorio.py`, `blog_stats.py`,
`dados_publicos.py`, etc.) can render the same shape on a data gap rather than
404'ing (which Search Console flags as a Soft 404 / data-quality signal).

Pattern:
- empty + historical → 200 + ``is_empty_period:true`` + ``X-Robots-Tag: noindex``
- empty + current    → same (NEVER 404 for a transient data gap)
- non-empty          → returns payload unchanged (caller renders normally)

Headers (when ``response`` provided):
- ``X-Robots-Tag: noindex, follow`` whenever the period is empty.
- ``X-Coverage-Status: full | empty`` for downstream sitemap-gating (#1039).

The route-level decision of whether to ALSO 404 (for current month, anti-Soft-404)
is intentionally out of scope here: callers that need that branch should still
implement it inline (see ``observatorio.py``). This helper covers the
"render the empty payload + correctly tag headers" branch only.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

from fastapi import Response


def apply_seo_empty_response(
    payload: dict,
    *,
    is_empty: bool,
    is_historical: bool,
    period_label: str,
    coverage_window: Optional[Tuple[date, date]] = None,
    response: Optional[Response] = None,
) -> dict:
    """Mark ``payload`` as an empty-period response and set SEO headers.

    Args:
        payload: The base response dict the route would otherwise return.
            Mutated in-place (and returned) when ``is_empty`` is True.
        is_empty: True when the underlying query returned zero rows.
        is_historical: True when the requested period has fully elapsed.
            Currently informational (does NOT 404 — programmatic SEO routes
            never 404 on a data gap). Reserved for future tag differentiation.
        period_label: Human-readable label for the period
            (e.g. ``"abril/2026"``, ``"semana 18 de 2026"``). Stored under
            ``payload["period_label"]`` for frontend rendering.
        coverage_window: Optional ``(start, end)`` tuple describing the
            window the route attempted to cover. Stored under
            ``payload["coverage_window"]`` as ISO-format strings.
        response: FastAPI ``Response`` to mutate with cache-control / robots
            headers. When ``None``, only the payload is mutated.

    Returns:
        The same ``payload`` dict. When ``is_empty`` is False the dict is
        unchanged; when True it gains ``is_empty_period``, ``period_label``
        and (optionally) ``coverage_window`` keys (only set if absent —
        callers can pre-populate them).
    """
    # Reserved for future header differentiation between current vs historical
    # empty periods (e.g. tighter cache TTL on current). Currently both
    # paths share the same response shape, so the parameter is accepted but
    # not yet branched on.
    _ = is_historical

    if not is_empty:
        if response is not None:
            response.headers["X-Coverage-Status"] = "full"
        return payload

    # Always force ``is_empty_period`` True when the caller declared the
    # period empty — this overrides any default-False that may have leaked in
    # from a Pydantic-shaped payload upstream (e.g. observatorio's
    # `_generate_relatorio` returns `is_empty_period: False` by default).
    payload["is_empty_period"] = True
    payload.setdefault("period_label", period_label)
    if coverage_window is not None:
        payload.setdefault(
            "coverage_window",
            {
                "start": coverage_window[0].isoformat(),
                "end": coverage_window[1].isoformat(),
            },
        )

    if response is not None:
        # ``follow`` lets crawlers traverse links back to the hub even on
        # noindex'd empty leaves — improves crawl budget reuse.
        response.headers["X-Robots-Tag"] = "noindex, follow"
        response.headers["X-Coverage-Status"] = "empty"

    return payload
