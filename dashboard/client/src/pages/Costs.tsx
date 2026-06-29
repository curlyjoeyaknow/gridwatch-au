import { useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer, ReferenceLine, Legend
} from "recharts";
import { DollarSign, TrendingUp, TrendingDown, Activity, Database, Wifi } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useGrain, useSummary, useLastUpdated } from "@/hooks/useViews";
import {
  NEM_REGIONS, REGION_NAMES, REGION_SHORT, STATE_COLORS, FUEL_META,
  fmt, fmtPrice, fmtMWh, fmtPct, formatPeriod,
  flattenRegion, nationalAggregate,
  type Grain, type RegionCode, type PeriodRow
} from "@/lib/views";

type RegionFilter = "national" | RegionCode;

const GRAIN_LABELS: Record<Grain, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  yearly: "Yearly",
};

const PriceTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs max-w-[200px]">
      <div className="font-semibold mb-1.5">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center justify-between gap-3 py-0.5">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: p.stroke ?? p.fill ?? p.color }} />
            <span className="text-muted-foreground">{p.name}</span>
          </span>
          <span className="font-medium num">{fmtPrice(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

function KpiCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string; sub?: string; icon?: any; color?: string;
}) {
  const c = color ?? "#10b981";
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-4 pb-3">
        <div className="p-2 rounded-lg flex-shrink-0" style={{ background: `${c}18` }}>
          {Icon
            ? <Icon className="w-4 h-4" style={{ color: c }} />
            : <div className="w-4 h-4 rounded-full" style={{ background: c }} />
          }
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

export default function Costs() {
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

  const sliceLimits: Record<Grain, number> = { daily: 90, weekly: 104, monthly: 60, yearly: 9999 };
  const displayRows = rows.slice(-sliceLimits[grain]);

  const tickFmt = (val: string) => formatPeriod(val, grain);

  // KPIs
  const priceRows = rows.filter(r => r.avg_price !== null);
  const avgPrice = priceRows.length
    ? priceRows.reduce((s, r) => s + (r.avg_price ?? 0), 0) / priceRows.length
    : null;
  const peakPrice = rows.reduce((s, r) => Math.max(s, r.peak_price ?? s), -Infinity);
  const minPrice = rows.reduce((s, r) => Math.min(s, r.min_price ?? s), Infinity);
  const negPricePct = rows.filter(r => (r.min_price ?? 0) < 0).length / Math.max(rows.length, 1) * 100;

  // Multi-region price comparison for national view
  const allRegionPriceRows = (() => {
    if (!view || regionFilter !== "national") return [];
    const periods = view.periods ?? [];
    return periods.map(p => {
      const row: any = { period: p };
      for (const r of NEM_REGIONS) {
        const match = (view.regions?.[r] ?? []).find((x: PeriodRow) => x.period === p);
        row[r] = match?.avg_price ?? null;
      }
      return row;
    }).slice(-sliceLimits[grain]);
  })();

  if (isLoading) return (
    <div className="p-6 space-y-5">
      <Skeleton className="h-7 w-48" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20" />)}
      </div>
      <Skeleton className="h-72" />
    </div>
  );

  return (
    <div className="p-6 space-y-5" data-testid="costs-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Electricity Costs</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Wholesale price trends — NEM spot market ($/MWh)</p>
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
              <SelectItem value="national">National (avg)</SelectItem>
              {NEM_REGIONS.map(code => (
                <SelectItem key={code} value={code}>{code} — {REGION_NAMES[code]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Avg Wholesale Price" value={fmtPrice(avgPrice)} icon={DollarSign} color="#10b981"
          sub={`${GRAIN_LABELS[grain]} avg`} />
        <KpiCard label="Peak Price" value={peakPrice > -Infinity ? fmtPrice(peakPrice) : "—"} icon={TrendingUp} color="#ef4444"
          sub="highest period" />
        <KpiCard label="Min Price" value={minPrice < Infinity ? fmtPrice(minPrice) : "—"} icon={TrendingDown} color="#3b82f6"
          sub="lowest period" />
        <KpiCard label="Negative Price %" value={fmtPct(negPricePct)} icon={Activity} color="#8b5cf6"
          sub="periods with min < $0" />
      </div>

      {/* Price time series */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold">
            Avg Wholesale Price ($/MWh)
            <span className="text-muted-foreground font-normal text-xs ml-2">
              {regionFilter === "national" ? "NEM National" : `${regionFilter} — ${REGION_NAMES[regionFilter as RegionCode]}`}
              {" · "}{GRAIN_LABELS[grain]}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {displayRows.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
              No data — run <code className="bg-muted px-1 rounded text-xs mx-1">backfill.py</code> to build history
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={displayRows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${v}`} width={46} />
                <Tooltip content={<PriceTooltip />} />
                <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1} />
                <Line type="monotone" dataKey="avg_price" name="Avg Price"
                  stroke="#10b981" strokeWidth={2} dot={false} connectNulls />
                <Line type="monotone" dataKey="peak_price" name="Peak Price"
                  stroke="#ef4444" strokeWidth={1.5} dot={false} strokeDasharray="4 2" connectNulls />
                <Line type="monotone" dataKey="min_price" name="Min Price"
                  stroke="#3b82f6" strokeWidth={1.5} dot={false} strokeDasharray="4 2" connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* All regions price comparison */}
      {regionFilter === "national" && allRegionPriceRows.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">
              Price by Region
              <span className="text-muted-foreground font-normal text-xs ml-2">{GRAIN_LABELS[grain]}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={allRegionPriceRows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${v}`} width={46} />
                <Tooltip content={<PriceTooltip />} />
                <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                {NEM_REGIONS.map(code => (
                  <Line key={code} type="monotone" dataKey={code} name={code}
                    stroke={STATE_COLORS[code]} strokeWidth={1.5} dot={false} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Price vs Renewable share scatter (bar comparison) */}
      {rows.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">
              Price Distribution
              <span className="text-muted-foreground font-normal text-xs ml-2">avg vs peak vs min per period</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={displayRows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period" tickFormatter={tickFmt} tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${v}`} width={46} />
                <Tooltip content={<PriceTooltip />} />
                <Legend iconSize={9} wrapperStyle={{ fontSize: 10 }} />
                <Bar dataKey="peak_price" name="Peak" fill="#ef4444" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
                <Bar dataKey="avg_price" name="Avg" fill="#10b981" fillOpacity={0.85} radius={[2, 2, 0, 0]} />
                <Bar dataKey="min_price" name="Min" fill="#3b82f6" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* State comparison table */}
      {summaries?.length ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">State Price Comparison — Full Ledger</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    {["Region", "Avg Price", "Peak Price", "Min Price", "Renewable %"].map(h => (
                      <th key={h}
                        className={`px-4 py-2.5 text-xs font-medium text-muted-foreground ${h === "Region" ? "text-left" : "text-right"}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {summaries.map(s => (
                    <tr key={s.region} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-2.5">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full"
                            style={{ background: STATE_COLORS[s.region as RegionCode] ?? "#94a3b8" }} />
                          <span className="font-medium">{s.region}</span>
                          <span className="text-muted-foreground text-xs hidden sm:inline">
                            {REGION_NAMES[s.region as RegionCode]}
                          </span>
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right num font-semibold text-emerald-600">{fmtPrice(s.avg_price)}</td>
                      <td className="px-4 py-2.5 text-right num text-red-500">{fmtPrice(s.peak_price)}</td>
                      <td className="px-4 py-2.5 text-right num text-blue-500">{fmtPrice(s.min_price)}</td>
                      <td className="px-4 py-2.5 text-right num">{fmtPct(s.renewable_share_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
