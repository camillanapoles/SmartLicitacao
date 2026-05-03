#!/bin/bash
# =============================================================================
# SEN-BE-010 + ADR-MEMORY-BUDGET Component B: RSS emergency kill
# =============================================================================
# Watches gunicorn/uvicorn worker processes and SIGTERMs any worker exceeding
# the critical RSS threshold (>5GB instantâneo). gunicorn/uvicorn auto-replaces
# killed workers, so service stays available.
#
# Usage (sidecar/cron):
#   * * * * * /app/scripts/rss_supervisor.sh >> /var/log/rss_supervisor.log
#
# Or as background daemon in start.sh:
#   /app/scripts/rss_supervisor.sh &
#
# Memory references:
#   - feedback_pool_leak_caller_timeout_vs_sql_timeout (5.5GB sustained Stage 4-7)
#   - feedback_chief_warm_stage5plus_no_pivot (warm continuation 7× failed)
#   - ADR docs/adr/MEMORY-BUDGET.md (3-tier: 2.5GB warn / 4GB alert / 5GB critical)
#
# Tuning:
#   RSS_CRITICAL_BYTES — kill threshold (default 5_000_000_000 = ~5GB)
#   RSS_CHECK_INTERVAL — seconds between checks (default 30)
#   RSS_DRY_RUN=true   — log without sending SIGTERM (audit mode)
#
# Exits cleanly when no matching workers remain (graceful shutdown).
# =============================================================================

set -e

RSS_CRITICAL_BYTES="${RSS_CRITICAL_BYTES:-5000000000}"
RSS_CHECK_INTERVAL="${RSS_CHECK_INTERVAL:-30}"
RSS_DRY_RUN="${RSS_DRY_RUN:-false}"
WORKER_PATTERN="${WORKER_PATTERN:-uvicorn|gunicorn.*main:app}"

log() {
  echo "[rss_supervisor] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
}

while true; do
  # `ps` columns: pid, rss (in KB), command. We only flag matching processes.
  # Subshell `|| true` guards against grep exit 1 (no matches) under future pipefail.
  ps -eo pid,rss,command | (grep -E "$WORKER_PATTERN" || true) | grep -v grep | while read -r pid rss_kb cmd; do
    rss_bytes=$((rss_kb * 1024))
    if [ "$rss_bytes" -gt "$RSS_CRITICAL_BYTES" ]; then
      rss_mb=$((rss_bytes / 1024 / 1024))
      log "CRITICAL pid=$pid rss=${rss_mb}MB cmd='$cmd' (threshold ${RSS_CRITICAL_BYTES} bytes)"
      if [ "$RSS_DRY_RUN" = "true" ]; then
        log "  DRY_RUN: would SIGTERM pid=$pid"
      else
        log "  SIGTERM pid=$pid"
        kill -TERM "$pid" || log "  WARN: kill -TERM pid=$pid failed"
      fi
    fi
  done
  sleep "$RSS_CHECK_INTERVAL"
done
