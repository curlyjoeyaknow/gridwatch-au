# GridWatch AU — System Architecture

## Shape
Ports & adapters (hexagonal) around a pure domain core. Dependencies point **inward**:
adapters and the CLI depend on the core; the core depends only on its own contracts and
the port ABCs.

```
            driving adapter                         driven adapters
        ┌────────────────────┐                 ┌──────────────────────────┐
        │       cli.py        │                 │ OpenElectricityClient  ───┼─▶ HTTP API
        │ (menu, error guard) │                 │ FakeDataSource            │
        └─────────┬───────────┘                 │ JsonRepository  ──────────┼─▶ files
                  │ calls                        │ CsvRepository             │
                  ▼                              └─────────┬────────────────┘
        ┌───────────────────────────┐    implements        │ implements
        │  application/manager.py    │   ┌──────────────────┴───────────────┐
        │   EnergyGridManager        │   │ ports/ : DataSource · Repository  │  ← spine
        │  CRUD·search·import·save   │◀──┤ (ABCs the core depends on)        │
        └─────────┬─────────────────┘   └───────────────────────────────────┘
                  │ uses
                  ▼
        ┌───────────────────────────┐   ┌───────────────────────────────────┐
        │ domain/ : Region·Analytics │   │ contracts/ : Reading hierarchy ·   │  ← spine
        │ (aggregate + pure folds)   │──▶│ FuelTech taxonomy · RegionSummary  │
        └───────────────────────────┘   └───────────────────────────────────┘
                                              exceptions.py (GridWatchError…)
```

## Layers
- **contracts/ (spine)** — `Reading` ABC + `PowerReading`/`EmissionReading`/
  `PriceReading`/`DemandReading`; `FuelTech` + `FuelCategory`; `RegionSummary`. Pure
  data + classification policy.
- **ports/ (spine)** — `DataSource` and `Repository` ABCs.
- **domain/** — `Region` (aggregate that owns its readings) and `analytics` (pure
  functions computing summaries). No I/O.
- **adapters/** — `OpenElectricityClient` (real, maps vendor JSON → readings),
  `FakeDataSource`, `JsonRepository`, `CsvRepository`.
- **application/** — `EnergyGridManager`, the facade the CLI talks to; orchestrates
  import/CRUD/search/summary/persist via the ports.
- **viz/** — `charts`, matplotlib renderers over readings/summaries.
- **cli.py** — menu-driven driving adapter; wraps every action in error handling.

## Error model
```
GridWatchError
 ├─ DataSourceError      # network timeout, non-200, malformed/partial JSON, bad region
 ├─ ValidationError      # bad region code, bad metric, unparseable date/number
 ├─ RegionNotFoundError  # operating on a region not loaded
 └─ PersistenceError     # file I/O, corrupt save file
```
Each layer raises the precise type; the CLI catches `GridWatchError` per action so a
failure degrades to a message, never a stack-trace crash.

## Data flow (live import)
1. CLI asks `EnergyGridManager.import_region("SA1", source)`.
2. Manager calls `source.fetch_power("SA1")` (port).
3. `OpenElectricityClient` GETs the v4 feed (with `User-Agent`), parses each series,
   reconstructs timestamps, and returns a list of typed `Reading`s — **vendor shape
   stops here**.
4. Manager stores them on the `Region`; analytics/summary/charts read from the region.
5. `manager.save(repo)` writes JSON/CSV via the `Repository` port.

## Testing strategy
- Core (contracts/domain/application) tested with `FakeDataSource` — no network.
- The real adapter's mapping is asserted against `tests/fixtures/nem_sa1_power_7d.json`
  (a captured real response).
- Persistence is round-tripped through **real temp files**.
- Charts render on the headless `Agg` backend and assert output files exist.
