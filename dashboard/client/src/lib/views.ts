/**
 * View types — mirror the JSON produced by materialize.py exactly.
 * The frontend never parses raw readings; it only consumes these pre-aggregated views.
 */

export const NEM_REGIONS = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"] as const;
export type RegionCode = typeof NEM_REGIONS[number];

export const REGION_NAMES: Record<RegionCode, string> = {
  NSW1: "New South Wales",
  QLD1: "Queensland",
  VIC1: "Victoria",
  SA1:  "South Australia",
  TAS1: "Tasmania",
};

// Short state labels without the NEM suffix digit
export const REGION_SHORT: Record<RegionCode, string> = {
  NSW1: "NSW",
  QLD1: "QLD",
  VIC1: "VIC",
  SA1:  "SA",
  TAS1: "TAS",
};

/**
 * Format a period string for chart x-axis ticks.
 *
 * daily   "2024-06-29"  → "29 Jun"
 * weekly  "2024-W26"    → "W26 '24"
 * monthly "2024-06"     → "Jun '24"
 * yearly  "FY2024"      → "FY2024"
 */
export function formatPeriod(val: string, grain: Grain): string {
  if (!val) return "";
  if (grain === "daily") {
    // "2024-06-29" → "29 Jun"
    const d = new Date(val + "T00:00:00");
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
  }
  if (grain === "weekly") {
    // "2024-W26" → "W26 '24"
    const m = val.match(/^(\d{4})-W(\d{2})$/);
    if (m) return `W${m[2]} '${m[1].slice(2)}`;
    return val;
  }
  if (grain === "monthly") {
    // "2024-06" → "Jun '24"
    const d = new Date(val + "-01T00:00:00");
    return d.toLocaleDateString("en-AU", { month: "short", year: "2-digit" });
  }
  // yearly: "FY2024" → "FY2024" (already readable)
  return val;
}

export const STATE_COLORS: Record<RegionCode, string> = {
  NSW1: "#10b981",
  QLD1: "#f59e0b",
  VIC1: "#3b82f6",
  SA1:  "#8b5cf6",
  TAS1: "#06b6d4",
};

export const FUEL_META: Record<string, { label: string; color: string; renewable: boolean }> = {
  SOLAR:      { label: "Solar",      color: "#f59e0b", renewable: true  },
  WIND:       { label: "Wind",       color: "#3b82f6", renewable: true  },
  HYDRO:      { label: "Hydro",      color: "#06b6d4", renewable: true  },
  BIOENERGY:  { label: "Bioenergy",  color: "#10b981", renewable: true  },
  COAL:       { label: "Coal",       color: "#78716c", renewable: false },
  GAS:        { label: "Gas",        color: "#f97316", renewable: false },
  DISTILLATE: { label: "Distillate", color: "#dc2626", renewable: false },
  BATTERY:    { label: "Battery",    color: "#8b5cf6", renewable: false },
  PUMPS:      { label: "Pumps",      color: "#94a3b8", renewable: false },
  OTHER:      { label: "Other",      color: "#cbd5e1", renewable: false },
};

export type Grain = "daily" | "weekly" | "monthly" | "yearly";

// ── summary.json ──────────────────────────────────────────────────────────────
export interface RegionSummary {
  region: string;
  total_generation_mwh: number;
  renewable_generation_mwh: number;
  renewable_share_pct: number;
  total_emissions_tco2e: number;
  emissions_intensity: number;
  avg_price: number | null;
  peak_price: number | null;
  min_price: number | null;
  first_date: string | null;
  last_date: string | null;
  days_covered: number;
  by_category_mwh: Record<string, number>;
  source?: string;
}

// ── daily | weekly | monthly | yearly ────────────────────────────────────────
export interface PeriodRow {
  period: string;
  fuel: Record<string, number>;  // { SOLAR: mwh, WIND: mwh, … }
  renewable_share_pct: number;
  total_gen_mwh: number;
  avg_price: number | null;
  peak_price: number | null;
  min_price: number | null;
  avg_demand_mw: number | null;
  peak_demand_mw: number | null;
  total_emissions_tco2e: number | null;
}

export interface GrainView {
  grain: Grain;
  periods: string[];
  regions: Record<string, PeriodRow[]>;
}

