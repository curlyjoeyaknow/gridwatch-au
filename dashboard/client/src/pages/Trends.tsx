import { useState } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
  Legend, ReferenceLine
} from "recharts";
import { TrendingUp, Leaf, Zap, BarChart2, Database, Wifi } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useGrain, useSummary, useLastUpdated } from "@/hooks/useViews";
import {
  NEM_REGIONS, REGION_NAMES, STATE_COLORS, FUEL_META,
  fmt, fmtPct, fmtMWh, renewableColor,
  flattenRegion, nationalAggregate,
  type Grain, type RegionCode, type PeriodRow, type GrainView
} from "@/lib/views";

const GRAIN_LABELS: Record<Grain, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  yearly: "Yearly",
};

const RenTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs max-w-[200px]">
      <div className="font-semibold mb-1.5">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center justify-between gap-3 py-0.5">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: p.stroke ?? p.color }} />
            <span className="text-muted-foreground">{p.name}</span>
          </span>
          <span className="font-medium num">{fmtPct(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

const EmitTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs">
      <div className="font-semibold mb-1">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-full" style={{ background: p.stroke ?? p.fill ?? p.color }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-medium num">{fmt(p.value, 0)} kt CO₂e</span>
        </div>
      ))}
    </div>
  );
};

function buildAllRegionRows(view: GrainView, field: keyof PeriodRow): any[] {
  const periods = view.periods ?? [];
  return periods.map(p => {
    const row: any = { period: p };
    for (const r of NEM_REGIONS) {
      const match = (view.regions?.[r] ?? []).find((x: PeriodRow) => x.period === p);
      row[r] = match?.[field] ?? null;
    }
    return row;
  });
}

