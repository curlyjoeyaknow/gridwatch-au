import { useState, useMemo } from "react";
import { Search, Download, Database, Wifi, RefreshCw, ChevronUp, ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useRawRecent, useSummary, useLastUpdated } from "@/hooks/useViews";
import { queryClient } from "@/lib/queryClient";
import {
  NEM_REGIONS, REGION_NAMES, STATE_COLORS, FUEL_META,
  fmt,
  type RegionCode, type RawRow
} from "@/lib/views";

type SortKey = "timestamp" | "region" | "fuel_tech" | "value";
type SortDir = "asc" | "desc";

function downloadCsv(rows: RawRow[], filename: string) {
  const header = ["timestamp", "region", "metric", "fuel_tech", "value", "unit", "interval_minutes"];
  const lines = [header.join(","), ...rows.map(r =>
    [r.timestamp, r.region, r.metric, r.fuel_tech ?? "", r.value, r.unit, r.interval_minutes].join(",")
  )];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export default function DataTable() {
  const [search, setSearch] = useState("");
  const [regionFilter, setRegionFilter] = useState<string>("all");
  const [fuelFilter, setFuelFilter] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 100;

  const { data: recent, isLoading, refetch } = useRawRecent();
  const { data: summaries } = useSummary();
  const { data: lastUpdated } = useLastUpdated();

  const hasLedger = !!summaries?.length;
  const rows = recent?.rows ?? [];

  // Unique fuel techs in data
  const allFuelTechs = useMemo(() => {
    const s = new Set(rows.map(r => r.fuel_tech).filter(Boolean) as string[]);
    return ["all", ...Array.from(s).sort()];
  }, [rows]);

  // Filter + sort
  const filtered = useMemo(() => {
    let r = rows;
    if (regionFilter !== "all") r = r.filter(x => x.region === regionFilter);
    if (fuelFilter !== "all") r = r.filter(x => x.fuel_tech === fuelFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      r = r.filter(x =>
        x.region.toLowerCase().includes(q) ||
        (x.fuel_tech ?? "").toLowerCase().includes(q) ||
        x.timestamp.includes(q)
      );
    }
    r = [...r].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "timestamp") cmp = a.timestamp.localeCompare(b.timestamp);
      else if (sortKey === "region") cmp = a.region.localeCompare(b.region);
      else if (sortKey === "fuel_tech") cmp = (a.fuel_tech ?? "").localeCompare(b.fuel_tech ?? "");
      else if (sortKey === "value") cmp = a.value - b.value;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return r;
  }, [rows, regionFilter, fuelFilter, search, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
    setPage(1);
  };

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <ChevronUp className="w-3 h-3 opacity-20" />;
    return sortDir === "asc"
      ? <ChevronUp className="w-3 h-3 text-emerald-600" />
      : <ChevronDown className="w-3 h-3 text-emerald-600" />;
  };

  if (isLoading) return (
    <div className="p-6 space-y-5">
      <Skeleton className="h-7 w-48" />
      <div className="flex gap-3">
        <Skeleton className="h-9 flex-1" />
        <Skeleton className="h-9 w-36" />
      </div>
      <Skeleton className="h-96" />
    </div>
  );

  return (
    <div className="p-6 space-y-5" data-testid="data-table-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Raw Data</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Recent readings — last 8 days ({recent?.count?.toLocaleString() ?? 0} total rows in ledger window)
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {hasLedger ? (
            <Badge variant="outline" className="text-xs gap-1.5">
              <Database className="w-3 h-3" />
              Ledger: {lastUpdated?.total_events?.toLocaleString()} events
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
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <Input
            placeholder="Search region, fuel, timestamp…"
            className="pl-8 h-9 text-sm"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            data-testid="search-input"
          />
        </div>
        <Select value={regionFilter} onValueChange={v => { setRegionFilter(v); setPage(1); }}>
          <SelectTrigger className="h-9 text-sm w-36" data-testid="filter-region">
            <SelectValue placeholder="Region" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All regions</SelectItem>
            {NEM_REGIONS.map(code => (
              <SelectItem key={code} value={code}>{code}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={fuelFilter} onValueChange={v => { setFuelFilter(v); setPage(1); }}>
          <SelectTrigger className="h-9 text-sm w-36" data-testid="filter-fuel">
            <SelectValue placeholder="Fuel" />
          </SelectTrigger>
          <SelectContent>
            {allFuelTechs.map(f => (
              <SelectItem key={f} value={f}>{f === "all" ? "All fuels" : (FUEL_META[f.toUpperCase()]?.label ?? f)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" className="h-9 gap-1.5" onClick={() => refetch()} data-testid="btn-refresh">
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </Button>
        <Button variant="outline" size="sm" className="h-9 gap-1.5"
          onClick={() => downloadCsv(filtered, `gridwatch-raw-${new Date().toISOString().slice(0, 10)}.csv`)}
          data-testid="btn-download">
          <Download className="w-3.5 h-3.5" />
          CSV ({filtered.length.toLocaleString()})
        </Button>
      </div>

      {/* Stats row */}
      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span>Showing <strong className="text-foreground">{filtered.length.toLocaleString()}</strong> rows</span>
        <span>·</span>
        <span>Page <strong className="text-foreground">{page}</strong> of {totalPages}</span>
        {(regionFilter !== "all" || fuelFilter !== "all" || search) && (
          <>
            <span>·</span>
            <button className="text-emerald-600 underline" onClick={() => { setRegionFilter("all"); setFuelFilter("all"); setSearch(""); setPage(1); }}>
              Clear filters
            </button>
          </>
        )}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  {([
                    { key: "timestamp" as SortKey, label: "Timestamp", align: "left" },
                    { key: "region" as SortKey,    label: "Region",    align: "left" },
                    { key: "fuel_tech" as SortKey, label: "Fuel",      align: "left" },
                    { key: null,                   label: "Metric",    align: "left" },
                    { key: "value" as SortKey,     label: "Value",     align: "right" },
                    { key: null,                   label: "Unit",      align: "left" },
                    { key: null,                   label: "Interval",  align: "right" },
                  ] as Array<{ key: SortKey | null; label: string; align: string }>).map(col => (
                    <th key={col.label}
                      className={`px-4 py-2.5 text-xs font-medium text-muted-foreground ${col.align === "right" ? "text-right" : "text-left"} ${col.key ? "cursor-pointer select-none hover:text-foreground" : ""}`}
                      onClick={() => col.key && toggleSort(col.key)}
                    >
                      <span className="flex items-center gap-1 justify-start">
                        {col.label}
                        {col.key && <SortIcon k={col.key} />}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {pageRows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground text-sm">
                      {rows.length === 0
                        ? "No recent data — run backfill.py then materialize.py"
                        : "No rows match your filters"}
                    </td>
                  </tr>
                ) : pageRows.map((row, i) => {
                  const fuelKey = (row.fuel_tech ?? "").toUpperCase();
                  const meta = FUEL_META[fuelKey];
                  return (
                    <tr key={i} className="hover:bg-muted/20 transition-colors" data-testid={`row-${i}`}>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground whitespace-nowrap">
                        {row.timestamp.replace("T", " ").slice(0, 19)}
                      </td>
                      <td className="px-4 py-2">
                        <span className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ background: STATE_COLORS[row.region as RegionCode] ?? "#94a3b8" }} />
                          <span className="font-medium">{row.region}</span>
                          <span className="text-muted-foreground text-xs hidden md:inline">
                            {REGION_NAMES[row.region as RegionCode]}
                          </span>
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        {meta ? (
                          <span className="flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
                            <span>{meta.label}</span>
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{row.fuel_tech ?? "—"}</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground text-xs">{row.metric}</td>
                      <td className="px-4 py-2 text-right num font-medium">{fmt(row.value, 1)}</td>
                      <td className="px-4 py-2 text-muted-foreground text-xs">{row.unit}</td>
                      <td className="px-4 py-2 text-right text-muted-foreground text-xs">{row.interval_minutes}m</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(1)} data-testid="page-first">«</Button>
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)} data-testid="page-prev">‹</Button>
          <span className="text-sm text-muted-foreground px-2">Page {page} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)} data-testid="page-next">›</Button>
          <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(totalPages)} data-testid="page-last">»</Button>
        </div>
      )}
    </div>
  );
}
