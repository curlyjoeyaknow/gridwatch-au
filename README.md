# GridWatch AU

A management system for **Australian electricity generation & emissions**, built to
surface progress on **UN SDG 7 (Affordable & Clean Energy)** and **SDG 13 (Climate
Action)**. It organises, searches, and maintains time-series readings for each
National Electricity Market (NEM) region, pulls **live data** from the free
[OpenElectricity](https://openelectricity.org.au) feed, and visualises the fuel mix,
renewable share, and emissions.

> **Scope:** the **NEM** — `NSW1`, `QLD1`, `VIC1`, `SA1`, `TAS1`. Western Australia
> (SWIS) and the NT are not part of the NEM and are out of scope by design.

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
Ports & adapters (hexagonal) around a pure domain core, with a test suite that runs
offline — see [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md).

## Quick start
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q                     # full suite (offline; uses a captured API fixture)
pytest -q -m "not slow"       # fast suite (what pre-commit runs)
ruff check src tests          # lint
python -m gridwatch.cli       # run the menu-driven CLI
python -m gridwatch.web       # run the web dashboard → http://127.0.0.1:8000
```

## Web dashboard
A browser UI (Flask) over the same data: a dashboard (region comparison + cross-region
charts), per-region pages (summary + all chart types), and a **queryable data table**
(filter/sort/paginate + CSV export). It reads from the local append-only ledger; the
**Refresh** button bulk-fetches live. Point it at a ledger with `GRIDWATCH_LEDGER`:
```bash
GRIDWATCH_LEDGER=data/ledger.jsonl python -m gridwatch.web
```
**Deploy (Docker + gunicorn):**
```bash
docker build -t gridwatch-au .
docker run -p 8000:8000 -v "$PWD/data:/data" gridwatch-au
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
(requires a `User-Agent` header — handled in the adapter).
