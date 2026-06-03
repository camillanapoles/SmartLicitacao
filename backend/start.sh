#!/bin/bash
# =============================================================================
# GTM-RESILIENCE-F01 AC6: Multi-process start script
# =============================================================================
# Supports three modes via PROCESS_TYPE env var:
#   web (default):    Uvicorn workers (FastAPI) — optionally colocated ARQ worker
#   worker:           ARQ background job worker only (LLM + Excel)
#   web+worker:       Both web + worker in same container (WORKER_COLOCATED compat)
#
# COST-OPT 2026-06-03: WORKER_COLOCATED=true starts ARQ worker as background
# subprocess in the same Railway container — eliminates need for separate
# bidiq-worker service (~$20/mo). Worker uses restart wrapper; SIGTERM
# propagates to both processes for graceful Railway shutdown.
#
# Railway deployment: Single service with PROCESS_TYPE=web and
# WORKER_COLOCATED=true replaces two separate services.

set -e

# ── Diagnostic: confirm start.sh is executing ───────────────────────────
# Railway filters stdout from entrypoint; redirect to stderr for visibility.
echo "[start.sh] DIAGNOSTIC: PID=$$ PROCESS_TYPE=${PROCESS_TYPE:-web} WORKER_COLOCATED=${WORKER_COLOCATED:-false} RUNNER=${RUNNER:-uvicorn} WORKERS=${WEB_CONCURRENCY:-2}" >&2

# ── Signal propagation ──────────────────────────────────────────────────
# When Railway sends SIGTERM (drainingSeconds=120), forward to both processes.
_uvicorn_pid=""
_worker_pid=""
_shutting_down=false

_forward_signal() {
  local sig="$1"
  echo "[start.sh] Received $sig — forwarding to child processes (uvicorn=$_uvicorn_pid, worker=$_worker_pid)"
  _shutting_down=true
  [ -n "$_uvicorn_pid" ] && kill "$sig" "$_uvicorn_pid" 2>/dev/null || true
  [ -n "$_worker_pid" ] && kill "$sig" "$_worker_pid" 2>/dev/null || true
}

trap '_forward_signal TERM' TERM
trap '_forward_signal INT' INT
trap '_forward_signal QUIT' QUIT

PROCESS_TYPE="${PROCESS_TYPE:-web}"

# ── ARQ Worker launcher (used by both worker-only and colocated modes) ──
_start_worker() {
  local mode_label="${1:-background}"
  echo "Starting ARQ worker process ($mode_label)..."
  # GTM-STAB-002 AC3: Restart wrapper — ARQ worker restarts on unexpected exit
  local _restart_delay="${WORKER_RESTART_DELAY:-5}"
  local _max_restarts="${WORKER_MAX_RESTARTS:-10}"
  local _restart_count=0
  while true; do
    # CRIT-051 AC3: --custom-log-dict redirects ARQ bootstrap logs to stdout.
    arq job_queue.WorkerSettings --custom-log-dict job_queue.arq_log_config
    local _exit_code=$?
    if [ "$_shutting_down" = "true" ]; then
      echo "ARQ worker exited (shutting down, code=$_exit_code)."
      break
    fi
    if [ $_exit_code -eq 0 ]; then
      echo "ARQ worker exited cleanly (code 0). Stopping."
      break
    fi
    _restart_count=$((_restart_count + 1))
    if [ $_restart_count -ge "$_max_restarts" ]; then
      echo "ARQ worker exceeded max restarts ($_max_restarts). Exiting."
      exit $_exit_code
    fi
    echo "ARQ worker exited with code $_exit_code (restart $_restart_count/$_max_restarts). Waiting ${_restart_delay}s..."
    sleep "$_restart_delay"
  done
}

# ── Uvicorn launcher (foreground) ───────────────────────────────────────
_start_uvicorn() {
  local workers="${WEB_CONCURRENCY:-2}"
  local limit_max_requests="${GUNICORN_MAX_REQUESTS:-10000}"
  local graceful_timeout="${UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN:-120}"
  local keep_alive="${GUNICORN_KEEP_ALIVE:-75}"
  local log_level="${UVICORN_LOG_LEVEL:-info}"
  local port="${PORT:-8000}"

  echo "Starting web process (uvicorn spawn-based workers=${workers})..."
  echo "  CRIT-083: spawn() avoids os.fork() — eliminates cryptography/OpenSSL SIGSEGV."
  echo "  Cross-worker SSE: Redis Streams (STORY-276). Graceful timeout: ${graceful_timeout}s"
  echo "  host=0.0.0.0, port=${port}, workers=${workers}, keep-alive=${keep_alive}s"
  echo "  ADR-MEMORY-BUDGET rotation: limit_max_requests=${limit_max_requests}"

  uvicorn main:app \
    --host "0.0.0.0" \
    --port "${port}" \
    --log-level "${log_level}" \
    --timeout-keep-alive "${keep_alive}" \
    --workers "${workers}" \
    --limit-max-requests "${limit_max_requests}" \
    --timeout-graceful-shutdown "${graceful_timeout}"
}

case "$PROCESS_TYPE" in
  web)
    # COST-OPT 2026-06-03: WORKER_COLOCATED=true eliminates separate Railway
    # service (~$20/mo). Worker runs as background subprocess with restart
    # wrapper. WEB_CONCURRENCY reduced to 1 by default when colocated to
    # stay within 1GB Railway memory limit.
    RUNNER="${RUNNER:-uvicorn}"

    if [ "$RUNNER" != "uvicorn" ]; then
      echo "ERROR: Only RUNNER=uvicorn is supported. RUNNER=gunicorn is deprecated (CRIT-083)."
      exit 1
    fi

    if [ "${WORKER_COLOCATED:-false}" = "true" ]; then
      echo "=== COST-OPT: Colocated mode — web + worker in same container ===" >&2
      echo "[start.sh] WORKER_COLOCATED=true, starting ARQ worker in background..." >&2
      # Reduce web concurrency when sharing memory with worker
      if [ -z "${WEB_CONCURRENCY}" ]; then
        export WEB_CONCURRENCY=1
        echo "  WEB_CONCURRENCY defaulted to 1 (colocated, ~500MB budget for worker)"
      fi
      # Start worker in background
      _start_worker "background" &
      _worker_pid=$!
      echo "  ARQ worker PID: $_worker_pid"
      # Start uvicorn in foreground (becomes main process for signal handling)
      _uvicorn_pid=$$
      _start_uvicorn
      # If uvicorn exits, kill worker and wait
      echo "[start.sh] uvicorn exited — stopping worker (PID $_worker_pid)..."
      kill "$_worker_pid" 2>/dev/null || true
      wait "$_worker_pid" 2>/dev/null || true
      echo "[start.sh] Both processes stopped."
      exit 0
    else
      # Original behavior: uvicorn only (exec replaces shell)
      exec uvicorn main:app \
        --host "0.0.0.0" \
        --port "${PORT:-8000}" \
        --log-level "${UVICORN_LOG_LEVEL:-info}" \
        --timeout-keep-alive "${GUNICORN_KEEP_ALIVE:-75}" \
        --workers "${WEB_CONCURRENCY:-2}" \
        --limit-max-requests "${GUNICORN_MAX_REQUESTS:-10000}" \
        --timeout-graceful-shutdown "${UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN:-120}"
    fi
    ;;
  worker)
    echo "Starting ARQ worker process (standalone)..."
    _start_worker "standalone"
    ;;
  *)
    echo "ERROR: Unknown PROCESS_TYPE='$PROCESS_TYPE'. Use 'web' or 'worker'."
    exit 1
    ;;
esac
