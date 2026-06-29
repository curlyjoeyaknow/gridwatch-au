import { useState } from "react";
import {
  RadialBarChart, RadialBar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
  PieChart, Pie, Legend, LineChart, Line
} from "recharts";
import { Leaf, Zap, Wind, Activity, Info, Database, Wifi } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useSummary, useLive, useLastUpdated, useGrain } from "@/hooks/useViews";
import {
  NEM_REGIONS, REGION_NAMES, STATE_COLORS, FUEL_META,
  fmt, fmtMWh, fmtPrice, fmtPct, renewableColor,
  nationalAggregate, allFuels,
  type RegionCode, type RegionSummary
} from "@/lib/views";

function RenewableGauge({ pct, label }: { pct: number; label: string }) {
  const color = renewableColor(pct);
  const data = [{ value: pct, fill: color }, { value: 100 - pct, fill: "#e2e8f0" }];
  return (
    <div className="text-center">
      <div className="relative w-24 h-24 mx-auto">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart innerRadius="70%" outerRadius="100%" startAngle={90} endAngle={-270} data={data} barSize={9}>
            <RadialBar dataKey="value" cornerRadius={4} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold num" style={{ color }}>{fmt(pct, 0)}%</span>
        </div>
      </div>
      <div className="text-[11px] text-muted-foreground mt-1 leading-tight">{label}</div>
    </div>
  );
}

