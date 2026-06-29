# GridWatch AU — Materialization Layer Integration Guide

> **UN SDG 7 — Affordable and Clean Energy**  
> This guide explains how `scripts/materialize.py` slots into the existing Python ingestion flow, what it produces, and how the Express + React frontend consumes it.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER (Python — your existing gridwatch-au repo)         │
│                                                                     │
│  gridwatch CLI / backfill.py                                        │
│    └─ JsonlEventLedger  →  data/ledger/ledger.jsonl                │
│    └─ ParquetEventLedger →  data/ledger/*.parquet                   │
│         (both are append-only; the materializer reads either/both)  │
└────────────────────────────┬────────────────────────────────────────┘
                             │  python scripts/materialize.py
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MATERIALIZATION LAYER (DuckDB — one-shot, in-memory)               │
│                                                                     │
│  1. Read ledger → staging table                                     │
│  2. Deduplicate by (region, metric, fuel_tech, timestamp)           │
│     keeping latest ingested_at  — mirrors replay_to_regions()       │
│  3. Join fuel taxonomy (mirrors fueltech.py FuelCategory exactly)   │
│  4. Run SQL aggregations per grain                                  │
│  5. Write JSON views to  data/views/                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │  static JSON files
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  EXPRESS API  (server/routes.ts)                                     │
│                                                                     │
│  GET /api/views/:name   →  reads data/views/<name>.json             │
│  GET /api/status        →  reads data/views/last_updated.json       │
│  GET /api/live          →  free 7d API fallback (no ledger needed)  │
└────────────────────────────┬────────────────────────────────────────┘
                             │  JSON over HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  REACT FRONTEND                                                     │
│  hooks/useViews.ts  →  useGrain() / useSummary() / useRawRecent()  │
│  pages/  →  Dashboard / Usage / Costs / Trends / DataTable          │
└─────────────────────────────────────────────────────────────────────┘
```

**Key property:** The Express server is a pure static file server. It reads pre-built JSON files from disk. There is no Python runtime involved at request time — cold-start latency is zero.

---

## Output Files (data/views/)

| File | Shape | Used by |
|---|---|---|
| `summary.json` | `RegionSummary[]` | Dashboard KPI cards, state comparison table |
| `daily.json` | `GrainView` | Usage stacked area (daily grain) |
| `weekly.json` | `GrainView` | Usage stacked area (weekly grain) |
| `monthly.json` | `GrainView` | Usage/Costs/Trends (default grain) |
| `yearly.json` | `GrainView` | Trends yearly bar chart |
| `raw_recent.json` | `{ count, rows: RawRow[] }` | Data table (last 8 days) |
| `last_updated.json` | `LastUpdated` | Status badge, `/api/status` |

### GrainView shape (all grain files share this)

```json
{
  "grain": "monthly",
  "periods": ["2010-07", "2010-08", …, "2026-06"],
  "regions": {
    "NSW1": [
      {
        "period": "2010-07",
        "fuel": {
          "SOLAR": 12345.6,
          "WIND":  89012.3,
          "COAL": 456789.0,
          "GAS":  23456.7,
          "HYDRO": 7890.1
        },
        "renewable_share_pct": 18.34,
        "total_gen_mwh": 589534.7,
        "avg_price": 45.23,
        "peak_price": 14200.0,
        "min_price": -1000.0,
        "avg_demand_mw": 8956.2,
        "peak_demand_mw": 13400.0,
        "total_emissions_tco2e": 412345.6
      }
    ],
    "QLD1": [ … ],
    "VIC1": [ … ],
    "SA1":  [ … ],
    "TAS1": [ … ]
  }
}
```

The `fuel` keys are **category strings** matching `FUEL_META` in `views.ts`
(`SOLAR`, `WIND`, `HYDRO`, `BIOENERGY`, `COAL`, `GAS`, `DISTILLATE`, `BATTERY`, `PUMPS`).
Multiple raw vendor fuel techs roll up into the same category
(e.g. `solar_utility` + `solar_rooftop` → `SOLAR`).

---

## Ledger Format Support

The script auto-detects which ledger(s) exist and merges them:

```
data/ledger/
  ledger.jsonl          ← JsonlEventLedger (CLI bulk_fetch)
  abc123-de.parquet     ← ParquetEventLedger (backfill.py)
  def456-gh.parquet
```

| Invocation | Behaviour |
|---|---|
| `python scripts/materialize.py` | Auto-detect: reads both `ledger.jsonl` and `*.parquet` from `data/ledger/` |
| `python scripts/materialize.py --ledger data/ledger/ledger.jsonl` | JSONL only (explicit file path) |
| `python scripts/materialize.py --ledger data/ledger` | Directory mode: both formats |

The deduplication step handles overlaps between formats — if the same reading appears in both the JSONL and a Parquet file, only the one with the latest `ingested_at` is kept. This mirrors `replay_to_regions()` exactly.

---

## Integrating with the Existing Python Ingestion Flow

### Option A — After every CLI bulk_fetch (JSONL ledger)

The CLI's menu option **11 (Bulk fetch → append-only ledger)** writes to a JSONL or Parquet file you specify. After each run, call materialize:

```bash
# 1. Fetch all regions → JSONL ledger
gridwatch
# → choose 11 → jsonl → data/ledger/ledger.jsonl

# 2. Materialize
python scripts/materialize.py

# 3. Start the dashboard (or it's already running — it reads new files immediately)
node dist/index.cjs
```

### Option B — After backfill.py (Parquet ledger, recommended for large history)

```bash
# 1. Backfill from 2010 (Pro API, ~5000 calls/day limit)
python scripts/backfill.py --start 2010-01-01 --interval 1d

# 2. Materialize (reads data/ledger/*.parquet automatically)
python scripts/materialize.py

# 3. Serve
node dist/index.cjs
```

### Option C — Calling materialize from within the Python backend

You can call `materialize.py` as a subprocess from any Python script, or import
the functions directly if you want to trigger materialization from your Flask web layer:

```python
# Option C1: subprocess (cleanest — no import pollution)
import subprocess, sys
result = subprocess.run(
    [sys.executable, "scripts/materialize.py", "--views", "summary", "daily", "monthly"],
    cwd="/path/to/gridwatch-au",
    capture_output=True, text=True,
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)

# Option C2: direct function call (faster for incremental rebuilds)
import sys
sys.path.insert(0, "scripts")          # or set PYTHONPATH
from materialize import get_con, build_summary, build_timeseries, VIEWS_DIR
from pathlib import Path
import logging, time

logger = logging.getLogger("materialize")
con = get_con(Path("data/ledger"), logger)
t0 = time.perf_counter()
build_summary(con, VIEWS_DIR, logger)
build_timeseries(con, "monthly", VIEWS_DIR, logger)
# … etc.
```

### Option D — Automated daily refresh (cron / shell script)

A convenience wrapper already exists at `scripts/refresh.sh`:

```bash
#!/usr/bin/env bash
# scripts/refresh.sh — incremental daily refresh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting GridWatch refresh"

# 1. Incremental fetch (last 7d to catch any gaps)
python scripts/backfill.py --start "$(date -u -d '7 days ago' +%Y-%m-%d)" --interval 1d

# 2. Materialize all views
python scripts/materialize.py

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Refresh complete"
```

Add to crontab (runs daily at 2 AM AEST = 4 PM UTC):

```cron
0 16 * * * cd /path/to/gridwatch-au && bash scripts/refresh.sh >> logs/refresh.log 2>&1
```

---

## Deduplication Logic (Critical Detail)

The materializer implements the same deduplication as `replay_to_regions()`:

```
For each unique (region, metric, fuel_tech, timestamp):
    keep the row with the latest ingested_at
```

This means you can safely re-ingest overlapping date ranges (e.g. fetching the
last 7 days every day). Revised readings (later `ingested_at`) automatically
supersede older ones. You never need to delete from the ledger.

In SQL:
```sql
WITH ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY region, metric, COALESCE(fuel_tech,'__null__'), timestamp
            ORDER BY ingested_at DESC
        ) AS rn
    FROM raw_ledger
)
SELECT * FROM ranked WHERE rn = 1
```

---

## Performance

| Ledger size | Materialization time (M2 MacBook) |
|---|---|
| 7 days live data (~200k events) | ~0.5 s |
| 1 year (~5M events) | ~2–4 s |
| 15 years full history (~60M events) | ~20–40 s |

DuckDB is columnar and vectorised — it reads Parquet natively and the JSONL
reader batches IO. For a 15-year history you should expect the `monthly.json`
to be ~200–400 KB and `daily.json` to be ~5–10 MB (well within browser budget).

---

## Running Only Specific Views

Useful for incremental refreshes (e.g. after a live 7d fetch, only rebuild
`raw_recent` and `summary` — the historical grains are unchanged):

```bash
# After a daily live fetch (quick, <1s)
python scripts/materialize.py --views summary raw_recent

# Full rebuild (after a large backfill)
python scripts/materialize.py

# Only monthly + yearly (for Trends page)
python scripts/materialize.py --views monthly yearly

# Adjust raw_recent window
python scripts/materialize.py --views raw_recent --raw-recent-days 14
```

---

## Troubleshooting

### "duckdb not installed"
```bash
pip install duckdb          # DuckDB only (no pyarrow needed for JSONL)
pip install duckdb pyarrow  # Both — needed if you use Parquet ledger too
```

### "JSONL ledger not found"
The default path is `data/ledger/ledger.jsonl` (relative to the repo root).
Either run `gridwatch` CLI option 11 first, or pass `--ledger` explicitly:
```bash
python scripts/materialize.py --ledger /absolute/path/to/ledger.jsonl
```

### Empty views after materialization
Check the `last_updated.json` — if `total_events` is 0, the ledger is empty.
Run the CLI bulk_fetch or `backfill.py` first.

### "FuelCategory.OTHER" in fuel dict
Unknown raw fuel tech strings (vendor additions, typos) map to `OTHER`. Add them
to `FUEL_TAXONOMY` in `materialize.py` *and* `_TAXONOMY` in `fueltech.py` to
keep both in sync.

### NaN / null in JSON output
DuckDB `AVG()` over an empty set returns `NULL`, which Python serialises as
`None` → JSON `null`. The frontend's `views.ts` types allow `null` for optional
fields (price, demand, emissions). All chart code uses null-checks before
rendering — this is expected and safe.

---

## File Locations Summary

```
gridwatch-au/              ← your Python repo root
  src/gridwatch/
    adapters/jsonl_ledger.py    ← JsonlEventLedger (writes ledger.jsonl)
    adapters/parquet_ledger.py  ← ParquetEventLedger (writes *.parquet)
    contracts/fueltech.py       ← FuelTech taxonomy (keep in sync with materialize.py)
    domain/replay.py            ← replay_to_regions() — dedup logic mirrored in SQL
    cli.py                      ← gridwatch CLI (option 11 = bulk_fetch)
  data/
    ledger/
      ledger.jsonl              ← JSONL ledger (JsonlEventLedger)
      *.parquet                 ← Parquet ledger (ParquetEventLedger / backfill.py)
    views/                      ← Materializer output (read by Express)
      summary.json
      daily.json
      weekly.json
      monthly.json
      yearly.json
      raw_recent.json
      last_updated.json
  scripts/
    backfill.py                 ← Pro API historical fetch → Parquet ledger
    materialize.py              ← THIS SCRIPT — DuckDB → JSON views
    refresh.sh                  ← Shell wrapper for daily cron
```
