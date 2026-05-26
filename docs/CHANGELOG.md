# Changelog — GridWatch AU

All notable changes are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Append-only ingest ledger + bulk fetch (PR #6), on branch `track-7-ingest-ledger`.

### Added
- **`IngestEvent` (ADR-007)** — `contracts/ingest.py`: envelope (`event_id`,
  `ingested_at`, `source`, `batch_id`) + reading payload; `from_reading`/`to_reading`/
  row round-trip.
- **`EventLedger` port** — `ports/ledger.py` (`append`/`read_all`), with
  `adapters/jsonl_ledger.py` (append-only JSON Lines) and `adapters/parquet_ledger.py`
  (append = new immutable Parquet file per batch; `pyarrow`).
- **Replay projection** — `domain/replay.py`: folds events → Regions, deduping by
  `(region, metric, fuel_tech, timestamp)` keeping the latest `ingested_at`.
- **Manager** — `bulk_fetch(ledger, …)` appends every reading as an event;
  `load_from_ledger()` derives state by replay. Data sources carry a `name` for lineage.
- **CLI** — menu options 11 (bulk fetch → ledger) and 12 (replay a ledger).
- **Refactor** — `reading_from_row` moved into `contracts/readings.py` (spine owns its
  rehydration; raises `ValidationError`); `adapters/serde.py` re-exports it.
- **Tests** — IngestEvent round-trip, ledger append/read for both adapters, replay
  dedup, bulk-fetch/load-from-ledger flows (full suite 125).

### Changed
- Added `pyarrow` runtime dependency (Parquet ledger).

SQLite repository adapter (PR #5).

### Added
- **`SqliteRepository` (ADR-006)** — `adapters/sqlite_repo.py`: a third interchangeable
  `Repository` over a single-file SQLite database (`regions` + indexed `readings`
  tables). `save` is a transactional snapshot replace; rehydration reuses
  `serde.reading_from_row`; `sqlite3`/OS errors wrapped in `PersistenceError`. Wired into
  the CLI save/load formats (`json`/`csv`/`sqlite`). Verified live (TAS1 22k readings
  round-trip).
- **Tests** — real on-disk round-trip incl. subtype preservation, snapshot-replace,
  corrupt-DB and missing-DB error paths (full suite 107).

Tracks 4 + 5 — visualisations + CLI (PR #4).

### Added
- **Visualisations (Track 4)** — `viz/charts.py` (headless Agg backend): fuel-mix pie,
  renewable-share bar, emissions-intensity bar, price-trend line; each raises
  `ValidationError` on empty input and writes a PNG.
- **CLI (Track 5)** — `cli.py`: menu-driven `GridWatchCLI` driving adapter wiring the
  real `OpenElectricityClient`, repositories, and charts; every action catches
  `GridWatchError` and reports it (never crashes). `gridwatch` console entry point.
- **Tests** — chart files written + empty-input guards; CLI action outputs, error
  paths, and a scripted `run()` loop (full suite 103, offline).
- **Live end-to-end** — fetched all five NEM regions and rendered charts: TAS1 99.8%
  renewable, SA1 68.7%, VIC1 28.5% (highest intensity, brown coal).

Tracks 2 + 3 — application facade + adapters (PR #3).

### Added
- **OpenElectricity adapter (ADR-002)** — `adapters/openelectricity.py`:
  `OpenElectricityClient` (real `DataSource`; `User-Agent`, timeout, errors wrapped in
  `DataSourceError`) and a **pure** `map_payload()` that reconstructs timestamps from
  `start + interval × index` and maps each vendor series to a typed `Reading` — vendor
  shape stops at the adapter. Verified live: SA1 ≈ 46k readings, 68.8% renewable.
- **FakeDataSource** — `adapters/fake_source.py`: the only fake, at the port.
- **Persistence (ADR-004)** — `adapters/json_repo.py` (canonical, loss-less),
  `adapters/csv_repo.py` (flat export), shared `adapters/serde.py` rehydration;
  I/O/parse failures raise `PersistenceError`.
- **EnergyGridManager** — `application/manager.py`: region/reading CRUD, live
  `import_region()`, composable `search()`, `summarise()`/`compare()`, `save()`/`load()`
  via the ports.
- **Tests** — adapter mapping against the captured fixture, HTTP behaviour via a fake
  session, real-file round-trips, and manager flows with `FakeDataSource` (full suite 91).

Tracks 0 + 1 — contracts spine + domain (PR #2).

### Added
- **Exception hierarchy** — `exceptions.py`: `GridWatchError` base with
  `DataSourceError`, `ValidationError`, `RegionNotFoundError`, `PersistenceError`.
- **Fuel-tech taxonomy (ADR-003)** — `contracts/fueltech.py`: `FuelCategory` enum,
  `FuelTech` value object, `classify()`; renewable + generation-counting policy
  (storage/interconnect/curtailment excluded; unknown → `OTHER`, never crashes).
- **Reading hierarchy (ADR-003)** — `contracts/readings.py`: abstract `Reading` +
  `PowerReading`/`EmissionReading`/`PriceReading`/`DemandReading` with polymorphic
  `metric`/`unit`/`label()`/`to_row()` and `energy_mwh` interval integration; frozen,
  validated.
- **RegionSummary** — `contracts/summary.py`: computed-insight value object + `as_dict()`.
- **Region scope (ADR-005)** — `contracts/regions.py`: NEM region codes, names,
  `validate_region()` (unknown region rejected).
- **Ports (ADR-001)** — `ports/datasource.py` (`DataSource`) and
  `ports/repository.py` (`Repository`) ABCs.
- **Domain** — `domain/region.py` (`Region` aggregate: encapsulated readings,
  read-only view, `add`/`remove_where`/`clear`, composable `filter()`) and
  `domain/analytics.py` (pure folds: generation, renewable share, emissions intensity,
  price stats, `summarise()`).
- **Tests** — 56 new tests across exceptions, fueltech, readings, ports, region,
  analytics (full suite 63, offline).

Repo scaffolding & process machinery (PR #1).

### Added (PR #1)
- **Project skeleton** — `pyproject.toml` (requests, matplotlib; dev: pytest, ruff,
  pre-commit), `src/gridwatch/` package tree (contracts · ports · domain · adapters ·
  application · viz · cli), `README.md`, `CLAUDE.md` (project memory / method).
- **Spec layer** — PRD (`docs/prd/`), system architecture
  (`docs/architecture/system-architecture.md`), and ADR-001..005 (ports & adapters,
  data source, reading spine, file persistence, NEM-only scope).
- **Build plan** — `docs/build/build-plan.md` (tracks + critical path 0→1→2→3→5) and
  `docs/build/MERGE-PROTOCOL.md` (reviewed-PR-into-main rule).
- **Enforcement** — `tools/check_decision_hygiene.py` commit guard (changelog/ADR
  discipline), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`,
  `.claude/settings.json` PreToolUse hook.
- **Test fixture** — `tests/fixtures/nem_sa1_power_7d.json`, a captured real
  OpenElectricity v4 response, so the suite runs offline.
