# ADR-007 — Append-only ingest event ledger (event-sourced downloads)

**Status:** Accepted · 2026-05-26
**Context tags:** the spine, event sourcing, ingestion, lineage, storage
**Related:** ADR-001 (ports & adapters), ADR-003 (reading spine), ADR-004/006 (repositories)

## Context

The OpenElectricity feed is a **rolling 7-day window** that is revised over time (recent
intervals change as data firms up). If each download overwrote the previous one, we would
lose history and could never audit what was observed when. The user also wants the data to
live **locally** after a bulk fetch, and to query *everything ever downloaded*.

This is exactly the shape an event log solves, following the event-sourcing principle:
an **append-only log is the source of truth; state is derived**. The repositories
(ADR-004/006) persist a *snapshot* of current state; they are not a history. We need a
separate, immutable record of ingestion.

## Decision

1. **Downloads append to an immutable ledger.** A bulk fetch turns every fetched reading
   into an `IngestEvent` and **appends** it; nothing is ever overwritten or deleted.
2. **`IngestEvent` carries an envelope + the reading payload.** Envelope: `event_id`,
   `ingested_at` (when we fetched), `source`, `batch_id` (shared across one bulk fetch).
   Payload: `region, metric, fuel_tech, timestamp, value, unit, interval_minutes`. The
   grain is **one event per observed reading** — the natural fact.
3. **A port with two adapters (ADR-001).** `ports/ledger.py` `EventLedger` (`append`,
   `read_all`); `adapters/jsonl_ledger.py` (append-only JSON Lines — simple, human-
   readable) and `adapters/parquet_ledger.py` (append = a new immutable Parquet file per
   batch in a directory — columnar, compact, the recommended store for volume).
4. **State is derived by replay, not stored as truth.** `domain/replay.py`
   `replay_to_regions()` folds the ledger into `Region`s, **deduplicating by
   `(region, metric, fuel_tech, timestamp)` and keeping the latest `ingested_at`** — so a
   revised observation supersedes the earlier one, deterministically.
5. **Ledger ≠ repository.** The ledger is the append-only history of *what was downloaded*;
   the JSON/CSV/SQLite repositories store a *snapshot* of derived state. Both exist; they
   are different concerns.

## Consequences

- (+) Full local history; revisions are captured, not lost; replay is reproducible.
- (+) Auditable lineage (`batch_id`, `ingested_at`, `source`) per event.
- (+) The query/browse feature (next track) reads a single growing local store.
- (−) Volume: one event per reading is large (a 5-region bulk fetch ≈ 200k events).
  Parquet compresses it well; JSONL is offered for small/inspectable cases with a caveat.
- (−) Adds a `pyarrow` dependency for the Parquet adapter.

## Alternatives rejected

- **Overwrite on each download** — simplest, but loses history and the revision record the
  whole feature exists to keep.
- **One event per fetch-batch (coarse grain)** — fewer rows, but each is a giant blob that
  is awkward to query/replay per reading; the per-reading grain is the queryable one.
- **Make the SQLite DB the append log** — conflates the snapshot store with the history;
  ADR keeps them separate so each stays simple.
