// ── GridWatch Australia — Data Layer ──
// Mirrors the Python domain model exactly.
// The live API endpoint: https://data.openelectricity.org.au/v4/stats/au/NEM/{REGION}/power/7d.json
// In production the backend fetches & caches this; here we expose helpers to work with it.

export const REGIONS = {
  NSW1: "New South Wales",
  QLD1: "Queensland",
  VIC1: "Victoria",
  SA1: "South Australia",
  TAS1: "Tasmania",
} as const;

export type RegionCode = keyof typeof REGIONS;

export const REGION_CODES = Object.keys(REGIONS) as RegionCode[];

// Fuel tech taxonomy (mirrors fueltech.py)
export const FUEL_CATEGORIES = {
  solar: { label: "Solar", color: "#f59e0b", renewable: true },
  wind: { label: "Wind", color: "#3b82f6", renewable: true },
  hydro: { label: "Hydro", color: "#06b6d4", renewable: true },
  bioenergy: { label: "Bioenergy", color: "#10b981", renewable: true },
  coal: { label: "Coal", color: "#78716c", renewable: false },
  gas: { label: "Gas", color: "#f97316", renewable: false },
  distillate: { label: "Distillate", color: "#dc2626", renewable: false },
  battery: { label: "Battery", color: "#8b5cf6", renewable: false },
  other: { label: "Other", color: "#94a3b8", renewable: false },
} as const;

export type FuelCategory = keyof typeof FUEL_CATEGORIES;

const FUEL_TECH_MAP: Record<string, FuelCategory> = {
  solar_utility: "solar",
  solar_rooftop: "solar",
  wind: "wind",
  hydro: "hydro",
  bioenergy_biomass: "bioenergy",
  bioenergy_biogas: "bioenergy",
  coal_black: "coal",
  coal_brown: "coal",
  gas_ccgt: "gas",
  gas_ocgt: "gas",
  gas_recip: "gas",
  gas_steam: "gas",
  gas_wcmg: "gas",
  distillate: "distillate",
  battery_charging: "battery",
  battery_discharging: "battery",
};

export function classify(rawFuel: string | null): FuelCategory {
  if (!rawFuel) return "other";
  return FUEL_TECH_MAP[rawFuel] ?? "other";
}

export function isRenewable(cat: FuelCategory): boolean {
  return FUEL_CATEGORIES[cat]?.renewable ?? false;
}

// ── Reading types ──
export interface Reading {
  region: RegionCode;
  timestamp: string; // ISO
  value: number;
  interval_minutes: number;
  metric: "power" | "emissions" | "price" | "demand";
  fuel_tech: string | null;
  fuel_category: FuelCategory;
  is_renewable: boolean;
  energy_mwh: number; // value * interval_minutes / 60
}

// ── Parse the OpenElectricity v4 payload into Readings ──
export function parsePayload(payload: any, region: RegionCode): Reading[] {
  const series: any[] = payload?.data ?? [];
  const readings: Reading[] = [];

  for (const s of series) {
    const stype: string = s.type;
    if (stype === "emissions_factor" || stype === "temperature") continue;

    const hist = s.history ?? {};
    const intervalStr: string = hist.interval ?? "";
    const interval = parseInterval(intervalStr);
    if (!interval || !hist.start || !Array.isArray(hist.data)) continue;

    const startMs = new Date(hist.start).getTime();
    const fuelRaw: string | null = s.fuel_tech ?? null;
    const fuelCat = fuelRaw ? classify(fuelRaw) : "other";
    const renewable = isRenewable(fuelCat);

    let metric: Reading["metric"];
    if (stype === "power" && fuelRaw === null) metric = "demand";
    else if (stype === "power") metric = "power";
    else if (stype === "emissions") metric = "emissions";
    else if (stype === "price") metric = "price";
    else if (stype === "demand") metric = "demand";
    else continue;

    for (let i = 0; i < hist.data.length; i++) {
      const raw = hist.data[i];
      if (raw === null || raw === undefined) continue;
      const value = Number(raw);
      if (!isFinite(value)) continue;
      const ts = new Date(startMs + i * interval * 60000).toISOString();
      readings.push({
        region,
        timestamp: ts,
        value,
        interval_minutes: interval,
        metric,
        fuel_tech: fuelRaw,
        fuel_category: fuelCat,
        is_renewable: renewable,
        energy_mwh: metric === "power" ? value * interval / 60 : 0,
      });
    }
  }
  return readings;
}

function parseInterval(s: string): number | null {
  const m = /^(\d+)([mhd])$/.exec(s.trim());
  if (!m) return null;
  const n = parseInt(m[1]);
  const unit = m[2];
  if (unit === "m") return n;
  if (unit === "h") return n * 60;
  if (unit === "d") return n * 1440;
  return null;
}

// ── RegionSummary ──
export interface RegionSummary {
  region: RegionCode;
  total_generation_mwh: number;
  renewable_generation_mwh: number;
  renewable_share_pct: number;
  total_emissions_tco2e: number;
  emissions_intensity: number;
  avg_price: number | null;
  peak_price: number | null;
  by_category_mwh: Partial<Record<FuelCategory, number>>;
  reading_count: number;
}

