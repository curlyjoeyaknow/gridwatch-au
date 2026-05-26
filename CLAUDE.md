# CLAUDE.md — GridWatch AU

Project memory for Claude Code. Read this first, every session. It is the
non-negotiable layer; the *why* behind it lives in `docs/`.

GridWatch AU is a **management system** for Australian electricity generation &
emissions. Members of the public, students, or analysts can **organise, search, and
maintain** time-series readings for each NEM region, pull **live data** from the free
OpenElectricity feed, and **visualise** the fuel mix, renewable share, and emissions.
It exists to make progress on **UN SDG 7 (Affordable & Clean Energy)** and **SDG 13
(Climate Action)** legible from real grid data.

## Method
This repo is built with **spec-driven delivery**: contracts first, decisions as ADRs,
build order from the critical path, real TDD. The patterns below are defaults here,
not options.

## Non-negotiables (this repo)

1. **The domain contracts are the spine.** `src/gridwatch/contracts/` (the `Reading`
   hierarchy, the fuel-tech taxonomy, `RegionSummary`) and `src/gridwatch/ports/` (the
   `DataSource` / `Repository` ABCs) are the stable shapes everything derives from. A
   change here is a design change → record an ADR (the guard warns if you don't).
2. **Ports & adapters at every boundary.** The core depends on a *port*
   (`ports/`), never a vendor SDK. External things (OpenElectricity) live behind an
   adapter (`adapters/`). Map the vendor shape to **our** contract (`Reading`) inside
   the adapter — never pass a raw vendor dict through the port. A leaky adapter is a bug.
3. **Real data, never synthesised.** Live readings come from the real OpenElectricity
   feed. Tests run **offline against a captured real response**
   (`tests/fixtures/`), never hand-faked numbers dressed up as API data.
4. **Real TDD.** Test first. Never mock the unit under test. The only fake is at a port
   (`FakeDataSource`); JSON/CSV persistence uses **real files on disk**, not mocks. A
   test that can't fail is not a test. Don't fake an implementation to pass a test.
5. **Decision hygiene.** A source change ships with a `docs/CHANGELOG.md` entry; a real
   design decision ships with an ADR. The commit guard enforces the changelog
   automatically (see Enforcement).
6. **Honest classification.** What counts as "renewable", and how imports/exports,
   battery, and curtailment are treated, is a policy decision recorded in ADR-003 — not
   tweaked silently to make a chart look greener.

## Repo map
```
docs/
  prd/                00-gridwatch-prd
  architecture/       system-architecture
    decisions/        ADR-001 ports · 002 data-source · 003 reading-spine ·
                      004 file-persistence · 005 scope-nem-only
  build/              build-plan (tracks, critical path 0→1→2→3→5) · MERGE-PROTOCOL
  CHANGELOG.md
src/gridwatch/
  contracts/          readings · fueltech · summary          ← the spine
  ports/              datasource · repository                ← the spine (interfaces)
  domain/             region · analytics (pure)
  adapters/           openelectricity · fake_source · json_repo · csv_repo
  application/        manager (EnergyGridManager facade)
  viz/                charts (matplotlib)
  cli.py              menu-driven driving adapter (built last)
  exceptions.py       GridWatchError hierarchy
tools/                check_decision_hygiene.py   (commit guard)
tests/                test-first; fixtures/ holds a captured real API response
```

## How to run
```bash
python3 -m venv .venv && . .venv/bin/activate    # setup
pip install -e ".[dev]"
pytest -q -m "not slow"                          # fast suite (what pre-commit runs)
pytest -q                                        # full suite (offline; real file round-trips)
ruff check src tests                             # lint
python -m gridwatch.cli                          # run the app
```

## Definition of done (a change is not done until)
- tests written first and passing (`pytest -q` green, full suite);
- ports kept clean (no vendor shape leaking past an adapter);
- a real design decision recorded as an ADR; the spine guarded;
- `docs/CHANGELOG.md` updated;
- non-negotiables (above) still hold.

## Enforcement (so the method doesn't rely on memory)
- **`.pre-commit-config.yaml`** — ruff + fast tests + decision-hygiene on every commit.
  Enable once: `pip install pre-commit && pre-commit install`.
- **`.github/workflows/ci.yml`** — ruff + **full** test suite + changelog discipline on
  PRs. The hard merge gate.
- **`.claude/settings.json`** — a `PreToolUse` Bash hook that **blocks a `git commit`**
  (exit 2) if source changed without a changelog entry. Deterministic.

## Merge protocol
Every track lands via a reviewed PR into `main`. No direct pushes to `main`. See
`docs/build/MERGE-PROTOCOL.md`.

## Where to resume
Critical path: **0 Contracts → 1 Domain → 2 Application → 3 Adapters → 5 CLI**
(Track 4 Viz parallels). See `docs/build/build-plan.md` for live track status.
