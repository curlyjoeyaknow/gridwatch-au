import { useQuery } from "@tanstack/react-query";
import { parsePayload, summarise, type RegionCode, type Reading, type RegionSummary, REGION_CODES } from "@/lib/data";

interface RegionApiResult {
  region: RegionCode;
  readings: Reading[];
  summary: RegionSummary;
  fetchedAt: string;
  error?: string;
}

interface AllRegionsResult {
  regions: Record<RegionCode, RegionApiResult | null>;
  allReadings: Reading[];
  summaries: RegionSummary[];
  isLoading: boolean;
  isError: boolean;
  fetchedAt: string | null;
}

export function useAllRegions(): AllRegionsResult {
  const { data, isLoading, isError } = useQuery<any>({
    queryKey: ["/api/regions"],
    staleTime: 10 * 60 * 1000,
  });

  if (!data || isLoading) {
    return { regions: {} as any, allReadings: [], summaries: [], isLoading, isError, fetchedAt: null };
  }

  const regions: Record<RegionCode, RegionApiResult | null> = {} as any;
  const allReadings: Reading[] = [];
  const summaries: RegionSummary[] = [];

  for (const code of REGION_CODES) {
    const payload = data?.regions?.[code];
    if (!payload) {
      regions[code] = null;
      continue;
    }
    try {
      const readings = parsePayload(payload, code);
      const summary = summarise(readings, code);
      regions[code] = { region: code, readings, summary, fetchedAt: data.fetchedAt };
      allReadings.push(...readings);
      summaries.push(summary);
    } catch (e) {
      regions[code] = null;
    }
  }

  return { regions, allReadings, summaries, isLoading: false, isError: false, fetchedAt: data?.fetchedAt ?? null };
}

export function useRegion(code: RegionCode) {
  const { data, isLoading, isError } = useQuery<any>({
    queryKey: [`/api/region/${code}`],
    staleTime: 10 * 60 * 1000,
  });

  if (!data || isLoading) return { readings: [], summary: null, isLoading, isError };

  try {
    const readings = parsePayload(data.data, code);
    const summary = summarise(readings, code);
    return { readings, summary, isLoading: false, isError: false };
  } catch {
    return { readings: [], summary: null, isLoading: false, isError: true };
  }
}