export function summarise(readings: Reading[], region: RegionCode): RegionSummary {
  const power = readings.filter(r => r.metric === "power");
  const totalGen = power.filter(r => !["battery","other"].includes(r.fuel_category))
    .reduce((s, r) => s + r.energy_mwh, 0);
  const renewableGen = power.filter(r => r.is_renewable)
    .reduce((s, r) => s + r.energy_mwh, 0);

  const emissions = readings.filter(r => r.metric === "emissions");
  const totalEmissions = emissions.reduce((s, r) => s + r.value, 0);

  const prices = readings.filter(r => r.metric === "price").map(r => r.value);
  const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;
  const peakPrice = prices.length ? Math.max(...prices) : null;

  const byCat: Partial<Record<FuelCategory, number>> = {};
  for (const r of power) {
    if (!["battery","other"].includes(r.fuel_category)) {
      byCat[r.fuel_category] = (byCat[r.fuel_category] ?? 0) + r.energy_mwh;
    }
  }

  return {
    region,
    total_generation_mwh: totalGen,
    renewable_generation_mwh: renewableGen,
    renewable_share_pct: totalGen > 0 ? (renewableGen / totalGen) * 100 : 0,
    total_emissions_tco2e: totalEmissions,
    emissions_intensity: totalGen > 0 ? totalEmissions / totalGen : 0,
    avg_price: avgPrice,
    peak_price: peakPrice,
    by_category_mwh: byCat,
    reading_count: readings.length,
  };
}

// ── PeriodPoint (aggregate.py mirror) ──
export type Period = "day" | "week" | "month";

export interface PeriodPoint {
  period_start: string; // ISO date string
  region: RegionCode;
  total_generation_mwh: number;
  renewable_share_pct: number;
  total_emissions_tco2e: number;
  emissions_intensity: number;
  avg_price: number | null;
  avg_demand_mw: number | null;
  by_category_mwh: Partial<Record<FuelCategory, number>>;
}

function floorPeriod(ts: Date, period: Period): string {
  const d = new Date(ts);
  if (period === "day") {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  if (period === "week") {
    const day = d.getDay(); // 0=Sun, 1=Mon…
    const diff = (day + 6) % 7; // days since Monday
    const monday = new Date(d);
    monday.setDate(d.getDate() - diff);
    return `${monday.getFullYear()}-W${String(getISOWeek(monday)).padStart(2, "0")}`;
  }
  // month
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function getISOWeek(d: Date): number {
  const tmp = new Date(d);
  tmp.setHours(0, 0, 0, 0);
  tmp.setDate(tmp.getDate() + 3 - ((tmp.getDay() + 6) % 7));
  const week1 = new Date(tmp.getFullYear(), 0, 4);
  return 1 + Math.round(((tmp.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7);
}

export function aggregate(readings: Reading[], period: Period, regionFilter?: RegionCode): PeriodPoint[] {
  const filtered = regionFilter ? readings.filter(r => r.region === regionFilter) : readings;
  const buckets = new Map<string, Reading[]>();

  for (const r of filtered) {
    const key = `${r.region}||${floorPeriod(new Date(r.timestamp), period)}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(r);
  }

  const points: PeriodPoint[] = [];
  for (const [key, group] of buckets) {
    const [region, period_start] = key.split("||") as [RegionCode, string];
    const power = group.filter(r => r.metric === "power" && !["battery","other"].includes(r.fuel_category));
    const totalGen = power.reduce((s, r) => s + r.energy_mwh, 0);
    const renewGen = power.filter(r => r.is_renewable).reduce((s, r) => s + r.energy_mwh, 0);
    const totalEmit = group.filter(r => r.metric === "emissions").reduce((s, r) => s + r.value, 0);
    const prices = group.filter(r => r.metric === "price").map(r => r.value);
    const demands = group.filter(r => r.metric === "demand").map(r => r.value);

    const byCat: Partial<Record<FuelCategory, number>> = {};
    for (const r of power) {
      byCat[r.fuel_category] = (byCat[r.fuel_category] ?? 0) + r.energy_mwh;
    }

    points.push({
      period_start,
      region,
      total_generation_mwh: totalGen,
      renewable_share_pct: totalGen > 0 ? (renewGen / totalGen) * 100 : 0,
      total_emissions_tco2e: totalEmit,
      emissions_intensity: totalGen > 0 ? totalEmit / totalGen : 0,
      avg_price: prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null,
      avg_demand_mw: demands.length ? demands.reduce((a, b) => a + b, 0) / demands.length : null,
      by_category_mwh: byCat,
    });
  }

  return points.sort((a, b) => a.period_start.localeCompare(b.period_start));
}

// ── Colour helpers ──
export const STATE_COLORS: Record<RegionCode, string> = {
  NSW1: "#10b981",
  QLD1: "#f59e0b",
  VIC1: "#3b82f6",
  SA1: "#8b5cf6",
  TAS1: "#06b6d4",
};

export function fmt(n: number, decimals = 1): string {
  return n.toLocaleString("en-AU", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function fmtMWh(n: number): string {
  if (n >= 1_000_000) return `${fmt(n / 1_000_000, 2)} TWh`;
  if (n >= 1_000) return `${fmt(n / 1_000, 1)} GWh`;
  return `${fmt(n, 0)} MWh`;
}

export function fmtPrice(n: number | null): string {
  if (n === null) return "—";
  return `$${fmt(n, 2)}/MWh`;
}