export default function Trends() {
  const [grain, setGrain] = useState<Grain>("monthly");

  const { data: view, isLoading } = useGrain(grain);
  const { data: yearlyView } = useGrain("yearly");
  const { data: summaries } = useSummary();
  const { data: lastUpdated } = useLastUpdated();

  const hasLedger = !!summaries?.length;
  const firstDate = lastUpdated?.first_date ?? summaries?.[0]?.first_date;
  const lastDate = lastUpdated?.last_date ?? summaries?.[0]?.last_date;

  const sliceLimits: Record<Grain, number> = { daily: 90, weekly: 104, monthly: 60, yearly: 9999 };

  const tickFmt = (val: string) => {
    if (!val) return "";
    if (grain === "daily" || grain === "weekly") return val.slice(5);
    if (grain === "monthly") return val.slice(0, 7);
    return val.slice(0, 4);
  };

  // Multi-region renewable share over time
  const renByRegion = view ? buildAllRegionRows(view, "renewable_share_pct").slice(-sliceLimits[grain]) : [];

  // National renewable area (all grains)
  const nationalRen = view
    ? nationalAggregate(view).slice(-sliceLimits[grain]).map(r => ({
        period: r.period,
        pct: Math.round(r.renewable_share_pct * 10) / 10,
      }))
    : [];

  // Emissions trend by region
  const emitByRegion = view ? buildAllRegionRows(view, "total_emissions_tco2e")
    .slice(-sliceLimits[grain])
    .map(row => {
      const out: any = { period: row.period };
      for (const r of NEM_REGIONS) out[r] = row[r] !== null ? Math.round((row[r] ?? 0) / 1000) : null; // kt
      return out;
    }) : [];

  // Yearly renewable share progression (bar chart, anchor to full history)
  const yearlyRen = yearlyView
    ? nationalAggregate(yearlyView).map(r => ({
        period: r.period.slice(0, 4),
        pct: Math.round(r.renewable_share_pct * 10) / 10,
      }))
    : [];

  // Fuel-level trend for solar + wind nationally
  const solarWindTrend = view
    ? nationalAggregate(view).slice(-sliceLimits[grain]).map(r => ({
        period: r.period,
        SOLAR: r.fuel["SOLAR"] ?? 0,
        WIND: r.fuel["WIND"] ?? 0,
      }))
    : [];

  if (isLoading) return (
    <div className="p-6 space-y-5">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-72" />
    </div>
  );

  return (
    <div className="p-6 space-y-5" data-testid="trends-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Renewable Trends</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Long-run trajectory of clean energy across Australia's NEM</p>
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

      {/* Grain selector */}
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

      {/* National renewable area */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
            <Leaf className="w-4 h-4 text-emerald-600" />
            National Renewable Share
            <span className="text-muted-foreground font-normal text-xs ml-1">{GRAIN_LABELS[grain]}</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {nationalRen.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
              No data — run <code className="bg-muted px-1 rounded text-xs mx-1">backfill.py</code> to build history
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={nationalRen} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <defs>
                  <linearGradient id="renGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} unit="%" width={38} />
                <Tooltip formatter={(v: number) => [`${fmt(v, 1)}%`, "Renewable"]} labelFormatter={tickFmt} />
                <ReferenceLine y={50} stroke="#10b981" strokeDasharray="5 3" strokeWidth={1} label={{ value: "50%", position: "right", fontSize: 9, fill: "#10b981" }} />
                <Area type="monotone" dataKey="pct" name="Renewable %" stroke="#10b981" strokeWidth={2}
                  fill="url(#renGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Multi-region renewable % */}
      {renByRegion.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-blue-500" />
              Renewable Share by State
              <span className="text-muted-foreground font-normal text-xs ml-1">{GRAIN_LABELS[grain]}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={renByRegion} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} unit="%" width={38} />
                <Tooltip content={<RenTooltip />} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                {NEM_REGIONS.map(code => (
                  <Line key={code} type="monotone" dataKey={code} name={`${code} — ${REGION_NAMES[code]}`}
                    stroke={STATE_COLORS[code]} strokeWidth={1.5} dot={false} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Yearly renewable bar — long view */}
      {yearlyRen.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
              <BarChart2 className="w-4 h-4 text-violet-500" />
              Renewable Share — Yearly Progression
              <span className="text-muted-foreground font-normal text-xs ml-1">full ledger history</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={yearlyRen} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} unit="%" width={38} />
                <Tooltip formatter={(v: number) => [`${fmt(v, 1)}%`, "Renewable"]} />
                <Bar dataKey="pct" name="Renewable %" radius={[3, 3, 0, 0]}>
                  {yearlyRen.map((d, i) => (
                    <rect key={i} fill={renewableColor(d.pct)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Solar + Wind national trend */}
      {solarWindTrend.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-amber-500" />
              Solar & Wind Generation — National
              <span className="text-muted-foreground font-normal text-xs ml-1">{GRAIN_LABELS[grain]}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={solarWindTrend} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <defs>
                  <linearGradient id="solarGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.05} />
                  </linearGradient>
                  <linearGradient id="windGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tickFormatter={v => fmtMWh(v)} tick={{ fontSize: 10 }} width={54} />
                <Tooltip formatter={(v: number, name: string) => [fmtMWh(v), name]} labelFormatter={tickFmt} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                <Area type="monotone" dataKey="SOLAR" name="Solar" stroke="#f59e0b" strokeWidth={2}
                  fill="url(#solarGrad)" dot={false} />
                <Area type="monotone" dataKey="WIND" name="Wind" stroke="#3b82f6" strokeWidth={2}
                  fill="url(#windGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Emissions trend */}
      {emitByRegion.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">
              Emissions by State (kt CO₂e)
              <span className="text-muted-foreground font-normal text-xs ml-2">{GRAIN_LABELS[grain]}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={emitByRegion} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v}k`} width={40} />
                <Tooltip content={<EmitTooltip />} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                {NEM_REGIONS.map(code => (
                  <Area key={code} type="monotone" dataKey={code} name={code}
                    stroke={STATE_COLORS[code]} fill={STATE_COLORS[code]} fillOpacity={0.2}
                    strokeWidth={1.5} dot={false} connectNulls stackId="e" />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* SDG callout */}
      <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-5 py-4">
        <p className="text-sm text-emerald-800">
          <span className="font-semibold">UN SDG 7 context:</span>{" "}
          Australia's NEM renewable share has grown substantially over the past decade, driven primarily
          by solar PV and wind capacity additions. SA and TAS regularly exceed 50 % renewable generation,
          with NSW and QLD showing strong upward trajectories. The data is sourced from{" "}
          <a href="https://openelectricity.org.au" target="_blank" rel="noopener noreferrer"
            className="underline font-medium">OpenElectricity</a>{" "}
          (AEMO-derived) and processed via a custom DuckDB ETL pipeline.
        </p>
      </div>
    </div>
  );
}