function KpiCard({ label, value, icon: Icon, sub, color }: {
  label: string; value: string; icon: any; sub?: string; color?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-4 pb-3">
        <div className="p-2 rounded-lg flex-shrink-0" style={{ background: color ? `${color}18` : "#10b98118" }}>
          <Icon className="w-4 h-4" style={{ color: color ?? "#10b981" }} />
        </div>
        <div className="min-w-0">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wide truncate">{label}</div>
          <div className="text-base font-bold num leading-tight truncate">{value}</div>
          {sub && <div className="text-[10px] text-muted-foreground truncate">{sub}</div>}
        </div>
      </CardContent>
    </Card>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs max-w-[200px]">
      <div className="font-semibold mb-1">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.fill ?? p.color }} />
          <span>{p.name}: <strong>{typeof p.value === "number" ? fmt(p.value, 1) : p.value}</strong></span>
        </div>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const { data: summaries, isLoading: sumLoading } = useSummary();
  const { data: live, isLoading: liveLoading } = useLive();
  const { data: lastUpdated } = useLastUpdated();
  const { data: monthlyView } = useGrain("monthly");
  const [fuelRegion, setFuelRegion] = useState<"national" | RegionCode>("national");

  const isLoading = sumLoading || liveLoading;

  // Use ledger summaries if available, otherwise fall back to live 7d data
  const displaySummaries: RegionSummary[] = summaries?.length
    ? summaries
    : live?.regions
      ? Object.values(live.regions).filter(Boolean) as RegionSummary[]
      : [];

  const hasLedger = !!summaries?.length;
  const dataSource = hasLedger ? "ledger" : "live_7d";

  // Aggregate national
  const totalGen = displaySummaries.reduce((s, r) => s + r.total_generation_mwh, 0);
  const totalRen = displaySummaries.reduce((s, r) => s + r.renewable_generation_mwh, 0);
  const nationalPct = totalGen > 0 ? (totalRen / totalGen) * 100 : 0;
  const totalEmit = displaySummaries.reduce((s, r) => s + r.total_emissions_tco2e, 0);
  const prices = displaySummaries.map(r => r.avg_price).filter((p): p is number => p !== null);
  const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;

  // Date range badge
  const firstDate = lastUpdated?.first_date ?? summaries?.[0]?.first_date;
  const lastDate  = lastUpdated?.last_date  ?? summaries?.[0]?.last_date;

  // Bar chart: renewable % by region
  const barData = NEM_REGIONS.map(code => {
    const s = displaySummaries.find(x => x.region === code);
    return { region: code, pct: s?.renewable_share_pct ?? 0 };
  });

  // Fuel mix pie for selected view
  const fuelMixSrc = fuelRegion === "national" ? displaySummaries : displaySummaries.filter(s => s.region === fuelRegion);
  const fuelMixData = (() => {
    const totals: Record<string, number> = {};
    for (const s of fuelMixSrc) {
      for (const [cat, mwh] of Object.entries(s.by_category_mwh ?? {})) {
        totals[cat] = (totals[cat] ?? 0) + mwh;
      }
    }
    return Object.entries(totals)
      .filter(([, v]) => v > 100)
      .map(([cat, v]) => ({
        name: FUEL_META[cat]?.label ?? cat,
        value: Math.round(v),
        color: FUEL_META[cat]?.color ?? "#94a3b8",
      }))
      .sort((a, b) => b.value - a.value);
  })();

  // Monthly renewable trend (last 24 months)
  const monthlyTrendData = (() => {
    if (!monthlyView) return [];
    const natRows = nationalAggregate(monthlyView).slice(-24);
    return natRows.map(r => ({ period: r.period, pct: Math.round(r.renewable_share_pct * 10) / 10 }));
  })();

  if (isLoading) return (
    <div className="p-6 space-y-5">
      <Skeleton className="h-7 w-56" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-64" />
    </div>
  );

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight">NEM Overview</h1>
          <p className="text-sm text-muted-foreground mt-0.5">National Electricity Market — Australia</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {hasLedger && firstDate && lastDate ? (
            <Badge variant="outline" className="text-xs gap-1.5">
              <Database className="w-3 h-3" />
              {firstDate} → {lastDate}
              <span className="text-muted-foreground">({lastUpdated?.total_events?.toLocaleString()} events)</span>
            </Badge>
          ) : (
            <Badge variant="outline" className="text-xs gap-1.5 text-amber-600 border-amber-300">
              <Wifi className="w-3 h-3" />
              Live 7d only — run backfill.py for history
            </Badge>
          )}
        </div>
      </div>

      {/* National KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="National Renewable %" value={fmtPct(nationalPct)} icon={Leaf} color="#10b981"
          sub={`${fmtMWh(totalRen)} of ${fmtMWh(totalGen)}`} />
        <KpiCard label="Total Generation" value={fmtMWh(totalGen)} icon={Zap} color="#3b82f6"
          sub={hasLedger ? `${lastUpdated?.days_covered ?? "?"} days of data` : "last 7 days"} />
        <KpiCard label="Total Emissions" value={`${fmt(totalEmit / 1000, 1)}k tCO₂e`} icon={Wind} color="#f97316"
          sub="dispatchable generation" />
        <KpiCard label="Avg Wholesale Price" value={fmtPrice(avgPrice)} icon={Activity} color="#8b5cf6"
          sub="NEM average" />
      </div>

      {/* State gauges + national */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Leaf className="w-4 h-4 text-emerald-600" />
            Renewable Share by State
            {hasLedger && <span className="text-muted-foreground font-normal text-xs">— full ledger period</span>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {NEM_REGIONS.map(code => {
              const s = displaySummaries.find(x => x.region === code);
              return (
                <RenewableGauge key={code}
                  pct={s?.renewable_share_pct ?? 0}
                  label={`${code}\n${REGION_NAMES[code]}`} />
              );
            })}
            <RenewableGauge pct={nationalPct} label="NEM\nNational" />
          </div>
        </CardContent>
      </Card>

      {/* Bar + Fuel mix */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Renewable % by Region</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="region" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} unit="%" width={36} />
                <Tooltip content={<CustomTooltip />} formatter={(v: number) => [`${fmt(v, 1)}%`, "Renewable"]} />
                <Bar dataKey="pct" name="Renewable %" radius={[4, 4, 0, 0]}>
                  {barData.map(d => <Cell key={d.region} fill={STATE_COLORS[d.region as RegionCode]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <CardTitle className="text-sm font-semibold">Fuel Mix (MWh)</CardTitle>
              <Tabs value={fuelRegion} onValueChange={(v) => setFuelRegion(v as any)}>
                <TabsList className="h-7">
                  <TabsTrigger value="national" className="text-[10px] px-2 h-6">All</TabsTrigger>
                  {NEM_REGIONS.map(c => (
                    <TabsTrigger key={c} value={c} className="text-[10px] px-1.5 h-6">{c.replace("1", "")}</TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            </div>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={fuelMixData} dataKey="value" nameKey="name" cx="42%" cy="50%"
                  innerRadius={50} outerRadius={80} paddingAngle={2}>
                  {fuelMixData.map((e, i) => <Cell key={i} fill={e.color} />)}
                </Pie>
                <Tooltip formatter={(v: number) => [fmtMWh(v), ""]} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Monthly renewable trend */}
      {monthlyTrendData.length > 2 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">
              National Renewable Share — Monthly Trend
              <span className="text-muted-foreground font-normal text-xs ml-2">last 24 months</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={monthlyTrendData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} unit="%" width={36} />
                <Tooltip formatter={(v: number) => [`${fmt(v, 1)}%`, "Renewable"]} />
                <Line type="monotone" dataKey="pct" stroke="#10b981" strokeWidth={2} dot={false} name="Renewable %" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Summary table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">State Summary</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  {["Region", "Renewable %", "Total Gen", "Emissions", "Intensity", "Avg Price", "Period"].map(h => (
                    <th key={h} className={`px-4 py-2.5 text-xs font-medium text-muted-foreground ${h === "Region" ? "text-left" : "text-right"} ${["Emissions","Intensity","Period"].includes(h) ? "hidden md:table-cell" : ""}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {NEM_REGIONS.map(code => {
                  const s = displaySummaries.find(x => x.region === code);
                  if (!s) return (
                    <tr key={code}><td colSpan={7} className="px-4 py-3 text-muted-foreground text-xs">{code} — loading</td></tr>
                  );
                  const color = renewableColor(s.renewable_share_pct);
                  return (
                    <tr key={code} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-2.5">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full" style={{ background: STATE_COLORS[code] }} />
                          <span className="font-medium">{code}</span>
                          <span className="text-muted-foreground text-xs hidden sm:inline">{REGION_NAMES[code]}</span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right num font-semibold" style={{ color }}>{fmtPct(s.renewable_share_pct)}</td>
                      <td className="px-4 py-2.5 text-right num text-muted-foreground">{fmtMWh(s.total_generation_mwh)}</td>
                      <td className="px-4 py-2.5 text-right num text-muted-foreground hidden md:table-cell">{fmt(s.total_emissions_tco2e / 1000, 1)}k tCO₂e</td>
                      <td className="px-4 py-2.5 text-right num text-muted-foreground hidden md:table-cell">{fmt(s.emissions_intensity, 3)}</td>
                      <td className="px-4 py-2.5 text-right num">{fmtPrice(s.avg_price)}</td>
                      <td className="px-4 py-2.5 text-right text-xs text-muted-foreground hidden md:table-cell">
                        {s.first_date && s.last_date ? `${s.first_date} → ${s.last_date}` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="border-t bg-muted/20">
                  <td className="px-4 py-2.5 font-semibold text-xs">NEM Total</td>
                  <td className="px-4 py-2.5 text-right num font-bold text-emerald-600">{fmtPct(nationalPct)}</td>
                  <td className="px-4 py-2.5 text-right num font-semibold">{fmtMWh(totalGen)}</td>
                  <td className="px-4 py-2.5 text-right num hidden md:table-cell">{fmt(totalEmit / 1000, 1)}k tCO₂e</td>
                  <td className="px-4 py-2.5 text-right num hidden md:table-cell">{totalGen > 0 ? fmt(totalEmit / totalGen, 3) : "—"}</td>
                  <td className="px-4 py-2.5 text-right num">{fmtPrice(avgPrice)}</td>
                  <td className="px-4 py-2.5 hidden md:table-cell" />
                </tr>
              </tfoot>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* SDG callout */}
      <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-5 py-4 flex gap-3">
        <Info className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-emerald-800">
          <span className="font-semibold">UN SDG 7 — Affordable and Clean Energy:</span>{" "}
          GridWatch tracks renewable energy penetration across Australia's NEM using{" "}
          <a href="https://openelectricity.org.au" target="_blank" rel="noopener noreferrer" className="underline font-medium">OpenElectricity</a>{" "}
          data sourced from AEMO. Historical depth is built by running{" "}
          <code className="bg-emerald-100 px-1 rounded text-xs">backfill.py</code> which appends
          daily-interval data to a Parquet ledger, then{" "}
          <code className="bg-emerald-100 px-1 rounded text-xs">materialize.py</code> (DuckDB) produces
          pre-aggregated views for instant chart rendering.
        </p>
      </div>
    </div>
  );
}
