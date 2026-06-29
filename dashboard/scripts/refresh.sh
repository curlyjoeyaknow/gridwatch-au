#!/usr/bin/env bash
# refresh.sh — fetch latest 7 days + materialize views
# Run daily (e.g. via cron or launchd) from your gridwatch-au project root.
#
# Usage:
#   ./scripts/refresh.sh              # fetch last 7 days + materialize all views
#   ./scripts/refresh.sh --full       # full backfill from 2010 + materialize
#   ./scripts/refresh.sh --materialize-only  # skip fetch, just re-materialize

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
LOG="data/refresh.log"
mkdir -p data/views data/ledger

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() { echo "[$(timestamp)] $*" | tee -a "$LOG"; }

log "─── GridWatch AU refresh ───────────────────────────────────"

case "${1:-}" in
  --full)
    log "Full backfill from 2010-01-01…"
    $PYTHON scripts/backfill.py --start 2010-01-01 --interval 1d
    ;;
  --materialize-only)
    log "Skipping fetch, materializing only."
    ;;
  *)
    # Daily refresh: fetch the last 10 days (overlapping window ensures no gaps)
    START=$(python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(days=10)).isoformat())")
    log "Incremental fetch from $START…"
    $PYTHON scripts/backfill.py --start "$START" --interval 1d
    ;;
esac

log "Materializing DuckDB views…"
$PYTHON scripts/materialize.py

log "Done. Views: $(ls data/views/*.json 2>/dev/null | wc -l | tr -d ' ') files"
