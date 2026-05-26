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
- **Persist:** save/load datasets as **JSON** (canonical) or **CSV** (export).
- **Visualise:** fuel-mix, renewable-share, emissions, and price charts (matplotlib).

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

## Data source
OpenElectricity v4 static feed (free, no key, no account):
`https://data.openelectricity.org.au/v4/stats/au/NEM/{REGION}/power/7d.json`
(requires a `User-Agent` header — handled in the adapter). See
[ADR-002](docs/architecture/decisions/ADR-002-data-source-openelectricity.md).
