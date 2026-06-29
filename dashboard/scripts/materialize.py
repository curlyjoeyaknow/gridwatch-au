#!/usr/bin/env python3
"""
materialize.py — DuckDB materialization layer for GridWatch AU.

Reads the append-only ledger (JSONL *or* Parquet, auto-detected), runs SQL
aggregations via DuckDB, and writes pre-built JSON views that the Express
server serves statically — no Python runtime needed at request time.

Ledger formats supported
────────────────────────
  JSONL   data/ledger/ledger.jsonl      (JsonlEventLedger — one event per line)
  Parquet data/ledger/*.parquet         (ParquetEventLedger — one file per batch)
  Both    if both exist, they are merged and deduplicated together

Auto-detection: pass --ledger to a directory → Parquet mode.
                pass --ledger to a *.jsonl file → JSONL mode.
                (default: data/ledger, tries both and merges)

Views written to data/views/
─────────────────────────────
  last_updated.json   — ISO timestamp + ledger stats
  summary.json        — per-region KPIs over the full ledger window
  daily.json          — day-grain:  fuel mix × price × demand × emissions
  weekly.json         — week-grain  (ISO week, Mon–Sun)
  monthly.json        — month-grain
  yearly.json         — financial-year grain (Jul–Jun, e.g. "FY2024")
  raw_recent.json     — last 8 days of raw readings for the Data table

JSON shapes (match views.ts exactly)
─────────────────────────────────────
  summary.json  → RegionSummary[]
  *.json grains → GrainView  { grain, periods, regions: { NSW1: PeriodRow[] } }
  PeriodRow     → { period, fuel:{SOLAR:mwh,…}, renewable_share_pct, total_gen_mwh,
                    avg_price, peak_price, min_price,
                    avg_demand_mw, peak_demand_mw, total_emissions_tco2e }
  raw_recent    → { count, rows: RawRow[] }

Usage
─────
    # from gridwatch-au project root (auto-detects jsonl + parquet):
    python scripts/materialize.py

    # only rebuild specific views:
    python scripts/materialize.py --views summary daily monthly

    # point at an explicit JSONL file:
    python scripts/materialize.py --ledger data/ledger/ledger.jsonl

    # point at a Parquet directory:
    python scripts/materialize.py --ledger data/ledger

    # verbose + dry-run check:
    python scripts/materialize.py --verbose

The script is idempotent — run it after every backfill or daily ingest.
An empty ledger produces empty-but-valid JSON files (the frontend gracefully
shows "no data" states).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = ROOT / "data" / "ledger"
VIEWS_DIR = ROOT / "data" / "views"

ALL_VIEWS = ["summary", "daily", "weekly", "monthly", "yearly", "raw_recent"]

# ── fuel taxonomy (mirrors fueltech.py exactly) ───────────────────────────────
# (raw_vendor_name, CATEGORY, display_name, is_renewable, counts_as_generation)
FUEL_TAXONOMY = [
    ("solar_utility",             "SOLAR",       "Solar (utility)",              True,  True),
    ("solar_rooftop",             "SOLAR",       "Solar (rooftop)",               True,  True),
    ("wind",                      "WIND",        "Wind",                          True,  True),
    ("hydro",                     "HYDRO",       "Hydro",                         True,  True),
    ("bioenergy_biomass",         "BIOENERGY",   "Bioenergy (biomass)",            True,  True),
    ("bioenergy_biogas",          "BIOENERGY",   "Bioenergy (biogas)",             True,  True),
    ("coal_black",                "COAL",        "Black coal",                    False, True),
    ("coal_brown",                "COAL",        "Brown coal",                    False, True),
    ("gas_ccgt",                  "GAS",         "Gas (CCGT)",                    False, True),
    ("gas_ocgt",                  "GAS",         "Gas (OCGT)",                    False, True),
    ("gas_recip",                 "GAS",         "Gas (reciprocating)",           False, True),
    ("gas_steam",                 "GAS",         "Gas (steam)",                   False, True),
    ("gas_wcmg",                  "GAS",         "Gas (waste coal mine gas)",     False, True),
    ("distillate",                "DISTILLATE",  "Distillate",                    False, True),
    ("battery_charging",          "BATTERY",     "Battery (charging)",            False, False),
    ("battery_discharging",       "BATTERY",     "Battery (discharging)",         False, False),
    ("pumps",                     "PUMPS",        "Pumps",                        False, False),
    ("imports",                   "IMPORT",       "Imports",                      False, False),
    ("exports",                   "EXPORT",       "Exports",                      False, False),
    ("curtailment_solar_utility", "CURTAILMENT",  "Curtailment (solar)",          False, False),
    ("curtailment_wind",          "CURTAILMENT",  "Curtailment (wind)",           False, False),
]


# ── logging ───────────────────────────────────────────────────────────────────
def setup_logging(verbose: bool = False) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("materialize")


# ── ledger loading ────────────────────────────────────────────────────────────
def _load_jsonl(path: Path, con, logger: logging.Logger) -> int:
    """
    Stream a JSONL ledger file into DuckDB.

    Each line is a JSON object matching IngestEvent.to_row():
        { event_id, ingested_at, source, batch_id, region, metric,
          fuel_tech, timestamp, value, unit, interval_minutes }

    Uses DuckDB's read_json for fast bulk loading (far quicker than
    Python-level json.loads iteration on large files).
    """
    if not path.exists():
        logger.warning(f"JSONL ledger not found: {path}")
        return 0

    size_mb = path.stat().st_size / 1_048_576
    logger.info(f"  Loading JSONL ledger: {path.name} ({size_mb:.1f} MB)")

    # DuckDB can read JSONL natively with auto-detected schema.
    # We cast to canonical types explicitly for safety.
    con.execute(f"""
        INSERT INTO raw_ledger
        SELECT
            CAST(event_id        AS VARCHAR)   AS event_id,
            CAST(ingested_at     AS TIMESTAMP) AS ingested_at,
            CAST(source          AS VARCHAR)   AS source,
            CAST(batch_id        AS VARCHAR)   AS batch_id,
            CAST(region          AS VARCHAR)   AS region,
            CAST(metric          AS VARCHAR)   AS metric,
            CAST(fuel_tech       AS VARCHAR)   AS fuel_tech,
            CAST(timestamp       AS TIMESTAMP) AS timestamp,
            CAST(value           AS DOUBLE)    AS value,
            CAST(unit            AS VARCHAR)   AS unit,
            CAST(interval_minutes AS INTEGER)  AS interval_minutes
        FROM read_json(
            '{path}',
            auto_detect = true,
            maximum_object_size = 67108864
        )
    """)
    count = con.execute("SELECT COUNT(*) FROM raw_ledger").fetchone()[0]
    logger.info(f"  Loaded {count:,} events from JSONL")
    return count


def _load_parquet(directory: Path, con, logger: logging.Logger) -> int:
    """Load all *.parquet files in directory into raw_ledger."""
    files = sorted(directory.glob("*.parquet"))
    if not files:
        return 0

    logger.info(f"  Loading Parquet ledger: {len(files)} files from {directory.name}/")
    glob_pattern = str(directory / "*.parquet")
    con.execute(f"""
        INSERT INTO raw_ledger
        SELECT
            CAST(event_id         AS VARCHAR)   AS event_id,
            CAST(ingested_at      AS TIMESTAMP) AS ingested_at,
            CAST(source           AS VARCHAR)   AS source,
            CAST(batch_id         AS VARCHAR)   AS batch_id,
            CAST(region           AS VARCHAR)   AS region,
            CAST(metric           AS VARCHAR)   AS metric,
            CAST(fuel_tech        AS VARCHAR)   AS fuel_tech,
            CAST(timestamp        AS TIMESTAMP) AS timestamp,
            CAST(value            AS DOUBLE)    AS value,
            CAST(unit             AS VARCHAR)   AS unit,
            CAST(interval_minutes AS INTEGER)   AS interval_minutes
        FROM read_parquet('{glob_pattern}')
    """)
    count = con.execute("SELECT COUNT(*) FROM raw_ledger").fetchone()[0]
    logger.info(f"  Loaded {count:,} total events (after Parquet)")
    return count


def get_con(ledger_path: Path, logger: logging.Logger):
    """
    Build a DuckDB connection with all ledger data loaded and pre-processed.

    Steps:
      1. Create raw_ledger staging table
      2. Load JSONL and/or Parquet (whichever exist at ledger_path)
      3. Deduplicate → readings table  (mirrors replay_to_regions())
      4. Load fuel taxonomy → fuel_map table
      5. Create power view (enriched with taxonomy join)
    """
    import duckdb

    con = duckdb.connect()

    # ── 1. Staging table ──────────────────────────────────────────────────────
    con.execute("""
        CREATE TABLE raw_ledger (
            event_id         VARCHAR,
            ingested_at      TIMESTAMP,
            source           VARCHAR,
            batch_id         VARCHAR,
            region           VARCHAR,
            metric           VARCHAR,
            fuel_tech        VARCHAR,
            timestamp        TIMESTAMP,
            value            DOUBLE,
            unit             VARCHAR,
            interval_minutes INTEGER
        )
    """)

    # ── 2. Load data ──────────────────────────────────────────────────────────
    loaded = 0
    ledger_path = Path(ledger_path)

    if ledger_path.is_file() and ledger_path.suffix == ".jsonl":
        # Explicit JSONL file path
        loaded += _load_jsonl(ledger_path, con, logger)

    elif ledger_path.is_dir():
        # Directory: try both JSONL and Parquet (merge them)
        jsonl_file = ledger_path / "ledger.jsonl"
        loaded += _load_jsonl(jsonl_file, con, logger)
        loaded += _load_parquet(ledger_path, con, logger)

    else:
        # Path doesn't exist yet — warn but don't crash (produces empty views)
        logger.warning(f"Ledger path not found: {ledger_path} — will produce empty views")

    if loaded == 0:
        logger.warning("No ledger data found — all views will be empty (run backfill first)")

    # ── 3. Deduplicate ────────────────────────────────────────────────────────
    # Mirrors replay_to_regions(): for each (region, metric, fuel_tech, timestamp)
    # keep the event with the latest ingested_at.  This correctly supersedes
    # any revised readings from later ingestions.
    con.execute("""
        CREATE TABLE readings AS
        WITH ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        region,
                        metric,
                        COALESCE(fuel_tech, '__null__'),
                        timestamp
                    ORDER BY ingested_at DESC NULLS LAST
                ) AS rn
            FROM raw_ledger
            WHERE value IS NOT NULL
        )
        SELECT
            event_id, ingested_at, source, batch_id,
            region, metric, fuel_tech, timestamp,
            value, unit, interval_minutes
        FROM ranked
        WHERE rn = 1
    """)

    deduped = con.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    raw = con.execute("SELECT COUNT(*) FROM raw_ledger").fetchone()[0]
    if raw > 0:
        logger.info(f"  Deduplication: {raw:,} raw → {deduped:,} canonical readings "
                    f"({raw - deduped:,} duplicates removed)")

    # Free staging memory
    con.execute("DROP TABLE raw_ledger")

    # ── 4. Fuel taxonomy ──────────────────────────────────────────────────────
    # Build VALUES list dynamically from the Python constant so the SQL and
    # fueltech.py can never drift apart — change one, change both.
    values_sql = ",\n            ".join(
        f"('{raw}', '{cat}', '{label}', {str(ren).lower()}, {str(gen).lower()})"
        for raw, cat, label, ren, gen in FUEL_TAXONOMY
    )
    con.execute(f"""
        CREATE TABLE fuel_map AS
        FROM (VALUES
            {values_sql}
        ) t(raw, category, display_name, is_renewable, counts_as_generation)
    """)

    # ── 5. Enriched power table ───────────────────────────────────────────────
    # Joins fuel taxonomy onto power readings so aggregations don't need a subquery.
    # energy_mwh = value_MW × interval_minutes / 60  (matches Reading.energy_mwh)
    con.execute("""
        CREATE TABLE power AS
        SELECT
            r.region,
            r.timestamp,
            r.value                                       AS mw,
            r.interval_minutes,
            r.value * r.interval_minutes / 60.0           AS energy_mwh,
            COALESCE(fm.category,         'OTHER')        AS category,
            COALESCE(fm.display_name,
                     r.fuel_tech, 'Unknown')              AS fuel_label,
            COALESCE(fm.is_renewable,           false)    AS is_renewable,
            COALESCE(fm.counts_as_generation,   false)    AS counts_as_generation
        FROM readings r
        LEFT JOIN fuel_map fm ON fm.raw = LOWER(TRIM(r.fuel_tech))
        WHERE r.metric = 'power'
          AND r.fuel_tech IS NOT NULL
          AND r.fuel_tech != ''
    """)

    return con


# ── view builders ─────────────────────────────────────────────────────────────
def write_json(path: Path, data, logger: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), default=str)
    size_kb = path.stat().st_size / 1024
    logger.info(f"  Wrote {path.name} ({size_kb:.1f} KB)")


def build_summary(con, views_dir: Path, logger: logging.Logger) -> None:
    """
    Per-region KPIs over the full ledger window → summary.json

    Shape: RegionSummary[]
    {
      region, total_generation_mwh, renewable_generation_mwh, renewable_share_pct,
      total_emissions_tco2e, emissions_intensity, avg_price, peak_price, min_price,
      first_date, last_date, days_covered, by_category_mwh: { SOLAR: mwh, … }
    }
    """
    logger.info("Building summary…")

    rows = con.execute("""
        WITH gen AS (
            SELECT
                region,
                SUM(CASE WHEN counts_as_generation           THEN energy_mwh ELSE 0 END) AS total_gen_mwh,
                SUM(CASE WHEN is_renewable
                          AND counts_as_generation           THEN energy_mwh ELSE 0 END) AS ren_gen_mwh
            FROM power
            GROUP BY region
        ),
        emit AS (
            SELECT region, SUM(value) AS total_emissions_tco2e
            FROM readings
            WHERE metric = 'emissions'
            GROUP BY region
        ),
        price AS (
            SELECT
                region,
                AVG(value) AS avg_price,
                MAX(value) AS peak_price,
                MIN(value) AS min_price
            FROM readings
            WHERE metric = 'price'
            GROUP BY region
        ),
        date_range AS (
            SELECT
                region,
                MIN(timestamp)                           AS first_ts,
                MAX(timestamp)                           AS last_ts,
                COUNT(DISTINCT CAST(timestamp AS DATE))  AS days_covered
            FROM readings
            GROUP BY region
        )
        SELECT
            g.region,
            g.total_gen_mwh,
            g.ren_gen_mwh,
            CASE WHEN g.total_gen_mwh > 0
                 THEN g.ren_gen_mwh / g.total_gen_mwh
                 ELSE 0 END                        AS renewable_share,
            e.total_emissions_tco2e,
            CASE WHEN g.total_gen_mwh > 0
                 THEN e.total_emissions_tco2e / g.total_gen_mwh
                 ELSE 0 END                        AS emissions_intensity,
            p.avg_price,
            p.peak_price,
            p.min_price,
            d.first_ts,
            d.last_ts,
            d.days_covered
        FROM gen g
        LEFT JOIN emit       e USING (region)
        LEFT JOIN price      p USING (region)
        LEFT JOIN date_range d USING (region)
        ORDER BY g.region
    """).fetchdf()

    fuel_rows = con.execute("""
        SELECT
            region,
            category,
            SUM(CASE WHEN counts_as_generation THEN energy_mwh ELSE 0 END) AS mwh
        FROM power
        GROUP BY region, category
        ORDER BY region, mwh DESC
    """).fetchdf()

    # Build by_category_mwh dict per region
    by_cat: dict[str, dict] = {}
    for _, r in fuel_rows.iterrows():
        by_cat.setdefault(str(r["region"]), {})[str(r["category"])] = round(float(r["mwh"]), 1)

    result = []
    for _, r in rows.iterrows():
        reg = str(r["region"])
        result.append({
            "region": reg,
            "total_generation_mwh":     round(float(r["total_gen_mwh"]  or 0), 1),
            "renewable_generation_mwh": round(float(r["ren_gen_mwh"]    or 0), 1),
            "renewable_share_pct":      round(float(r["renewable_share"] or 0) * 100, 2),
            "total_emissions_tco2e":    round(float(r["total_emissions_tco2e"] or 0), 1),
            "emissions_intensity":      round(float(r["emissions_intensity"]   or 0), 4),
            "avg_price":  (round(float(r["avg_price"]),  2) if r["avg_price"]  is not None else None),
            "peak_price": (round(float(r["peak_price"]), 2) if r["peak_price"] is not None else None),
            "min_price":  (round(float(r["min_price"]),  2) if r["min_price"]  is not None else None),
            "first_date": str(r["first_ts"])[:10] if r["first_ts"] is not None else None,
            "last_date":  str(r["last_ts"])[:10]  if r["last_ts"]  is not None else None,
            "days_covered": int(r["days_covered"] or 0),
            "by_category_mwh": by_cat.get(reg, {}),
        })

    write_json(views_dir / "summary.json", result, logger)


def build_timeseries(con, grain: str, views_dir: Path, logger: logging.Logger) -> None:
    """
    Build a time-series view → daily.json | weekly.json | monthly.json | yearly.json

    Shape: GrainView
    {
      grain: "daily",
      periods: ["2010-01-01", …],
      regions: {
        "NSW1": [
          {
            period: "2010-01-01",
            fuel: { SOLAR: 123.4, WIND: 56.7, COAL: 4500.0, … },  ← category-aggregated MWh
            renewable_share_pct: 18.3,
            total_gen_mwh: 5000.0,
            avg_price: 45.23,
            peak_price: 234.5,
            min_price: -10.0,
            avg_demand_mw: 8500.0,
            peak_demand_mw: 12000.0,
            total_emissions_tco2e: 4500.0
          }, …
        ], …
      }
    }

    fuel dict keys are CATEGORY strings (e.g. SOLAR, COAL) — already rolled up
    from individual fuel techs (e.g. solar_utility + solar_rooftop → SOLAR).
    This matches FUEL_META keys in views.ts.
    """
    logger.info(f"Building {grain}…")

    # Period label expressions per grain
    grain_exprs = {
        "daily": {
            "trunc":  "CAST(timestamp AS DATE)",
            "label":  "CAST(CAST(timestamp AS DATE) AS VARCHAR)",
        },
        "weekly": {
            "trunc":  "DATE_TRUNC('week', timestamp)",
            # ISO week label: "2024-W01"
            "label":  "STRFTIME(DATE_TRUNC('week', timestamp), '%Y-W%V')",
        },
        "monthly": {
            "trunc":  "DATE_TRUNC('month', timestamp)",
            "label":  "STRFTIME(DATE_TRUNC('month', timestamp), '%Y-%m')",
        },
        "yearly": {
            # Financial year: subtract 6 months so Jul becomes the "start" of the FY year.
            # FY2024 = Jul 2023 – Jun 2024  →  label = 'FY2024'
            "trunc":  "DATE_TRUNC('year', timestamp - INTERVAL '6 months')",
            "label":  "('FY' || CAST(YEAR(timestamp - INTERVAL '6 months') + 1 AS VARCHAR))",
        },
    }
    if grain not in grain_exprs:
        raise ValueError(f"Unknown grain: {grain!r}")

    expr = grain_exprs[grain]
    label_sql  = expr["label"]

    # ── Generation by fuel category per (period, region) ─────────────────────
    # Note: we aggregate by CATEGORY (not raw fuel_tech) so that e.g.
    # solar_utility + solar_rooftop both contribute to the SOLAR bucket.
    gen_df = con.execute(f"""
        SELECT
            {label_sql}                                              AS period,
            region,
            category,
            ROUND(SUM(CASE WHEN counts_as_generation
                           THEN energy_mwh ELSE 0 END), 3)          AS gen_mwh,
            -- keep is_renewable so we can double-check ren share
            MAX(CAST(is_renewable AS INTEGER))                       AS is_renewable_flag,
            MAX(CAST(counts_as_generation AS INTEGER))               AS gen_flag
        FROM power
        GROUP BY {label_sql}, region, category
        ORDER BY period, region, gen_mwh DESC
    """).fetchdf()

    # ── Price, demand, emissions per (period, region) ─────────────────────────
    meta_df = con.execute(f"""
        SELECT
            {label_sql}                                        AS period,
            region,
            ROUND(AVG(CASE WHEN metric='price'
                           THEN value END), 2)                 AS avg_price,
            ROUND(MAX(CASE WHEN metric='price'
                           THEN value END), 2)                 AS peak_price,
            ROUND(MIN(CASE WHEN metric='price'
                           THEN value END), 2)                 AS min_price,
            ROUND(AVG(CASE WHEN metric='demand'
                           THEN value END), 1)                 AS avg_demand_mw,
            ROUND(MAX(CASE WHEN metric='demand'
                           THEN value END), 1)                 AS peak_demand_mw,
            ROUND(SUM(CASE WHEN metric='emissions'
                           THEN value END), 1)                 AS total_emissions_tco2e
        FROM readings
        GROUP BY {label_sql}, region
        ORDER BY period, region
    """).fetchdf()

    # ── Renewable share per (period, region) ──────────────────────────────────
    ren_df = con.execute(f"""
        SELECT
            {label_sql}                                                AS period,
            region,
            ROUND(
                SUM(CASE WHEN is_renewable AND counts_as_generation
                         THEN energy_mwh ELSE 0 END)
                / NULLIF(
                    SUM(CASE WHEN counts_as_generation
                             THEN energy_mwh ELSE 0 END), 0
                  ) * 100, 2
            )                                                          AS renewable_share_pct,
            ROUND(SUM(CASE WHEN counts_as_generation
                           THEN energy_mwh ELSE 0 END), 3)             AS total_gen_mwh
        FROM power
        GROUP BY {label_sql}, region
        ORDER BY period, region
    """).fetchdf()

    # ── Assemble in Python ────────────────────────────────────────────────────
    # fuel_data[region][period] = { CATEGORY: mwh, … }
    fuel_data: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    periods_ordered: list[str] = []
    seen_periods: set[str] = set()

    for _, r in gen_df.iterrows():
        period = str(r["period"])
        region = str(r["region"])
        cat    = str(r["category"])
        mwh    = float(r["gen_mwh"])
        if period not in seen_periods:
            seen_periods.add(period)
            periods_ordered.append(period)
        fuel_data[region][period][cat] = mwh

    # meta_data[region][period] = { avg_price, peak_price, … }
    meta_data: dict[str, dict[str, dict]] = defaultdict(dict)
    for _, r in meta_df.iterrows():
        period = str(r["period"])
        region = str(r["region"])
        meta_data[region][period] = {
            "avg_price":             (float(r["avg_price"])             if r["avg_price"]             is not None else None),
            "peak_price":            (float(r["peak_price"])            if r["peak_price"]            is not None else None),
            "min_price":             (float(r["min_price"])             if r["min_price"]             is not None else None),
            "avg_demand_mw":         (float(r["avg_demand_mw"])         if r["avg_demand_mw"]         is not None else None),
            "peak_demand_mw":        (float(r["peak_demand_mw"])        if r["peak_demand_mw"]        is not None else None),
            "total_emissions_tco2e": (float(r["total_emissions_tco2e"]) if r["total_emissions_tco2e"] is not None else None),
        }

    # ren_data[region][period] = { renewable_share_pct, total_gen_mwh }
    ren_data: dict[str, dict[str, dict]] = defaultdict(dict)
    for _, r in ren_df.iterrows():
        period = str(r["period"])
        region = str(r["region"])
        ren_data[region][period] = {
            "renewable_share_pct": (float(r["renewable_share_pct"]) if r["renewable_share_pct"] is not None else 0.0),
            "total_gen_mwh":       (float(r["total_gen_mwh"])       if r["total_gen_mwh"]       is not None else 0.0),
        }

    # Union of all regions from all three data frames
    all_regions = sorted(
        set(fuel_data.keys()) | set(meta_data.keys()) | set(ren_data.keys())
    )
    periods_sorted = sorted(seen_periods)

    result: dict = {
        "grain":   grain,
        "periods": periods_sorted,
        "regions": {},
    }

    for region in all_regions:
        period_rows = []
        for period in periods_sorted:
            fuel = fuel_data[region].get(period, {})
            meta = meta_data[region].get(period, {})
            ren  = ren_data[region].get(period, {})

            period_rows.append({
                "period":                  period,
                "fuel":                    fuel,           # { SOLAR: mwh, … }
                "renewable_share_pct":     ren.get("renewable_share_pct", 0.0),
                "total_gen_mwh":           ren.get("total_gen_mwh", 0.0),
                # All meta fields — may be None if that metric doesn't exist for this period
                "avg_price":               meta.get("avg_price"),
                "peak_price":              meta.get("peak_price"),
                "min_price":              meta.get("min_price"),
                "avg_demand_mw":           meta.get("avg_demand_mw"),
                "peak_demand_mw":          meta.get("peak_demand_mw"),
                "total_emissions_tco2e":   meta.get("total_emissions_tco2e"),
            })

        result["regions"][region] = period_rows

    write_json(views_dir / f"{grain}.json", result, logger)

    # Log a quick stat
    total_periods = len(periods_sorted)
    logger.info(f"  {grain}: {total_periods} periods × {len(all_regions)} regions")


def build_raw_recent(con, views_dir: Path, logger: logging.Logger,
                     days: int = 8, limit: int = 50_000) -> None:
    """
    Last N days of raw readings (all metrics) for the Data table → raw_recent.json

    Shape: { count: int, rows: RawRow[] }
    RawRow: { region, metric, fuel_tech, timestamp, value, unit, interval_minutes }

    Ordered newest-first. Capped at `limit` rows so the JSON stays manageable
    even on a multi-year ledger.
    """
    logger.info(f"Building raw_recent (last {days} days, max {limit:,} rows)…")

    rows = con.execute(f"""
        SELECT
            region,
            metric,
            fuel_tech,
            CAST(timestamp AS VARCHAR)  AS timestamp,
            ROUND(value, 4)             AS value,
            unit,
            interval_minutes
        FROM readings
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
        ORDER BY timestamp DESC, region, metric
        LIMIT {limit}
    """).fetchdf()

    records = []
    for _, r in rows.iterrows():
        records.append({
            "region":           str(r["region"]),
            "metric":           str(r["metric"]),
            "fuel_tech":        (str(r["fuel_tech"]) if r["fuel_tech"] is not None else None),
            "timestamp":        str(r["timestamp"]),
            "value":            float(r["value"]),
            "unit":             str(r["unit"]),
            "interval_minutes": int(r["interval_minutes"]),
        })

    write_json(views_dir / "raw_recent.json", {"count": len(records), "rows": records}, logger)
    logger.info(f"  raw_recent: {len(records):,} rows")


def build_last_updated(con, views_dir: Path, logger: logging.Logger,
                       elapsed: float) -> None:
    """Write a manifest so the frontend can show data freshness."""
    row = con.execute("""
        SELECT
            COUNT(*)               AS total_events,
            COUNT(DISTINCT region) AS regions,
            MIN(timestamp)         AS first_ts,
            MAX(timestamp)         AS last_ts
        FROM readings
    """).fetchone()

    data = {
        "materialized_at":  datetime.now(UTC).isoformat(),
        "elapsed_seconds":  round(elapsed, 2),
        "total_events":     int(row[0]),
        "regions":          int(row[1]),
        "first_date":  (str(row[2])[:10] if row[2] is not None else None),
        "last_date":   (str(row[3])[:10] if row[3] is not None else None),
    }
    write_json(views_dir / "last_updated.json", data, logger)
    logger.info(
        f"  Ledger covers {data['first_date']} → {data['last_date']} "
        f"({data['total_events']:,} events, {data['regions']} regions)"
    )


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="GridWatch AU — DuckDB materializer (JSONL + Parquet ledger → JSON views)"
    )
    parser.add_argument(
        "--ledger",
        default=str(DEFAULT_LEDGER),
        help=(
            "Path to ledger. "
            "Directory → auto-detect ledger.jsonl + *.parquet. "
            "*.jsonl file → JSONL only. "
            f"Default: {DEFAULT_LEDGER}"
        ),
    )
    parser.add_argument(
        "--views-dir",
        default=str(VIEWS_DIR),
        help=f"Output directory for JSON views. Default: {VIEWS_DIR}",
    )
    parser.add_argument(
        "--views",
        nargs="+",
        default=ALL_VIEWS,
        choices=ALL_VIEWS,
        metavar="VIEW",
        help=f"Views to build (default: all). Choices: {', '.join(ALL_VIEWS)}",
    )
    parser.add_argument(
        "--raw-recent-days",
        type=int,
        default=8,
        help="How many days of raw readings to include in raw_recent.json (default: 8)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("━━━ GridWatch AU — Materialize ━━━")

    # Validate dependencies
    try:
        import duckdb  # noqa: F401
    except ImportError:
        logger.error("duckdb not installed. Run:  pip install duckdb")
        sys.exit(1)

    ledger_path = Path(args.ledger)
    views_dir   = Path(args.views_dir)
    views_to_build = args.views

    logger.info(f"Ledger : {ledger_path}")
    logger.info(f"Views  : {views_dir}")
    logger.info(f"Tasks  : {', '.join(views_to_build)}")

    t0 = time.perf_counter()

    # ── Build DuckDB in-memory workspace ─────────────────────────────────────
    con = get_con(ledger_path, logger)
    deduped_count = con.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    logger.info(f"Canonical readings available: {deduped_count:,}")

    # ── Build requested views ─────────────────────────────────────────────────
    if "summary"    in views_to_build: build_summary(con, views_dir, logger)
    if "daily"      in views_to_build: build_timeseries(con, "daily",   views_dir, logger)
    if "weekly"     in views_to_build: build_timeseries(con, "weekly",  views_dir, logger)
    if "monthly"    in views_to_build: build_timeseries(con, "monthly", views_dir, logger)
    if "yearly"     in views_to_build: build_timeseries(con, "yearly",  views_dir, logger)
    if "raw_recent" in views_to_build:
        build_raw_recent(con, views_dir, logger, days=args.raw_recent_days)

    elapsed = time.perf_counter() - t0
    build_last_updated(con, views_dir, logger, elapsed)

    logger.info(f"\n✓ Done in {elapsed:.2f}s — views written to {views_dir}/")


if __name__ == "__main__":
    main()
