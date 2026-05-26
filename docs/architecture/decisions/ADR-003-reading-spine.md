# ADR-003 — Typed `Reading` hierarchy + fuel-tech taxonomy as the spine

**Status:** Accepted · 2026-05-26
**Context tags:** the spine, domain model, classification policy, OOP
**Related:** ADR-001 (ports & adapters), ADR-002 (data source)

## Context

Everything in the system — search, summaries, persistence, charts — operates on
"readings". If a reading were a loose dict, every consumer would re-implement unit
handling and fuel classification, and a mislabelled unit would silently corrupt
emissions maths. The shape of a reading and the meaning of a fuel tech are therefore
the **spine** of this system: the stable contract the rest derives from.

The feed mixes metrics in one payload — `power` (MW), `emissions` (tCO₂e), `price`
(AUD/MWh), `demand` (MW), `temperature` (°C) — and ~16 fuel techs (`solar_utility`,
`solar_rooftop`, `wind`, `hydro`, `coal_black`, `gas_ccgt/ocgt/...`, `distillate`,
`battery_charging/discharging`, `bioenergy_*`, `pumps`, `imports`, `exports`,
`curtailment_*`).

## Decision

1. **A typed `Reading` hierarchy** in `contracts/readings.py`: an abstract `Reading`
   (region, timestamp, value) with subclasses `PowerReading`, `EmissionReading`,
   `PriceReading`, `DemandReading`. `unit`, `label()`, and `to_row()` are **polymorphic**
   — each subclass knows its own unit and how to serialise. Consumers never branch on a
   string metric.
2. **A fuel-tech taxonomy** in `contracts/fueltech.py`: a `FuelCategory` enum
   (`SOLAR, WIND, HYDRO, BIOENERGY, COAL, GAS, DISTILLATE, BATTERY, PUMPS, IMPORT,
   EXPORT, CURTAILMENT, OTHER`) and a mapping from each raw vendor `fuel_tech` string to
   a `FuelTech` value object carrying `category`, `display_name`, and `is_renewable`.
3. **Renewable policy is explicit and recorded here:** `SOLAR, WIND, HYDRO, BIOENERGY`
   are renewable. `COAL, GAS, DISTILLATE` are not. `BATTERY, PUMPS, IMPORT, EXPORT,
   CURTAILMENT` are **excluded from the renewable-share numerator and denominator** —
   they are storage/interconnect/curtailment flows, not generation by source, and
   counting them would distort the share. Renewable share = renewable generation ÷
   total *generation* (renewable + non-renewable source techs only).
4. **An unknown fuel tech maps to `OTHER`, non-renewable, never crashes** — the feed can
   add techs without breaking ingestion (defensive per the robustness requirement).

## Consequences

- (+) One place defines units and renewable status; maths can't silently drift.
- (+) Polymorphism over `Reading` is clean (charts/summaries iterate uniformly).
- (+) The classification policy is auditable, not buried in a chart function.
- (−) Adding a metric/category is a spine change → an ADR and the guard's ADR warning;
  that friction is intended.

## Alternatives rejected

- **Dict-shaped readings with a `metric` string** — less code now, but pushes unit and
  renewable logic into every consumer and invites silent unit-mix bugs.
- **One flat `Reading` with an `is_renewable` bool passed in by the caller** — lets the
  caller decide policy ad hoc; the whole point is that policy is fixed here.
- **Counting battery discharge as renewable** — flattering but wrong; the stored energy
  may be fossil-charged, so it would overstate the renewable share.
