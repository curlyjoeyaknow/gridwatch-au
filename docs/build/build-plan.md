# GridWatch AU — Build Plan & Critical Path

Companion to the PRD and ADRs. Spec-driven: contracts first, the CLI last.

## Why this order

Search, summaries, persistence, and charts all derive from the **reading contract**
(ADR-003) reached through **ports** (ADR-001). Nothing above is trustworthy until those
shapes exist, so the contracts come first; the user-facing CLI is a thin driving
adapter at the end.

```
        ┌──────────────── 0. CONTRACTS (spine) ────────────────┐
        │  Reading hierarchy · FuelTech taxonomy · RegionSummary │
        │  DataSource / Repository ports · exception hierarchy   │
        └───────┬───────────────────────┬───────────────────────┘
                │                       │
        1. DOMAIN                3. ADAPTERS
        Region aggregate          OpenElectricityClient · FakeDataSource
        Analytics (pure fns)      JsonRepository · CsvRepository
                │                       │
                └────────► 2. APPLICATION ◄────────┘
                           EnergyGridManager (facade)
                                   │
        4. VIZ (matplotlib) ──parallel──┐         │
                                        └──► 5. CLI (driving adapter) + live e2e
```

**Critical path:** `0 → 1 → 2 → 3 → 5`. Track 4 (viz) parallels once 0–1 land.

## PR / track mapping

Each track lands via a reviewed PR into `main` (see `MERGE-PROTOCOL.md`).

- **PR #1 — Scaffolding & process** (this PR): repo, toolchain, docs/ADRs, guard,
  pre-commit, CI, fixture.
- **PR #2 — Tracks 0 + 1:** contracts spine + domain.
- **PR #3 — Tracks 2 + 3:** application facade + adapters (incl. live API client).
- **PR #4 — Tracks 4 + 5:** visualisations + CLI + live end-to-end run.

## Tracks

Legend: ✅ done · 🟡 partial · ⬜ todo

### Track 0 — Contracts spine  ✅
| # | Task | Status |
|---|------|--------|
| 0.1 | `exceptions.py` — `GridWatchError` hierarchy | ✅ |
| 0.2 | `contracts/fueltech.py` — `FuelCategory` + taxonomy + renewable policy (ADR-003) | ✅ |
| 0.3 | `contracts/readings.py` — `Reading` ABC + Power/Emission/Price/Demand | ✅ |
| 0.4 | `contracts/summary.py` — `RegionSummary` value object | ✅ |
| 0.5 | `ports/datasource.py`, `ports/repository.py` — port ABCs | ✅ |

### Track 1 — Domain  ✅
| 1.1 | `domain/region.py` — Region aggregate (encapsulated readings, find/filter) | ✅ |
| 1.2 | `domain/analytics.py` — pure summary functions (share, intensity, price) | ✅ |

### Track 2 — Application  ⬜
| 2.1 | `application/manager.py` — `EnergyGridManager` facade (CRUD/search/import/save) | ⬜ |

### Track 3 — Adapters  ⬜
| 3.1 | `adapters/openelectricity.py` — real `DataSource`, vendor→`Reading` mapping | ⬜ |
| 3.2 | `adapters/fake_source.py` — `FakeDataSource` for tests | ⬜ |
| 3.3 | `adapters/json_repo.py`, `adapters/csv_repo.py` — `Repository` impls | ⬜ |

### Track 4 — Visualisations  ⬜
| 4.1 | `viz/charts.py` — fuel mix · renewable share · emissions · price (PNG) | ⬜ |

### Track 5 — CLI & e2e  ⬜
| 5.1 | `cli.py` — menu-driven driving adapter, per-action error handling | ⬜ |
| 5.2 | Live end-to-end run against the real API; finalise README | ⬜ |
