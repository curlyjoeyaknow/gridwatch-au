# GridWatch AU

A management system for **Australian electricity generation & emissions**, built to
surface progress on **UN SDG 7 (Affordable & Clean Energy)** and **SDG 13 (Climate
Action)**. It organises, searches, and maintains time-series readings for each
National Electricity Market (NEM) region, pulls **live data** from the free
[OpenElectricity](https://openelectricity.org.au) feed, and visualises the fuel mix,
renewable share, and emissions.

> **Scope:** the **NEM** — `NSW1`, `QLD1`, `VIC1`, `SA1`, `TAS1`. Western Australia
> (SWIS) and the NT are not part of the NEM and are out of scope by design (see
> [ADR-005](docs/architecture/decisions/ADR-005-scope-nem-only.md)).

## What it does
- **Maintain (CRUD):** import or hand-add regions and readings; edit/delete a reading.
- **Organise:** readings grouped by region → metric → fuel tech, each fuel tech
  classified into a category with a renewable flag.
- **Search/filter:** by region, fuel category, renewable-only, metric, value
  threshold, and time window.
- **Summarise:** total generation, **renewable share %**, total emissions,
  **emissions intensity (tCO₂e/MWh)**, average/peak price — per region and compared.
- **Live API:** fetch the 7-day feed for any NEM region (free, no API key).
- **Bulk fetch + ledger:** download all regions into an append-only **JSONL/Parquet
  event ledger** (immutable history); current state is **derived by replay** (dedup,
  latest-ingest-wins).
- **Browse:** a queryable **data table** (filter by region/metric/fuel/category/
  renewable/value/time, sort, page) with CSV export of the filtered set.
- **Persist:** JSON, CSV, or **SQLite** snapshots.
- **Visualise (9 chart types):** fuel-mix pie, renewable-share & emissions-intensity
  bars, price trend, **stacked generation-over-time**, renewable-share-over-time,
  demand-vs-generation, emissions-over-time, and a price duration curve (matplotlib).

## How it's built
Spec-driven delivery, ports & adapters, real TDD — see [`CLAUDE.md`](CLAUDE.md) for the
method and [`docs/`](docs/) for the PRD, architecture, ADRs, and build plan.

## Quick start
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q                     # full suite (offline; uses a captured API fixture)
pytest -q -m "not slow"       # fast suite (what pre-commit runs)
ruff check src tests          # lint
python -m gridwatch.cli       # run the menu-driven app
```

## Example (live, last 7 days)
```
Region    Renewable %   Intensity     Gen MWh
TAS1            99.8%       0.020      204159     # ~all hydro
SA1             68.7%       0.297      239297     # wind + solar
QLD1            33.6%       0.593     1213865
NSW1            32.8%       0.674     1345371
VIC1            28.5%       0.916     1105084     # brown coal
```
Charts (fuel mix, renewable share, emissions intensity, price trend) are written to
`outputs/` as PNGs.

## Data source
OpenElectricity v4 static feed (free, no key, no account):
`https://data.openelectricity.org.au/v4/stats/au/NEM/{REGION}/power/7d.json`
(requires a `User-Agent` header — handled in the adapter). See
[ADR-002](docs/architecture/decisions/ADR-002-data-source-openelectricity.md).
