# ADR-002 — Data source: OpenElectricity v4 static JSON feed

**Status:** Accepted · 2026-05-26
**Context tags:** data source, API, free-tier, robustness
**Related:** ADR-001 (ports & adapters), ADR-005 (NEM-only scope)

## Context

The brief requires real data from a free, no-payment source — not synthesised numbers.
For the Australian electricity grid the candidates are: the AEMO NEMWeb data dumps, the
new keyed OpenElectricity platform API (v4, requires a free account + API key), and the
**OpenElectricity static JSON feed** that powers the public site.

We probed all three (2026-05-26):
- `data.openelectricity.org.au/v4/stats/au/NEM/{REGION}/power/7d.json` → **HTTP 200**,
  `created_at` was the current day (live), 31–33 series per region, **no key required**.
- The same `v3` path is frozen at 2024-12-13 (stale).
- AEMO NEMWeb → reachable but ships zipped, wide CSV reports designed for market
  systems, not app consumption.
- A bare Python `urllib`/default User-Agent request to the feed → **HTTP 403**; the
  same request with a browser-like `User-Agent` → 200.

## Decision

1. **Use the OpenElectricity v4 static feed** as the live data source, one request per
   region: `…/v4/stats/au/NEM/{REGION}/power/7d.json`.
2. **The adapter always sends a `User-Agent` header.** The 403-without-UA behaviour is
   encoded in the adapter and covered by the design, not rediscovered at runtime.
3. **Series → readings mapping** lives in the adapter (ADR-001): each `(type, fuel_tech)`
   series with a `history{start, interval, data[]}` block is expanded into typed
   `Reading`s, timestamps reconstructed as `start + interval × index`.
4. **The captured fixture is the test contract.** A real response is saved under
   `tests/fixtures/` and the mapping is asserted against it offline.

## Consequences

- (+) Real, current, regional Australian grid data with zero credentials or cost.
- (+) Simple GET + JSON — no CSV wrangling, no OAuth.
- (−) An undocumented static feed can change/disappear; mitigated by isolating it in one
  adapter (ADR-001) and shipping an offline fixture so tests never depend on it.
- (−) `power/7d` is a rolling 7-day window at 5-/30-minute resolution — fine for this
  system; longer history would need the keyed API (a future adapter).

## Alternatives rejected

- **Keyed OpenElectricity platform API** — most "proper", but needs an account/API key,
  which conflicts with the no-friction brief; can be added later as a second adapter.
- **AEMO NEMWeb CSV** — authoritative and free, but zipped wide-format market reports
  are heavy to parse and a poor fit for a teaching-scale management system.
- **Synthesised data** — explicitly disallowed by the brief.
