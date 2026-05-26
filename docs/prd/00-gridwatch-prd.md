# GridWatch AU — Product Requirements (v0.1)

## Problem
Australia's progress on **SDG 7 (Affordable & Clean Energy)** and **SDG 13 (Climate
Action)** is visible in real grid data, but that data is spread across raw API series
that are hard to organise, search, or summarise. There is no small, inspectable tool
that lets a student/analyst pull it in, maintain a working dataset, and read the story
(fuel mix, renewable share, emissions intensity) per region.

## Goal
A management system that **organises, searches, and maintains** Australian NEM
electricity readings, pulls **live** data from a free source, and **visualises**
insights — built cleanly with OOP and robust error handling.

## Users
- **Student / educator** — explores the energy transition with real data.
- **Citizen analyst** — compares regions, tracks renewable share over a week.

## In scope
- Manage **regions** (NSW1, QLD1, VIC1, SA1, TAS1) and their **readings** (power,
  emissions, price, demand) over a rolling 7-day window.
- CRUD, search/filter, per-region and cross-region summaries.
- Live fetch from OpenElectricity; save/load JSON and CSV.
- Charts: fuel mix, renewable share, emissions, price.

## Out of scope (this version)
- WA (SWIS) / NT — not in the NEM (ADR-005).
- Forecasting / market bidding / settlement.
- Multi-user accounts, a web UI, or a hosted service.

## Functional requirements
1. **Import** the live 7-day feed for a region and map it into typed readings.
2. **Add / edit / delete** a reading by hand; **clear** a region.
3. **Search** by region, fuel category, renewable-only, metric, value threshold, time
   window — composably.
4. **Summarise**: total generation (MWh), renewable share (%), total emissions (tCO₂e),
   emissions intensity (tCO₂e/MWh), average & peak price (AUD/MWh).
5. **Compare** regions on those metrics.
6. **Persist**: save/load a dataset (JSON canonical, CSV export).
7. **Visualise**: produce the four chart types to screen and to `outputs/`.

## Non-functional requirements
- **OOP**: abstraction (ABCs), inheritance (`Reading`/exception/adapter trees),
  polymorphism, encapsulation (see ADR-003, ADR-001).
- **Robustness**: a typed exception hierarchy; the CLI never crashes on bad input,
  network failure, or a corrupt file — it reports and continues.
- **Real data & real tests**: live source for runtime; an offline captured fixture for
  tests; persistence tested against real files.

## Success criteria
- `pytest -q` green (full suite, offline); `ruff` clean; CI green on PRs.
- A live end-to-end run imports a real region, summarises it, and writes a chart.
