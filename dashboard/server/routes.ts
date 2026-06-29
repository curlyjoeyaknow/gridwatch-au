/**
 * GridWatch AU — Express API routes
 *
 * Pure file server: reads pre-built JSON views from data/views/ and returns
 * them with appropriate caching headers. No Python runtime needed at request
 * time. All computation happens in materialize.py (DuckDB).
 *
 * Views are produced by:
 *   1. scripts/backfill.py   — fetches Pro API → Parquet ledger
 *   2. scripts/materialize.py — DuckDB aggregations → data/views/*.json
 *
 * Endpoints
 * ─────────
 *   GET /api/views/summary       → summary.json       (per-region KPIs, full window)
 *   GET /api/views/daily         → daily.json         (day-grain time series)
 *   GET /api/views/weekly        → weekly.json
 *   GET /api/views/monthly       → monthly.json
 *   GET /api/views/yearly        → yearly.json
 *   GET /api/views/raw_recent    → raw_recent.json    (last 8 days, for Data table)
 *   GET /api/views/last_updated  → last_updated.json
 *
 *   GET /api/refresh             → triggers a live 7-day fetch from OpenElectricity
 *                                   (free endpoint, no API key needed) and merges
 *                                   into the views so the dashboard stays current
 *                                   even without running backfill.py locally.
 */

import type { Express } from "express";
import type { Server } from "http";
import fs from "fs";
import path from "path";
import https from "https";

// ── View file locations ───────────────────────────────────────────────────────
const VIEWS_DIR = path.resolve(process.cwd(), "data", "views");
const VALID_VIEWS = new Set([
  "summary", "daily", "weekly", "monthly", "yearly", "raw_recent", "last_updated"
]);

// ── Live API config (free endpoint, for /api/refresh) ────────────────────────
const OE_FREE_BASE = "https://data.openelectricity.org.au/v4/stats/au/NEM/{region}/power/7d.json";
const OE_PRO_BASE  = "https://api.openelectricity.org.au/v4";
const NEM_REGIONS  = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"];
const UA = "gridwatch-au/2.0 (+https://github.com/curlyjoeyaknow/gridwatch-au)";
const API_KEY = process.env.OPENELECTRICITY_API_KEY ?? "";

// In-memory live-data cache (falls back to free 7d endpoint)
const liveCache = new Map<string, { data: unknown; fetchedAt: number }>();
const LIVE_TTL_MS = 15 * 60 * 1000; // 15 min

function readViewFile(name: string): unknown | null {
  const fp = path.join(VIEWS_DIR, `${name}.json`);
  try {
    const raw = fs.readFileSync(fp, "utf8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function viewFileAge(name: string): number | null {
  const fp = path.join(VIEWS_DIR, `${name}.json`);
  try {
    return Date.now() - fs.statSync(fp).mtimeMs;
  } catch {
    return null;
  }
}

function fetchLive(region: string): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const url = OE_FREE_BASE.replace("{region}", region);
    const req = https.get(url, { headers: { "User-Agent": UA } }, (res) => {
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => {
        try { resolve(JSON.parse(body)); }
        catch { reject(new Error("JSON parse error")); }
      });
    });
    req.on("error", reject);
    req.setTimeout(25000, () => { req.destroy(); reject(new Error("timeout")); });
  });
}

