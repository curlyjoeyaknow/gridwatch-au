# ADR-001 — Ports & Adapters at every external boundary

**Status:** Accepted · 2026-05-26
**Context tags:** architecture, boundaries, testability, the spine
**Related:** ADR-002 (data source), ADR-003 (reading spine), ADR-004 (persistence)

## Context

GridWatch depends on two volatile externals: a third-party HTTP API (OpenElectricity,
which has already rebranded once and changed its API shape) and a persistence medium
(files now, possibly a DB later). If the core spoke `requests` and raw vendor JSON
directly, every one of those changes would ripple through the whole codebase, and the
core would be untestable without network and disk.

## Decision

1. **The core depends on ports, never on a vendor SDK.** Two abstract base classes in
   `src/gridwatch/ports/` define the boundary: `DataSource` (where readings come from)
   and `Repository` (where datasets are saved/loaded).
2. **Externals live behind adapters** in `src/gridwatch/adapters/`:
   `OpenElectricityClient`, `FakeDataSource`, `JsonRepository`, `CsvRepository`.
3. **Adapters map the vendor shape to our contract.** The OpenElectricity adapter
   parses vendor JSON and returns **our** `Reading` objects (ADR-003). A raw vendor
   dict must never cross the port — a leaky adapter is a bug.
4. **The only fake is at a port.** `FakeDataSource` lets the whole core be tested with
   no network; persistence is tested against **real temp files**, not mocks.

## Consequences

- (+) The core is unit-testable offline; the API client is the only networked piece.
- (+) Swapping data source (e.g. AEMO) or storage (e.g. SQLite) is an adapter change,
  not a core rewrite.
- (+) Clear demonstration of abstraction/polymorphism for the OOP brief.
- (−) A little extra indirection (two ABCs) versus calling `requests` inline.

## Alternatives rejected

- **Call `requests`/`json` directly in the core** — fastest to write, but couples the
  core to a vendor that has already proven unstable, and forces network into tests.
- **A single "service" god-class** — collapses the boundaries this ADR exists to keep,
  and erodes testability as features pile on.
