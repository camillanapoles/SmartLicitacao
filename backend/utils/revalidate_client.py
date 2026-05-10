"""Fire-and-forget ISR revalidation client for Next.js on-demand cache busting.

Calls `POST <FRONTEND_REVALIDATE_URL>` with the shared `REVALIDATE_SECRET` to
trigger Next.js `revalidatePath` for the given paths.

Usage (from ARQ ingestion job or admin endpoint)::

    from utils.revalidate_client import revalidate_paths

    # Non-blocking — never raises, never delays ingestion
    await revalidate_paths(["/observatorio/raio-x-marco-2026"])

Environment variables:
    FRONTEND_REVALIDATE_URL  Full URL to the Next.js revalidate handler
                             (e.g. https://smartlic.tech/api/revalidate).
                             When unset the call is silently skipped.
    REVALIDATE_SECRET        Shared secret sent as x-revalidate-secret header.
                             When unset the call is silently skipped.
"""

from __future__ import annotations

import logging
import os
from typing import Sequence

import httpx

logger = logging.getLogger(__name__)


async def revalidate_paths(paths: Sequence[str]) -> None:
    """Fire-and-forget POST to Next.js /api/revalidate endpoint.

    Never raises — all errors are logged as warnings.  The caller must NOT
    await this function inside a ``try/except`` that would re-raise.

    Args:
        paths: URL paths to revalidate (e.g. ``["/licitacoes/saude"]``).
    """
    url = os.environ.get("FRONTEND_REVALIDATE_URL")
    secret = os.environ.get("REVALIDATE_SECRET")

    if not url or not secret:
        logger.debug(
            "revalidate_paths: FRONTEND_REVALIDATE_URL or REVALIDATE_SECRET not set, skipping"
        )
        return

    paths_list = list(paths)
    if not paths_list:
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"paths": paths_list},
                # NOTE: REVALIDATE_SECRET is intentionally never logged.
                headers={"x-revalidate-secret": secret},
            )
            resp.raise_for_status()
        logger.info(
            "seo_revalidate ok",
            extra={"event": "seo_revalidate", "paths": paths_list, "status": "ok"},
        )
    except Exception as exc:
        logger.warning(
            "seo_revalidate failed: %s",
            exc,
            extra={"event": "seo_revalidate", "paths": paths_list, "status": "failed"},
        )
        # Non-blocking Sentry breadcrumb — never re-raises.
        try:
            import sentry_sdk  # noqa: PLC0415

            sentry_sdk.add_breadcrumb(
                message=f"revalidate_paths failed: {exc}", level="warning"
            )
        except Exception:
            pass
