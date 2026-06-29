import { useQuery } from "@tanstack/react-query";
import type {
  RegionSummary, GrainView, LastUpdated, RawRecent, LiveData, Grain
} from "@/lib/views";

const IS_STATIC = import.meta.env.VITE_STATIC_DATA_MODE === "true";

// ── summary (full ledger KPIs) ────────────────────────────────────────────────
export function useSummary() {
  return useQuery<RegionSummary[]>({
    queryKey: ["/api/views/summary"],
    staleTime: 5 * 60_000,
  });
}

// ── grain views ───────────────────────────────────────────────────────────────
export function useGrain(grain: Grain) {
  return useQuery<GrainView>({
    queryKey: [`/api/views/${grain}`],
    staleTime: 5 * 60_000,
  });
}

// ── last_updated ──────────────────────────────────────────────────────────────
export function useLastUpdated() {
  return useQuery<LastUpdated>({
    queryKey: ["/api/views/last_updated"],
    staleTime: 60_000,
  });
}

// ── raw recent rows (Data page) ───────────────────────────────────────────────
export function useRawRecent() {
  return useQuery<RawRecent>({
    queryKey: ["/api/views/raw_recent"],
    staleTime: 5 * 60_000,
  });
}

// ── live data ─────────────────────────────────────────────────────────────────
// In static (Pages) mode there is no Express proxy to call — the hook returns
// undefined so components fall back to their ledger-view data.
export function useLive() {
  return useQuery<LiveData>({
    queryKey: ["/api/live"],
    staleTime: 10 * 60_000,
    enabled: !IS_STATIC,          // disabled on GitHub Pages
  });
}

// ── status ────────────────────────────────────────────────────────────────────
// In static mode we map /api/status to last_updated.json and synthesise the
// shape the components expect (has_ledger_data, last_materialized, etc.)
export function useStatus() {
  return useQuery<any>({
    queryKey: ["/api/status"],
    staleTime: 30_000,
    // In static mode the default queryFn fetches last_updated.json (via resolveUrl)
    // and we post-process it into the status shape in select.
    select: IS_STATIC
      ? (raw: any) => ({
          status: "ok",
          has_ledger_data: raw?.total_events > 0,
          last_materialized: raw?.materialized_at ?? null,
          first_date: raw?.first_date ?? null,
          last_date: raw?.last_date ?? null,
          total_events: raw?.total_events ?? 0,
        })
      : undefined,
  });
}

// ── Has ledger data? ──────────────────────────────────────────────────────────
export function useHasLedger() {
  const { data } = useStatus();
  return data?.has_ledger_data ?? false;
}
