# ADR-006 — SQLite repository adapter

**Status:** Accepted · 2026-05-26
**Context tags:** persistence, adapters, query
**Related:** ADR-001 (ports & adapters), ADR-004 (file persistence)

## Context

ADR-004 chose JSON/CSV files and explicitly reserved a `SqliteRepository` as a future
adapter for "stronger queries and indexed lookups". Datasets are now large enough
(a single region's 7-day window is tens of thousands of readings) that a flat file
reload is clumsy when a user wants to filter/sort. SQLite gives indexed, SQL-backed
storage with zero server and a single-file database — and it slots behind the existing
`Repository` port, so the core does not change.

## Decision

1. **Add `adapters/sqlite_repo.py` — `SqliteRepository(Repository)`**, a third
   interchangeable implementation of the same port (ADR-001). The manager and CLI treat
   it exactly like the JSON/CSV repositories.
2. **Schema:** a `regions(code, name)` table and a `readings(region, metric, fuel_tech,
   timestamp, value, unit, interval_minutes)` table, with an index on
   `(region, metric, timestamp)` for the query/browse feature.
3. **`save` is a snapshot replace** within a single transaction (mirrors JSON/CSV "save
   the current state"): tables are (re)created and rewritten atomically. The append-only
   *history* is the ledger's job (ADR-007), not the repository's.
4. **Rehydration reuses `serde.reading_from_row`** so the SQLite path produces the same
   typed `Reading` subclasses as the other repositories.
5. **All `sqlite3` / OS errors are wrapped in `PersistenceError`** so the CLI reports a
   corrupt or unreadable database cleanly.

## Consequences

- (+) Indexed, SQL-queryable local store; a natural backing for the data-table browse.
- (+) No new heavy dependency (`sqlite3` is in the stdlib).
- (−) `save` rewrites the whole snapshot; fine at this scale, and incremental history is
  handled by the ledger (ADR-007), keeping the two concerns separate.

## Alternatives rejected

- **Make SQLite the only store** — would drop the human-inspectable JSON/CSV that ADR-004
  values; instead it joins them as a peer adapter.
- **An ORM (SQLAlchemy)** — unnecessary weight for two tables; raw `sqlite3` is clearer
  and dependency-free.
