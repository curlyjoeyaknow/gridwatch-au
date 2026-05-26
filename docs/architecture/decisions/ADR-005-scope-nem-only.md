# ADR-005 — Scope: NEM regions only

**Status:** Accepted · 2026-05-26
**Context tags:** scope, domain boundary
**Related:** ADR-002 (data source)

## Context

"Australian electricity" is not one grid. The **National Electricity Market (NEM)**
covers the eastern and southern states — NSW, QLD, VIC, SA, TAS (ACT sits inside NSW1).
**Western Australia** runs on the separate **SWIS** (Wholesale Electricity Market) and
the **Northern Territory** on its own systems. The OpenElectricity feed used here
(ADR-002) is organised by NEM region code (`NSW1, QLD1, VIC1, SA1, TAS1`).

## Decision

1. **GridWatch covers the five NEM regions only:** `NSW1, QLD1, VIC1, SA1, TAS1`. These
   are the recognised region codes the manager and adapter accept.
2. **An unknown region code is rejected** with a `ValidationError` listing the valid
   codes — it is not silently treated as empty.
3. **The boundary is documented** in the README and surfaced in the CLI, so the absence
   of WA/NT reads as a deliberate scope decision, not a data gap.

## Consequences

- (+) Honest scope; matches the data source exactly; no half-supported regions.
- (−) No WA/NT coverage. Adding SWIS would mean a different data source/adapter and is
  out of scope for this version.

## Alternatives rejected

- **Claim "all of Australia"** — would imply WA/NT coverage the NEM feed cannot provide;
  misleading for an SDG-reporting tool.
- **Silently accept any region string** — turns a typo or an out-of-scope request into
  an empty result that looks like "no generation", which is worse than a clear error.
