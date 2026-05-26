# ADR-008 — Web dashboard as a driving adapter

**Status:** Accepted · 2026-05-26
**Context tags:** driving adapter, web UI, reuse
**Related:** ADR-001 (ports & adapters), ADR-007 (ingest ledger)

## Context

The CLI is one way to drive the system; a browser view of the same data was also
wanted. The architecture already isolates all behaviour behind the `EnergyGridManager`
facade, the query engine, and the chart renderers, so a web UI should add **no new
domain logic** — only a second *driving adapter* alongside the CLI (ADR-001).

## Decision

1. **A Flask app under `src/gridwatch/web/`**, server-rendered (Jinja templates), exposed
   via a `create_app(...)` factory so it is testable with Flask's test client and a
   `FakeDataSource`-backed manager.
2. **It reuses the core unchanged:** `manager.compare()/summarise()/query()` and
   `viz.charts.*`. Charts are rendered on demand to a temp dir and served as PNG
   responses; no chart logic is duplicated.
3. **Reads from the ledger; refreshes live.** On startup it loads state from the
   configured `EventLedger` (ADR-007); `POST /refresh` runs a `bulk_fetch` + replay. The
   ledger path is taken from the `GRIDWATCH_LEDGER` env var when not passed explicitly.
4. **Routes:** `/` dashboard (region comparison + cross-region charts), `/region/<code>`
   (per-region summary + charts), `/table` (queryable data table: filter/sort/paginate),
   `/table.csv` (export the filtered set), `/charts/<kind>[/<region>].png`, `POST /refresh`.
5. **Deploy-ready:** a `Dockerfile` runs the factory under `gunicorn`; nothing about the
   core changes between local (`python -m gridwatch.web`) and a container.

## Consequences

- (+) A browser UI with zero new business logic; CLI and web stay in sync because both
  call the same facade.
- (+) Testable without a running server (Flask test client + fakes).
- (−) Adds a `flask` dependency and (for serving) `gunicorn` in the image.
- (−) On-demand chart rendering writes temp PNGs per request — fine at this scale; a
  cache could be added later.

## Alternatives rejected

- **A single-page JS frontend + JSON API** — more moving parts than a server-rendered
  dashboard needs for this scope; the `/table.csv` and JSON-ready query result leave the
  door open later.
- **Putting web logic in the core** — would violate ADR-001; the web layer stays a thin
  driving adapter.
