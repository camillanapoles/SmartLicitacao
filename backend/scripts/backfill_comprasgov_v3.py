"""Backfill ComprasGov v3 data into pncp_raw_bids — SPIKE RESULT: NO-GO.

SPIKE-SEO-BACKFILL (Issue #1040, 2026-05-10):
  The ComprasGov v3 API (https://dadosabertos.compras.gov.br) has been returning
  HTTP 404 for ALL endpoints since at least 2026-03-03. The API is hosted on Azure
  infrastructure but has no active routes responding to requests.

  This script is intentionally a NO-GO stub. It documents the intent and the
  blockers so a future implementor can pick up if the API comes back online.

ACTUAL RECOMMENDATION (from spike):
  Use PCP v2 instead — see `backfill_pcp_v2.py` (to be created per story follow-up).
  PCP v2 has confirmed Feb 2026 (5,536 records) and Mar 2026 (7,948 records) data
  accessible at the existing endpoint.

  For PNCP gap coverage, run the existing script first:
    cd backend
    python -m scripts.backfill_pncp_historical --days 120

Usage (when/if API comes back):
    cd backend
    python -m scripts.backfill_comprasgov_v3 --dry-run

References:
  - Spike document: docs/spikes/2026-05/SPIKE-SEO-BACKFILL-fev-mar-2026.md
  - Existing ComprasGov adapter: backend/clients/compras_gov_client.py
  - Contract tests (note API down): backend/tests/contracts/test_compras_gov_contract.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date

logger = logging.getLogger("backfill_comprasgov_v3")

# Months confirmed as having zero coverage in pncp_raw_bids
BACKFILL_WINDOWS = [
    (date(2026, 2, 1), date(2026, 2, 28)),
    (date(2026, 3, 1), date(2026, 3, 31)),
]

# TODO (when API comes back): implement using ComprasGovAdapter
# from clients.compras_gov_client import ComprasGovAdapter
# from ingestion.loader import bulk_upsert


async def _check_api_availability() -> bool:
    """Probe ComprasGov v3 API health before attempting backfill.

    Returns True if API is reachable, False if still down.
    """
    import httpx

    probe_url = (
        "https://dadosabertos.compras.gov.br"
        "/modulo-legado/1_consultarLicitacao"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(probe_url, params={"pagina": 1, "tamanhoPagina": 1})
        if resp.status_code == 404:
            logger.error(
                "ComprasGov v3 API returned 404 — still down. "
                "Use PCP v2 backfill instead. "
                "See docs/spikes/2026-05/SPIKE-SEO-BACKFILL-fev-mar-2026.md"
            )
            return False
        return resp.status_code == 200
    except Exception as exc:
        logger.error("ComprasGov v3 API unreachable: %s", exc)
        return False


async def _main(dry_run: bool) -> int:
    logger.warning(
        "=== ComprasGov v3 Backfill — SPIKE RESULT: NO-GO ==="
    )
    logger.warning(
        "API has been returning HTTP 404 since 2026-03-03. "
        "Checking current availability..."
    )

    available = await _check_api_availability()
    if not available:
        logger.error(
            "ComprasGov v3 API is unavailable. Aborting. "
            "Alternative: run `python -m scripts.backfill_pncp_historical --days 120` "
            "for PNCP coverage, or implement PCP v2 backfill for Feb/Mar 2026 data."
        )
        return 1

    # TODO: If we reach here, API is back online. Implement:
    # 1. For each (date_start, date_end) in BACKFILL_WINDOWS:
    #    async with ComprasGovAdapter() as client:
    #        async for record in client.fetch(date_start.isoformat(), date_end.isoformat()):
    #            # Convert UnifiedProcurement -> pncp_raw_bids row dict
    #            # Challenge: modalidade_id is NOT NULL in pncp_raw_bids
    #            # Need: migration to drop NOT NULL, or a sentinel value (e.g., 999)
    #            pass
    # 2. Call bulk_upsert(rows) in batches of 500
    # 3. Schema compatibility gaps to resolve before implementing:
    #    - modalidade_id: NOT NULL constraint — needs migration or sentinel
    #    - orgao_cnpj: not available in ComprasGov legacy endpoint
    #    - valor_total_estimado: not in legacy listing (may need detail call)
    #    - esfera_id: ComprasGov is federal-only → hardcode "F"

    logger.info("API is available. Implementation TODO — see comments in this file.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill ComprasGov v3 data into pncp_raw_bids. "
            "SPIKE RESULT: NO-GO — API currently down. "
            "See docs/spikes/2026-05/SPIKE-SEO-BACKFILL-fev-mar-2026.md"
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Check API availability only, do not upsert data (default: True).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    return asyncio.run(_main(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