/** Parse the free-API 7d payload into the same shape as a summary.json row */
function parseFreePayload(payload: any, region: string) {
  const FUEL_MAP: Record<string, { cat: string; renewable: boolean; countsAsGen: boolean }> = {
    solar_utility: { cat: "SOLAR", renewable: true, countsAsGen: true },
    solar_rooftop: { cat: "SOLAR", renewable: true, countsAsGen: true },
    wind: { cat: "WIND", renewable: true, countsAsGen: true },
    hydro: { cat: "HYDRO", renewable: true, countsAsGen: true },
    bioenergy_biomass: { cat: "BIOENERGY", renewable: true, countsAsGen: true },
    bioenergy_biogas: { cat: "BIOENERGY", renewable: true, countsAsGen: true },
    coal_black: { cat: "COAL", renewable: false, countsAsGen: true },
    coal_brown: { cat: "COAL", renewable: false, countsAsGen: true },
    gas_ccgt: { cat: "GAS", renewable: false, countsAsGen: true },
    gas_ocgt: { cat: "GAS", renewable: false, countsAsGen: true },
    gas_recip: { cat: "GAS", renewable: false, countsAsGen: true },
    gas_steam: { cat: "GAS", renewable: false, countsAsGen: true },
    gas_wcmg: { cat: "GAS", renewable: false, countsAsGen: true },
    distillate: { cat: "DISTILLATE", renewable: false, countsAsGen: true },
  };

  const series: any[] = payload?.data ?? [];
  const catMwh: Record<string, number> = {};
  let totalGenMwh = 0, renGenMwh = 0, totalEmissions = 0;
  const prices: number[] = [];

  for (const s of series) {
    const stype: string = s.type;
    const fuelRaw: string | null = s.fuel_tech ?? null;
    const hist = s.history ?? {};
    const intervalStr: string = hist.interval ?? "";
    const m = /^(\d+)([mhd])$/.exec(intervalStr.trim());
    if (!m) continue;
    const interval = parseInt(m[1]) * (m[2] === "m" ? 1 : m[2] === "h" ? 60 : 1440);
    const startMs = hist.start ? new Date(hist.start).getTime() : null;
    if (!startMs || !Array.isArray(hist.data)) continue;

    const fm = fuelRaw ? FUEL_MAP[fuelRaw] : null;

    if (stype === "power" && fuelRaw && fm) {
      const mwh = (hist.data as any[]).reduce((sum: number, v: any) => {
        if (v == null) return sum;
        return sum + (Number(v) * interval / 60);
      }, 0);
      if (fm.countsAsGen) {
        catMwh[fm.cat] = (catMwh[fm.cat] ?? 0) + mwh;
        totalGenMwh += mwh;
        if (fm.renewable) renGenMwh += mwh;
      }
    } else if (stype === "emissions") {
      const em = (hist.data as any[]).reduce((sum: number, v: any) => sum + (v == null ? 0 : Number(v)), 0);
      totalEmissions += em;
    } else if (stype === "price") {
      for (const v of hist.data as any[]) {
        if (v != null) prices.push(Number(v));
      }
    }
  }

  const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;
  const peakPrice = prices.length ? Math.max(...prices) : null;

  return {
    region,
    total_generation_mwh: Math.round(totalGenMwh * 10) / 10,
    renewable_generation_mwh: Math.round(renGenMwh * 10) / 10,
    renewable_share_pct: totalGenMwh > 0 ? Math.round((renGenMwh / totalGenMwh) * 10000) / 100 : 0,
    total_emissions_tco2e: Math.round(totalEmissions * 10) / 10,
    emissions_intensity: totalGenMwh > 0 ? Math.round((totalEmissions / totalGenMwh) * 10000) / 10000 : 0,
    avg_price: avgPrice !== null ? Math.round(avgPrice * 100) / 100 : null,
    peak_price: peakPrice !== null ? Math.round(peakPrice * 100) / 100 : null,
    by_category_mwh: catMwh,
    source: "live_7d",
  };
}

export async function registerRoutes(httpServer: Server, app: Express) {

  // ── GET /api/views/:name — serve pre-built materialized views ─────────────
  app.get("/api/views/:name", (req, res) => {
    const name = req.params.name;
    if (!VALID_VIEWS.has(name)) {
      return res.status(404).json({ error: `Unknown view: ${name}` });
    }

    const data = readViewFile(name);
    if (data === null) {
      // View file doesn't exist yet — return a helpful message
      return res.status(503).json({
        error: "View not yet materialized",
        hint: "Run: python scripts/materialize.py (after python scripts/backfill.py)",
        view: name,
      });
    }

    const age = viewFileAge(name);
    // Cache for 5 min client-side, stale-while-revalidate 30 min
    res.setHeader("Cache-Control", "public, max-age=300, stale-while-revalidate=1800");
    if (age !== null) {
      res.setHeader("X-View-Age-Seconds", Math.floor(age / 1000).toString());
    }
    return res.json(data);
  });

  // ── GET /api/live — fetch live 7d data from free endpoint (always fresh) ──
  // Used by the frontend as a fallback when no ledger views exist yet,
  // and to show the "right now" snapshot on the dashboard.
  app.get("/api/live", async (_req, res) => {
    const results: Record<string, unknown> = {};
    const errors: Record<string, string> = {};

    await Promise.all(NEM_REGIONS.map(async (region) => {
      const cached = liveCache.get(region);
      if (cached && Date.now() - cached.fetchedAt < LIVE_TTL_MS) {
        results[region] = cached.data;
        return;
      }
      try {
        const raw = await fetchLive(region);
        const parsed = parseFreePayload(raw, region);
        liveCache.set(region, { data: parsed, fetchedAt: Date.now() });
        results[region] = parsed;
      } catch (e: any) {
        errors[region] = e.message;
        results[region] = null;
      }
    }));

    res.json({
      fetchedAt: new Date().toISOString(),
      source: "live_7d_free",
      regions: results,
      errors: Object.keys(errors).length ? errors : undefined,
    });
  });

  // ── GET /api/status — health check + view freshness ───────────────────────
  app.get("/api/status", (_req, res) => {
    const views: Record<string, { exists: boolean; age_seconds: number | null }> = {};
    for (const v of VALID_VIEWS) {
      const age = viewFileAge(v);
      views[v] = { exists: age !== null, age_seconds: age !== null ? Math.floor(age / 1000) : null };
    }
    const lastUpdated = readViewFile("last_updated") as any;
    res.json({
      status: "ok",
      has_ledger_data: views["summary"].exists,
      last_materialized: lastUpdated?.materialized_at ?? null,
      first_date: lastUpdated?.first_date ?? null,
      last_date: lastUpdated?.last_date ?? null,
      total_events: lastUpdated?.total_events ?? null,
      views,
    });
  });
}
