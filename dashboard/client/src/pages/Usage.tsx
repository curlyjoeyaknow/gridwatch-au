import { useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, Cell, Legend
} from "recharts";
import { Zap, TrendingUp, Database, Wifi } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useGrain, useSummary, useLastUpdated } from "@/hooks/useViews";
import {
  NEM_REGIONS, REGION_NAMES, REGION_SHORT, STATE_COLORS, FUEL_META,
  fmt, fmtMWh, fmtPct, formatPeriod,
  flattenRegion, nationalAggregate, allFuels,
  type Grain, type RegionCode, type PeriodRow
} from "@/lib/views";

type RegionFilter = "national" | RegionCode;

const GRAIN_LABELS: Record<Grain, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  yearly: "Yearly",
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const sorted = [...payload].sort((a, b) => b.value - a.value);
  const total = sorted.reduce((s: number, p: any) => s + (p.value ?? 0), 0);
  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs max-w-[220px]">
      <div className="font-semibold mb-1.5 text-foreground">{label}</div>
      {sorted.map((p: any, i: number) => (
        <div key={i} className="flex items-center justify-between gap-3 py-0.5">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.fill ?? p.color }} />
            <span className="text-muted-foreground">{p.name}</span>
          </span>
          <span className="font-medium num">{fmtMWh(p.value)}</span>
        </div>
      ))}
      {sorted.length > 1 && (
        <div className="flex items-center justify-between gap-3 border-t mt-1.5 pt-1.5">
          <span className="font-medium">Total</span>
          <span className="font-bold num">{fmtMWh(total)}</span>
        </div>
      )}
    </div>
  );
};

const DemandTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs">
      <div className="font-semibold mb-1">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.fill ?? p.color }} />
          <span>{p.name}: <strong>{fmt(p.value, 0)} MW</strong></span>
        </div>
      ))}
    </div>
  );
};

function buildChartRows(rows: PeriodRow[], fuels: string[]): any[] {
  return rows.map(r => {
    const out: any = { period: r.period, total: r.total_gen_mwh, demand: r.avg_demand_mw ?? 0 };
    for (const f of fuels) out[f] = r.fuel[f] ?? 0;
    return out;
  });
}

function buildRegionDemandRows(rows: PeriodRow[], region: string): any[] {
  return rows.map(r => ({ period: r.period, [region]: r.avg_demand_mw ?? 0 }));
}

function buildAllRegionDemandRows(view: any, regions: string[], fuels: string[]): any[] {
  const periods = view?.periods ?? [];
  return periods.map((p: string) => {
    const row: any = { period: p };
    for (const r of regions) {
      const regionRows: PeriodRow[] = view?.regions?.[r] ?? [];
      const match = regionRows.find((x: PeriodRow) => x.period === p);
      row[r] = match?.avg_demand_mw ?? 0;
    }
    return row;
  });
}

