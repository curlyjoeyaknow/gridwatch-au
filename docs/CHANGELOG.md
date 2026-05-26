# Changelog — GridWatch AU

All notable changes are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Tracks 2 + 3 — application facade + adapters (PR #3), on branch `track-2-3-app-adapters`.

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
