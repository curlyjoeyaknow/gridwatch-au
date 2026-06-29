#!/usr/bin/env python3
"""
backfill.py — Historical bulk fetch for GridWatch AU using the OpenElectricity SDK.

Strategy
--------
Uses the official openelectricity Python SDK to fetch daily energy + emissions
data per NEM region, grouped by fueltech_group. Also fetches market data
(price + demand) per region.

Per-call limits (from API docs):
  daily interval → up to 366 days per call

We chunk in 365-day windows and fetch:
  - energy + emissions  → /v4/data/network/NEM  (per region, fueltech_group)
  - price + demand      → /v4/market/NEM        (per region)

Total calls: 5 regions × ceil(years/1) chunks × 2 endpoints = ~170 calls for
a full 2010→today backfill. Well within the 5000/day Pro limit.

Usage
-----
    python scripts/backfill.py
    python scripts/backfill.py --start 2020-01-01 --regions NSW1 VIC1
    python scripts/backfill.py --dry-run

Environment
-----------
    OPENELECTRICITY_API_KEY  — Pro API key (or in .env at project root)

Output
------
    data/ledger/*.parquet    — one Parquet file per batch
    data/backfill.log        — append-only progress log
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

# ── add src/ to path ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gridwatch.adapters.parquet_ledger import ParquetEventLedger
from gridwatch.contracts.fueltech import FuelCategory, classify
from gridwatch.contracts.ingest import IngestEvent
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.contracts.regions import NEM_REGIONS

# ── config ────────────────────────────────────────────────────────────────────
load_dotenv(ROOT / ".env")

LEDGER_DIR = ROOT / "data" / "ledger"
LOG_PATH   = ROOT / "data" / "backfill.log"

CHUNK_DAYS         = 365   # safely under the 366-day daily limit
INTER_CALL_SLEEP   = 0.5   # polite gap between SDK calls
MAX_RETRIES        = 3
RETRY_WAIT         = 10    # seconds between retries (longer for SDK errors)

# fueltech_group values returned by the API → our FuelCategory mapping
FUELTECH_GROUP_MAP: dict[str, FuelCategory] = {
    "solar":       FuelCategory.SOLAR,
    "wind":        FuelCategory.WIND,
    "hydro":       FuelCategory.HYDRO,
    "bioenergy":   FuelCategory.BIOENERGY,
    "coal":        FuelCategory.COAL,
    "gas":         FuelCategory.GAS,
    "distillate":  FuelCategory.DISTILLATE,
    "battery":     FuelCategory.BATTERY,
    "pumps":       FuelCategory.PUMPS,
    "imports":     FuelCategory.IMPORT,
    "exports":     FuelCategory.EXPORT,
    # catch-alls
    "nuclear":     FuelCategory.OTHER,
    "other":       FuelCategory.OTHER,
}


# ── logging ───────────────────────────────────────────────────────────────────

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


# ── date chunking ─────────────────────────────────────────────────────────────

def date_chunks(start: date, end: date, chunk_days: int):
    """Yield (chunk_start, chunk_end) pairs covering [start, end)."""
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=chunk_days), end)
        yield cur, nxt
        cur = nxt


# ── SDK helpers ───────────────────────────────────────────────────────────────

def make_client():
    """Return a synchronous OEClient (SDK handles auth via env var)."""
    from openelectricity import OEClient
    return OEClient()


def fetch_energy_chunk(
    client,
    region: str,
    date_start: date,
    date_end: date,
    logger: logging.Logger,
):
    """
    Fetch daily energy + emissions per fueltech_group for one region/chunk.
    Returns the TimeSeriesResponse or None on unrecoverable failure.
    """
    from openelectricity.types import DataMetric

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.get_network_data(
                network_code="NEM",
                metrics=[DataMetric.ENERGY, DataMetric.EMISSIONS],
                interval="1d",
                date_start=datetime.combine(date_start, datetime.min.time()),
                date_end=datetime.combine(date_end, datetime.min.time()),
                network_region=region,
                primary_grouping="network_region",
                secondary_grouping="fueltech_group",
            )
            return resp
        except Exception as e:
            err = str(e)
            logger.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed for energy {region} {date_start}→{date_end}: {err[:120]}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT * attempt)

    logger.error(f"  All retries failed for energy {region} {date_start}→{date_end}")
    return None


def fetch_market_chunk(
    client,
    region: str,
    date_start: date,
    date_end: date,
    logger: logging.Logger,
):
    """
    Fetch daily price + demand for one region/chunk.
    Returns the TimeSeriesResponse or None on failure.
    """
    from openelectricity.types import MarketMetric

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.get_market(
                network_code="NEM",
                metrics=[MarketMetric.PRICE, MarketMetric.DEMAND],
                interval="1d",
                date_start=datetime.combine(date_start, datetime.min.time()),
                date_end=datetime.combine(date_end, datetime.min.time()),
                network_region=region,
                primary_grouping="network_region",
            )
            return resp
        except Exception as e:
            err = str(e)
            logger.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed for market {region} {date_start}→{date_end}: {err[:120]}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT * attempt)

    logger.error(f"  All retries failed for market {region} {date_start}→{date_end}")
    return None


# ── response → IngestEvent conversion ────────────────────────────────────────

def energy_response_to_events(
    resp,
    region: str,
    batch_id: str,
    ingested_at: datetime,
) -> list[IngestEvent]:
    """Convert a TimeSeriesResponse (energy/emissions) → IngestEvents."""
    events: list[IngestEvent] = []
    if not resp or not resp.data:
        return events

    for series in resp.data:
        metric = series.metric          # "energy" | "emissions"
        unit   = series.unit            # "MWh" | "tCO2e"
        interval_minutes = 1440         # 1d

        for result in series.results:
            # columns.fueltech_group may be None if the API doesn't group
            ft_raw = result.columns.fueltech_group
            fuel_cat = FUELTECH_GROUP_MAP.get(ft_raw.lower(), FuelCategory.OTHER) if ft_raw else None

            for point in result.data:
                if point.value is None:
                    continue
                ts = point.timestamp.replace(tzinfo=None)  # strip tz for our domain model

                if metric == "energy":
                    reading = PowerReading(
                        region=region,
                        timestamp=ts,
                        value=point.value,
                        interval_minutes=interval_minutes,
                        fuel=fuel_cat,
                    )
                elif metric == "emissions":
                    reading = EmissionReading(
                        region=region,
                        timestamp=ts,
                        value=point.value,
                        interval_minutes=interval_minutes,
                        fuel=fuel_cat or FuelCategory.OTHER,
                    )
                else:
                    continue

                events.append(
                    IngestEvent.from_reading(
                        reading,
                        source="openelectricity_pro",
                        batch_id=batch_id,
                        ingested_at=ingested_at,
                    )
                )

    return events


def market_response_to_events(
    resp,
    region: str,
    batch_id: str,
    ingested_at: datetime,
) -> list[IngestEvent]:
    """Convert a market TimeSeriesResponse (price/demand) → IngestEvents."""
    events: list[IngestEvent] = []
    if not resp or not resp.data:
        return events

    interval_minutes = 1440  # 1d

    for series in resp.data:
        metric = series.metric   # "price" | "demand"

        for result in series.results:
            for point in result.data:
                if point.value is None:
                    continue
                ts = point.timestamp.replace(tzinfo=None)

                if metric == "price":
                    reading = PriceReading(
                        region=region,
                        timestamp=ts,
                        value=point.value,
                        interval_minutes=interval_minutes,
                    )
                elif metric == "demand":
                    reading = DemandReading(
                        region=region,
                        timestamp=ts,
                        value=point.value,
                        interval_minutes=interval_minutes,
                    )
                else:
                    continue

                events.append(
                    IngestEvent.from_reading(
                        reading,
                        source="openelectricity_pro",
                        batch_id=batch_id,
                        ingested_at=ingested_at,
                    )
                )

    return events


# ── main backfill loop ────────────────────────────────────────────────────────

def run_backfill(
    regions: list[str],
    start: date,
    end: date,
    dry_run: bool,
    logger: logging.Logger,
) -> dict[str, int]:
    api_key = os.environ.get("OPENELECTRICITY_API_KEY", "")
    logger.info(f"API key: {'set ✓' if api_key else 'NOT SET ✗'}")
    if not api_key and not dry_run:
        logger.error("OPENELECTRICITY_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    chunks = list(date_chunks(start, end, CHUNK_DAYS))
    # 2 endpoints per region per chunk
    total_calls = len(regions) * len(chunks) * 2
    logger.info(f"Backfill plan: {len(regions)} regions × {len(chunks)} chunks × 2 endpoints = {total_calls} API calls")
    logger.info(f"Date range: {start} → {end} | Interval: 1d")
    logger.info(f"Ledger: {LEDGER_DIR}")

    if dry_run:
        logger.info("── DRY RUN (no API calls) ──")
        for region in regions:
            for cs, ce in chunks:
                logger.info(f"  Would fetch: {region} energy+emissions {cs}→{ce}")
                logger.info(f"  Would fetch: {region} price+demand     {cs}→{ce}")
        return {}

    ledger = ParquetEventLedger(LEDGER_DIR)
    counts: dict[str, int] = {}
    total_events = 0

    client = make_client()

    for region in regions:
        region_events = 0
        logger.info(f"\n── {region} ──────────────────────────────────────────")

        for chunk_start, chunk_end in chunks:
            ingested_at = datetime.now(UTC).replace(tzinfo=None)
            all_events: list[IngestEvent] = []

            # ── energy + emissions ──
            logger.info(f"  [{region}] energy+emissions {chunk_start} → {chunk_end}…")
            energy_resp = fetch_energy_chunk(client, region, chunk_start, chunk_end, logger)
            if energy_resp:
                batch_id = uuid4().hex
                evts = energy_response_to_events(energy_resp, region, batch_id, ingested_at)
                all_events.extend(evts)
                logger.info(f"    → {len(evts)} energy/emissions events")
            else:
                logger.warning(f"    → skipped energy+emissions (no data)")

            time.sleep(INTER_CALL_SLEEP)

            # ── price + demand ──
            logger.info(f"  [{region}] price+demand    {chunk_start} → {chunk_end}…")
            market_resp = fetch_market_chunk(client, region, chunk_start, chunk_end, logger)
            if market_resp:
                batch_id = uuid4().hex
                evts = market_response_to_events(market_resp, region, batch_id, ingested_at)
                all_events.extend(evts)
                logger.info(f"    → {len(evts)} price/demand events")
            else:
                logger.warning(f"    → skipped price+demand (no data)")

            time.sleep(INTER_CALL_SLEEP)

            # ── append to ledger ──
            if all_events:
                ledger.append(all_events)
                region_events += len(all_events)
                logger.info(f"  chunk total: {len(all_events)} events appended")

        counts[region] = region_events
        total_events += region_events
        logger.info(f"  {region} total: {region_events} events")

    logger.info(f"\n{'─'*50}")
    logger.info(f"Backfill complete: {total_events} total events")
    logger.info(f"Per-region: {counts}")
    return counts


# ── CLI ───────────────────────────────────────────────────────────────────────

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
    parser.add_argument("--dry-run", action="store_true", help="Print plan only, no API calls")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("GridWatch AU — Historical Backfill")

    run_backfill(
        regions=[r.upper() for r in args.regions],
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        dry_run=args.dry_run,
        logger=logger,
    )


if __name__ == "__main__":
    main()