export default function Usage() {
  const [grain, setGrain] = useState<Grain>("monthly");
  const [regionFilter, setRegionFilter] = useState<RegionFilter>("national");

  const { data: view, isLoading } = useGrain(grain);
  const { data: summaries } = useSummary();
  const { data: lastUpdated } = useLastUpdated();

  const hasLedger = !!summaries?.length;
  const firstDate = lastUpdated?.first_date ?? summaries?.[0]?.first_date;
  const lastDate = lastUpdated?.last_date ?? summaries?.[0]?.last_date;

  const rows: PeriodRow[] = view
    ? regionFilter === "national"
      ? nationalAggregate(view)
      : flattenRegion(view, regionFilter)
    : [];

  const fuels = view ? allFuels(view) : [];
  const chartRows = buildChartRows(rows, fuels);

  // For demand chart: per-region bars when national, single region line otherwise
  const demandRows = view
    ? regionFilter === "national"
      ? buildAllRegionDemandRows(view, [...NEM_REGIONS], fuels)
      : rows.map(r => ({ period: r.period, demand: r.avg_demand_mw ?? 0 }))
    : [];

  // Slice for readability (yearly shows all, monthly last 60, weekly last 104, daily last 90)
  const sliceLimits: Record<Grain, number> = { daily: 90, weekly: 104, monthly: 60, yearly: 9999 };
  const displayRows = chartRows.slice(-sliceLimits[grain]);
  const displayDemand = demandRows.slice(-sliceLimits[grain]);

  const tickFmt = (val: string) => formatPeriod(val, grain);

  if (isLoading) return (
    <div className="p-6 space-y-5">
      <Skeleton className="h-7 w-48" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-72" />
    </div>
  );

  // KPIs for current view
  const totalMWh = rows.reduce((s, r) => s + r.total_gen_mwh, 0);
  const avgRen = rows.length ? rows.reduce((s, r) => s + r.renewable_share_pct, 0) / rows.length : 0;
  const peakDemand = rows.reduce((s, r) => Math.max(s, r.peak_demand_mw ?? 0), 0);
  const avgDemand = rows.length
    ? rows.reduce((s, r) => s + (r.avg_demand_mw ?? 0), 0) / rows.length
    : 0;

  return (
    <div className="p-6 space-y-5" data-testid="usage-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Energy Usage</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Generation by fuel type across the NEM</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {hasLedger && firstDate && lastDate ? (
            <Badge variant="outline" className="text-xs gap-1.5">
              <Database className="w-3 h-3" />
              {firstDate} → {lastDate}
            </Badge>
          ) : (
            <Badge variant="outline" className="text-xs gap-1.5 text-amber-600 border-amber-300">
              <Wifi className="w-3 h-3" />
              Live 7d only
            </Badge>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium">Grain</span>
          <Tabs value={grain} onValueChange={v => setGrain(v as Grain)}>
            <TabsList className="h-8">
              {(["daily", "weekly", "monthly", "yearly"] as Grain[]).map(g => (
                <TabsTrigger key={g} value={g} className="text-xs px-2.5 h-7" data-testid={`grain-${g}`}>
                  {GRAIN_LABELS[g]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium">Region</span>
          <Select value={regionFilter} onValueChange={v => setRegionFilter(v as RegionFilter)}>
            <SelectTrigger className="h-8 text-xs w-40" data-testid="region-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="national">National (NEM)</SelectItem>
              {NEM_REGIONS.map(code => (
                <SelectItem key={code} value={code}>{REGION_SHORT[code]} — {REGION_NAMES[code]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Generation", value: fmtMWh(totalMWh), icon: Zap, color: "#3b82f6" },
          { label: "Avg Renewable Share", value: fmtPct(avgRen), icon: null, color: "#10b981" },
          { label: "Avg Demand", value: `${fmt(avgDemand, 0)} MW`, icon: null, color: "#8b5cf6" },
          { label: "Peak Demand", value: `${fmt(peakDemand, 0)} MW`, icon: TrendingUp, color: "#f97316" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-3 pt-4 pb-3">
              <div className="p-2 rounded-lg flex-shrink-0" style={{ background: `${color}18` }}>
                {Icon
                  ? <Icon className="w-4 h-4" style={{ color }} />
                  : <div className="w-4 h-4 rounded-full" style={{ background: color }} />
                }
              </div>
              <div className="min-w-0">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wide truncate">{label}</div>
                <div className="text-base font-bold num leading-tight truncate">{value}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Stacked area: fuel mix */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            Generation by Fuel Type
            <span className="text-muted-foreground font-normal text-xs ml-2">
              {regionFilter === "national" ? "NEM National" : `${REGION_SHORT[regionFilter as RegionCode]} — ${REGION_NAMES[regionFilter as RegionCode]}`}
              {" · "}{GRAIN_LABELS[grain]}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {displayRows.length === 0 ? (
            <div className="h-72 flex items-center justify-center text-sm text-muted-foreground">
              No data — run <code className="bg-muted px-1 rounded text-xs mx-1">backfill.py</code> to build ledger history
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={displayRows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tickFormatter={v => fmtMWh(v)} tick={{ fontSize: 10 }} width={54} />
                <Tooltip content={<CustomTooltip />} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                {fuels.map(fuel => (
                  <Area
                    key={fuel}
                    type="monotone"
                    dataKey={fuel}
                    name={FUEL_META[fuel]?.label ?? fuel}
                    stackId="1"
                    stroke={FUEL_META[fuel]?.color ?? "#94a3b8"}
                    fill={FUEL_META[fuel]?.color ?? "#94a3b8"}
                    fillOpacity={0.75}
                    strokeWidth={1}
                    dot={false}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Demand chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            Average Demand (MW)
            <span className="text-muted-foreground font-normal text-xs ml-2">{GRAIN_LABELS[grain]}</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {displayDemand.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">No demand data</div>
          ) : regionFilter === "national" ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={displayDemand} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tickFormatter={v => `${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10 }} unit=" MW" width={52} />
                <Tooltip content={<DemandTooltip />} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                {NEM_REGIONS.map(code => (
                  <Bar key={code} dataKey={code} name={REGION_SHORT[code]} stackId="d"
                    fill={STATE_COLORS[code]} radius={code === NEM_REGIONS[NEM_REGIONS.length - 1] ? [2, 2, 0, 0] : [0, 0, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={displayDemand} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} unit=" MW" width={52} />
                <Tooltip content={<DemandTooltip />} />
                <Bar dataKey="demand" name="Avg Demand" radius={[3, 3, 0, 0]}
                  fill={STATE_COLORS[regionFilter as RegionCode] ?? "#10b981"} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Renewable breakdown by fuel, stacked bar */}
      {rows.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Renewable Fuel Breakdown — Share of Total Generation</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={displayRows}
                margin={{ top: 4, right: 8, bottom: 4, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} unit="%" domain={[0, 100]} width={36} />
                <Tooltip
                  formatter={(v: number, name: string) => [`${fmt(v, 1)}%`, name]}
                  labelFormatter={tickFmt}
                />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                {(["SOLAR", "WIND", "HYDRO", "BIOENERGY"] as const).filter(f => fuels.includes(f)).map(fuel => {
                  return (
                    <Bar
                      key={fuel}
                      dataKey={(entry: any) => entry.total > 0 ? (entry[fuel] / entry.total) * 100 : 0}
                      name={FUEL_META[fuel]?.label ?? fuel}
                      stackId="r"
                      fill={FUEL_META[fuel]?.color}
                      radius={fuel === "BIOENERGY" ? [2, 2, 0, 0] : [0, 0, 0, 0]}
                    />
                  );
                })}
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
