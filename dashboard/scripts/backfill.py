#!/usr/bin/env python3
"""
backfill.py — Historical bulk fetch for GridWatch AU using the Pro API.

Strategy
--------
The OpenElectricity Pro API supports date_start / date_end on:
  GET https://api.openelectricity.org.au/v4/stats/au/NEM/{region}/power?
        interval=1d&date_start=YYYY-MM-DD&date_end=YYYY-MM-DD

Rate limits (per your plan):
  - 5000 calls/day
  - Daily interval → up to 366 days per call
  - We have 5 NEM regions × N chunks = calls used

We fetch daily-interval data going back to 2010-01-01 (the practical NEM
renewable era) in 365-day chunks, appending each batch as a Parquet file to
data/ledger/ via the existing ParquetEventLedger adapter.

The ledger is append-only with deduplication on replay, so re-running is safe —
duplicate timestamps for the same (region, metric, fuel_tech) are silently
overwritten by the replay projection.

Usage
-----
    # from your gridwatch-au project root:
    python scripts/backfill.py

    # or limit to specific regions:
    python scripts/backfill.py --regions NSW1 VIC1

    # or limit date range:
    python scripts/backfill.py --start 2020-01-01 --end 2026-01-01

    # dry run (print chunks, don't fetch):
    python scripts/backfill.py --dry-run

Environment
-----------
    OPENELECTRICITY_API_KEY  — your Pro API key (or put in .env)

Output
------
    data/ledger/*.parquet    — one Parquet file per (region, batch)
    data/backfill.log        — progress log
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, UTC
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv

# ── add src/ to path so we can import gridwatch ──────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gridwatch.adapters.openelectricity import map_payload
from gridwatch.adapters.parquet_ledger import ParquetEventLedger
from gridwatch.contracts.ingest import IngestEvent
from gridwatch.contracts.regions import NEM_REGIONS

# ── config ───────────────────────────────────────────────────────────────────
load_dotenv(ROOT / ".env")
API_KEY = os.environ.get("OPENELECTRICITY_API_KEY", "")
BASE_URL = "https://api.openelectricity.org.au/v4"
LEDGER_DIR = ROOT / "data" / "ledger"
LOG_PATH = ROOT / "data" / "backfill.log"

# Per-call limits (from the API docs)
MAX_DAYS_PER_CALL = {
    "5m": 8,
    "1h": 32,
    "1d": 366,
    "1w": 366,
    "1M": 732,
}
CHUNK_DAYS = 365          # stay safely under the 366-day daily limit
RETRY_WAIT = 5            # seconds between retries
MAX_RETRIES = 3
INTER_REQUEST_SLEEP = 0.3 # polite delay between calls (≈3 req/s max)


def setup_logging(verbose: bool = False) -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8"),
    ]
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    return logging.getLogger("backfill")


def date_chunks(start: date, end: date, chunk_days: int):
    """Yield (chunk_start, chunk_end) pairs covering [start, end]."""
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=chunk_days), end)
        yield cur, nxt
        cur = nxt


def fetch_chunk(
    session: requests.Session,
    region: str,
    interval: str,
    date_start: date,
    date_end: date,
    logger: logging.Logger,
) -> dict | None:
    """
    Fetch one chunk from the Pro API.
    Returns the parsed JSON payload or None on unrecoverable failure.

    Endpoint: GET /v4/stats/au/NEM/{region}/power
    Params: interval, date_start, date_end
    """
    url = f"{BASE_URL}/stats/au/NEM/{region}/power"
    params = {
        "interval": interval,
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "User-Agent": "gridwatch-au/1.0 (+https://github.com/curlyjoeyaknow/gridwatch-au)",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"  Rate limited, waiting {wait}s…")
                time.sleep(wait)
                continue
            if resp.status_code == 400:
                logger.error(f"  Bad request: {resp.text[:200]}")
                return None
            if resp.status_code == 401:
                logger.error("  401 Unauthorised — check OPENELECTRICITY_API_KEY")
                sys.exit(1)
            logger.warning(f"  HTTP {resp.status_code} attempt {attempt}/{MAX_RETRIES}: {resp.text[:100]}")
        except requests.RequestException as e:
            logger.warning(f"  Network error attempt {attempt}/{MAX_RETRIES}: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT * attempt)

    logger.error(f"  All {MAX_RETRIES} attempts failed for {region} {date_start}→{date_end}")
    return None


def payload_to_events(
    payload: dict,
    region: str,
    batch_id: str,
    ingested_at: datetime,
) -> list[IngestEvent]:
    """Map a Pro API payload → IngestEvents using the existing adapter."""
    readings = map_payload(payload, region)
    return [
        IngestEvent.from_reading(
            r,
            source="openelectricity_pro",
            batch_id=batch_id,
            ingested_at=ingested_at,
        )
        for r in readings
    ]


def already_fetched_dates(ledger_dir: Path, region: str) -> set[date]:
    """
    Scan the ledger to find which dates already have data for this region.
    Reads the Parquet metadata (timestamps column) to avoid re-fetching.
    """
    try:
        import pyarrow.parquet as pq
        covered: set[date] = set()
        for pfile in ledger_dir.glob("*.parquet"):
            try:
                table = pq.read_table(pfile, columns=["region", "timestamp"])
                for row in table.to_pydict().get("timestamp", []):
                    if table.to_pydict()["region"][table.to_pydict()["timestamp"].index(row)] == region:
                        pass  # this approach is slow for large files
            except Exception:
                pass
        return covered  # returns empty — caller will rely on deduplication in replay instead
    except ImportError:
        return set()


def run_backfill(
    regions: list[str],
    start: date,
    end: date,
    interval: str,
    dry_run: bool,
    logger: logging.Logger,
) -> dict[str, int]:
    """Main backfill loop. Returns per-region event counts."""
    if not API_KEY and not dry_run:
        logger.error("OPENELECTRICITY_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    ledger = ParquetEventLedger(LEDGER_DIR)
    session = requests.Session()
    total_calls = 0
    total_events = 0
    counts: dict[str, int] = {}

    chunks = list(date_chunks(start, end, CHUNK_DAYS))
    total_calls_needed = len(regions) * len(chunks)
    logger.info(f"Backfill plan: {len(regions)} regions × {len(chunks)} chunks "
                f"= {total_calls_needed} API calls")
    logger.info(f"Date range: {start} → {end} | Interval: {interval}")
    logger.info(f"Ledger: {LEDGER_DIR}")

    if dry_run:
        logger.info("── DRY RUN (no API calls) ──")
        for region in regions:
            for chunk_start, chunk_end in chunks:
                logger.info(f"  Would fetch: {region} {chunk_start} → {chunk_end}")
        return {}

    for region in regions:
        region_events = 0
        logger.info(f"\n── {region} ──────────────────────────────────────────")

        for chunk_start, chunk_end in chunks:
            logger.info(f"  Fetching {chunk_start} → {chunk_end}…")
            ingested_at = datetime.now(UTC)
            batch_id = uuid4().hex

            payload = fetch_chunk(session, region, interval, chunk_start, chunk_end, logger)
            total_calls += 1

            if payload is None:
                logger.warning(f"  Skipping {chunk_start}→{chunk_end} (no data)")
                continue

            events = payload_to_events(payload, region, batch_id, ingested_at)
            if events:
                ledger.append(events)
                region_events += events_count = len(events)
                logger.info(f"  → {events_count} events appended")
            else:
                logger.warning(f"  → 0 events (empty payload?)")

            time.sleep(INTER_REQUEST_SLEEP)

        counts[region] = region_events
        total_events += region_events
        logger.info(f"  {region} total: {region_events} events")

    logger.info(f"\n{'─'*50}")
    logger.info(f"Backfill complete: {total_calls} API calls, {total_events} events total")
    logger.info(f"Per-region: {counts}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="GridWatch AU — historical backfill")
    parser.add_argument(
        "--regions", nargs="+", default=list(NEM_REGIONS),
        help=f"Regions to fetch (default: all NEM). Options: {' '.join(NEM_REGIONS)}"
    )
    parser.add_argument(
        "--start", default="2010-01-01",
        help="Start date YYYY-MM-DD (default: 2010-01-01)"
    )
    parser.add_argument(
        "--end", default=date.today().isoformat(),
        help="End date YYYY-MM-DD (default: today)"
    )
    parser.add_argument(
        "--interval", default="1d",
        choices=["5m", "1h", "1d", "1w", "1M"],
        help="Data interval (default: 1d — daily, 366 days/call)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan only, no API calls")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("GridWatch AU — Historical Backfill")
    logger.info(f"API key: {'set ✓' if API_KEY else 'NOT SET ✗'}")

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    run_backfill(
        regions=[r.upper() for r in args.regions],
        start=start,
        end=end,
        interval=args.interval,
        dry_run=args.dry_run,
        logger=logger,
    )


if __name__ == "__main__":
    main()
