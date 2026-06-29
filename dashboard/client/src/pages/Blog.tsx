import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Clock, ExternalLink } from "lucide-react";

const POSTS = [
  {
    id: 1,
    tag: "Project Overview",
    tagColor: "bg-emerald-100 text-emerald-800",
    title: "Building GridWatch AU: Tracking Australia's Renewable Energy Transition",
    date: "June 2026",
    readTime: "8 min read",
    excerpt: `GridWatch AU started as a Computer Science project exploring how open government data can be turned into meaningful climate insights. The goal was to use Python to fetch live data from the OpenElectricity API (which aggregates AEMO's 5-minute dispatch data), process it through a clean hexagonal architecture, and then present it in a consumer-ready format — going far beyond basic filtered tables and static matplotlib charts.`,
    body: [
      `The project covers the five NEM (National Electricity Market) regions: NSW1, QLD1, VIC1, SA1, and TAS1. Western Australia and the NT operate separate grids and are out of scope by design.`,
      `The Python backend uses a ports-and-adapters (hexagonal) architecture, with a pure domain core that has no I/O dependencies. This made it easy to build a comprehensive offline test suite using captured API fixtures, and to swap between storage backends (JSON, CSV, SQLite, JSONL ledger, Parquet).`,
      `The key insight is the fuel taxonomy — mapping 20+ raw vendor fuel_tech strings (solar_utility, coal_brown, gas_ccgt, etc.) to a clean set of categories, each tagged as renewable or not. This is what powers all the analytics: renewable share, emissions intensity, and fuel mix breakdowns.`,
    ],
    un_sdg: "SDG 7 — Affordable and Clean Energy",
  },
  {
    id: 2,
    tag: "Data Analysis",
    tagColor: "bg-blue-100 text-blue-800",
    title: "What the Numbers Say: Australia's Renewable Energy State by State",
    date: "June 2026",
    readTime: "5 min read",
    excerpt: `Tasmania runs on almost 100% renewable energy — almost entirely hydro. South Australia regularly hits 60–70% renewable, driven by its massive wind and solar fleet. New South Wales and Victoria, the largest grids, are still heavily coal-dependent but are transitioning rapidly.`,
    body: [
      `Tasmania's hydro dominance makes it a genuine outlier — it's been effectively 100% renewable for decades. The key constraint is interconnection with Victoria via Basslink; SA exports excess renewables, while Tasmania exports clean hydro.`,
      `South Australia is the NEM's renewable energy showcase. After closing its last coal plant in 2016, SA now relies on wind (mainly from the Yorke Peninsula), rooftop solar, and large-scale battery storage (including the world-famous Hornsdale Power Reserve). Negative spot prices — where there's so much solar and wind that generators pay to offload power — occur regularly.`,
      `Queensland's renewable uptake has been slower due to distance and a large coal base, but the state has strong solar irradiance and is building rapidly. Its 2030 target of 80% renewable is ambitious but increasingly credible.`,
      `Victoria has the oldest coal fleet in Australia (Latrobe Valley brown coal), giving it the highest emissions intensity in the NEM. But it's also building wind and solar aggressively, and the Liddell-era retirements are creating space for new capacity.`,
    ],
    un_sdg: "SDG 13 — Climate Action",
  },
  {
    id: 3,
    tag: "Technical Notes",
    tagColor: "bg-purple-100 text-purple-800",
    title: "From Python Domain Model to React Dashboard: Architecture Decisions",
    date: "June 2026",
    readTime: "6 min read",
    excerpt: `The Python backend's domain model translates almost directly to TypeScript. The Reading hierarchy (PowerReading, EmissionReading, PriceReading, DemandReading), the fuel taxonomy, and the analytics functions all port cleanly. Here's how the frontend mirrors the backend structure.`,
    body: [
      `The OpenElectricity v4 API returns 5-minute time-series for each fuel tech and metric. A single region fetch contains ~30 series with 2,000+ data points each — about 60,000 readings per region, or 300,000 for all five NEM regions. Parsing this in the browser is surprisingly fast using modern JS.`,
      `The key analytical functions — renewable_share(), total_generation_mwh(), emissions_intensity() — are pure functions in both the Python backend and the TypeScript frontend. The fuel taxonomy (classify(), isRenewable()) uses the same logic, ensuring the frontend and backend produce identical numbers.`,
      `Aggregation (day/week/month bucketing) is done on the frontend for flexibility. The backend caches the raw API payloads with a 15-minute TTL; all chart computations happen in React. This makes the dashboard feel instant when switching between views.`,
      `Recharts was chosen over Chart.js for its React-native composability — you define charts as JSX, which makes it easy to wire up live state (region toggles, period selectors) without imperative chart updates.`,
    ],
    un_sdg: null,
  },
];

export default function BlogPage() {
  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Blog</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Project write-up, data analysis, and technical notes
        </p>
      </div>

      <div className="space-y-6">
        {POSTS.map(post => (
          <Card key={post.id} className="overflow-hidden hover:shadow-md transition-shadow">
            <CardHeader className="pb-3 bg-gradient-to-r from-muted/60 to-transparent">
              <div className="flex flex-wrap gap-2 items-center mb-2">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${post.tagColor}`}>
                  {post.tag}
                </span>
                {post.un_sdg && (
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                    🌍 {post.un_sdg}
                  </span>
                )}
              </div>
              <h2 className="text-base font-bold leading-snug">{post.title}</h2>
              <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{post.date}</span>
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{post.readTime}</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm leading-relaxed font-medium text-foreground/90">{post.excerpt}</p>
              <div className="space-y-2">
                {post.body.map((para, i) => (
                  <p key={i} className="text-sm text-muted-foreground leading-relaxed">{para}</p>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Data source credit */}
      <Card className="bg-slate-50 border-slate-200">
        <CardContent className="pt-4 pb-3">
          <div className="flex items-start gap-3">
            <ExternalLink className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-slate-600 leading-relaxed">
              <span className="font-semibold">Data source:</span>{" "}
              All electricity data is sourced from the{" "}
              <a href="https://openelectricity.org.au" target="_blank" rel="noopener noreferrer"
                className="underline text-emerald-700 font-medium">
                OpenElectricity API
              </a>{" "}
              (free, no API key required), which aggregates AEMO's 5-minute dispatch data for the NEM.
              The endpoint used is{" "}
              <code className="bg-slate-100 px-1 rounded text-[10px]">
                data.openelectricity.org.au/v4/stats/au/NEM/{"{REGION}"}/power/7d.json
              </code>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