// ── last_updated.json ─────────────────────────────────────────────────────────
export interface LastUpdated {
  materialized_at: string;
  elapsed_seconds: number;
  total_events: number;
  regions: number;
  first_date: string | null;
  last_date: string | null;
}

// ── raw_recent.json ───────────────────────────────────────────────────────────
export interface RawRow {
  region: string;
  metric: string;
  fuel_tech: string | null;
  timestamp: string;
  value: number;
  unit: string;
  interval_minutes: number;
}

export interface RawRecent {
  count: number;
  rows: RawRow[];
}

// ── live /api/live ────────────────────────────────────────────────────────────
export interface LiveData {
  fetchedAt: string;
  source: string;
  regions: Record<string, RegionSummary | null>;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
export function fmt(n: number, d = 1): string {
  return n.toLocaleString("en-AU", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function fmtMWh(n: number): string {
  if (n >= 1_000_000) return `${fmt(n / 1_000_000, 2)} TWh`;
  if (n >= 1_000)     return `${fmt(n / 1_000, 1)} GWh`;
  return `${fmt(n, 0)} MWh`;
}

export function fmtPrice(n: number | null): string {
  if (n === null) return "—";
  return `$${fmt(n, 2)}/MWh`;
}

export function fmtPct(n: number): string {
  return `${fmt(n, 1)}%`;
}

export function renewableColor(pct: number): string {
  if (pct >= 60) return "#10b981";
  if (pct >= 30) return "#f59e0b";
  return "#ef4444";
}

/** Flatten a GrainView for a single region into chart-ready { period, ...fuels, meta } rows */
export function flattenRegion(view: GrainView, region: string): PeriodRow[] {
  return view.regions[region] ?? [];
}

/** Get all unique fuel categories present in a GrainView */
export function allFuels(view: GrainView): string[] {
  const seen = new Set<string>();
  for (const rows of Object.values(view.regions)) {
    for (const row of rows) {
      Object.keys(row.fuel).forEach(f => seen.add(f));
    }
  }
  const order = ["SOLAR","WIND","HYDRO","BIOENERGY","GAS","COAL","DISTILLATE"];
  return [
    ...order.filter(f => seen.has(f)),
    ...[...seen].filter(f => !order.includes(f)).sort(),
  ];
}

/** Merge per-region rows into a single national aggregate per period */
export function nationalAggregate(view: GrainView, regionFilter?: string[]): PeriodRow[] {
  const regions = regionFilter
    ? Object.keys(view.regions).filter(r => regionFilter.includes(r))
    : Object.keys(view.regions);

  const byPeriod = new Map<string, PeriodRow>();

  for (const region of regions) {
    for (const row of view.regions[region] ?? []) {
      const existing = byPeriod.get(row.period);
      if (!existing) {
        byPeriod.set(row.period, { ...row, fuel: { ...row.fuel } });
      } else {
        // Merge fuel mwh
        for (const [cat, mwh] of Object.entries(row.fuel)) {
          existing.fuel[cat] = (existing.fuel[cat] ?? 0) + mwh;
        }
        existing.total_gen_mwh += row.total_gen_mwh;
        if (row.total_emissions_tco2e !== null && existing.total_emissions_tco2e !== null) {
          existing.total_emissions_tco2e += row.total_emissions_tco2e;
        }
        // Weighted avg price (approx: simple avg across regions)
        if (row.avg_price !== null && existing.avg_price !== null) {
          existing.avg_price = (existing.avg_price + row.avg_price) / 2;
        }
        if (row.peak_price !== null) {
          existing.peak_price = Math.max(existing.peak_price ?? 0, row.peak_price);
        }
        if (row.avg_demand_mw !== null && existing.avg_demand_mw !== null) {
          existing.avg_demand_mw = existing.avg_demand_mw + row.avg_demand_mw;
        }
      }
    }
  }

  // Recompute renewable_share_pct for aggregated rows
  const rows = [...byPeriod.values()].sort((a, b) => a.period.localeCompare(b.period));
  for (const row of rows) {
    const ren = (["SOLAR","WIND","HYDRO","BIOENERGY"] as string[])
      .reduce((s, c) => s + (row.fuel[c] ?? 0), 0);
    const gen = row.total_gen_mwh;
    row.renewable_share_pct = gen > 0 ? (ren / gen) * 100 : 0;
  }
  return rows;
}
