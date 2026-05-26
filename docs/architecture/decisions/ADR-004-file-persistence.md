# ADR-004 — File persistence: JSON canonical, CSV export

**Status:** Accepted · 2026-05-26
**Context tags:** persistence, storage, robustness
**Related:** ADR-001 (ports & adapters), ADR-003 (reading spine)

## Context

The system must save and reload managed datasets. The stack was chosen as
"Python + JSON/CSV files" — no database server. Persistence still sits behind the
`Repository` port (ADR-001) so a DB could be added later as another adapter without
touching the core.

## Decision

1. **JSON is the canonical save format** (`JsonRepository`): a full, loss-less,
   round-trippable representation of regions and their typed readings, including the
   reading subclass so it rehydrates to the right `Reading` type (ADR-003).
2. **CSV is an export/interop format** (`CsvRepository`): one flat row per reading
   (`region, metric, fuel_tech, timestamp, value, unit`) for spreadsheets/analysis. CSV
   load is supported but is the lossy/flat view; JSON is authoritative.
3. **Both implement the same `Repository` port** and are covered by **real-file**
   round-trip tests (write to a temp dir, read back, assert equality) — never mocked.
4. **I/O failures raise `PersistenceError`** (corrupt file, missing path, permission)
   so the CLI can report cleanly instead of crashing.

## Consequences

- (+) Zero infra; saved files are human-inspectable (good for a teaching project).
- (+) JSON preserves types; CSV gives instant spreadsheet/BI interop.
- (−) No concurrent-writer safety or indexed queries — acceptable at this scale; a
  future `SqliteRepository` adapter would address it without a core change.

## Alternatives rejected

- **SQLite** — stronger queries, but adds schema/migration overhead the brief's stack
  choice deliberately avoids; reserved as a future adapter.
- **Pickle** — round-trips Python objects trivially but is opaque, version-fragile, and
  unsafe to load from untrusted sources.
