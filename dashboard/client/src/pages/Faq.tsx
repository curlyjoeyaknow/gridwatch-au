import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HelpCircle, ExternalLink } from "lucide-react";

const FAQS = [
  {
    section: "About GridWatch",
    items: [
      {
        q: "What is GridWatch AU?",
        a: "GridWatch AU is a Computer Science project that fetches live electricity generation, emissions, and price data from Australia's National Electricity Market (NEM) and presents it in an interactive dashboard. It was built to showcase UN SDG 7 (Affordable and Clean Energy) and SDG 13 (Climate Action) using real government-linked data."
      },
      {
        q: "What regions does it cover?",
        a: "GridWatch covers the five NEM regions: NSW1 (New South Wales), QLD1 (Queensland), VIC1 (Victoria), SA1 (South Australia), and TAS1 (Tasmania). Western Australia (SWIS) and the Northern Territory are not part of the NEM and are out of scope by design — they operate separate electricity grids."
      },
      {
        q: "How often is the data updated?",
        a: "The underlying OpenElectricity API provides 5-minute interval data for the past 7 days. GridWatch caches each region's payload for 15 minutes to avoid hammering the API. You can manually trigger a refresh using the 'Refresh live data' button in the sidebar."
      },
    ]
  },
  {
    section: "The Data",
    items: [
      {
        q: "Where does the data come from?",
        a: "Data comes from the OpenElectricity v4 API (data.openelectricity.org.au), which aggregates AEMO's (Australian Energy Market Operator) dispatch data. It's free and requires no API key. The raw API endpoint is: data.openelectricity.org.au/v4/stats/au/NEM/{REGION}/power/7d.json"
      },
      {
        q: "What does 'renewable %' mean exactly?",
        a: "Renewable share = renewable generation (MWh) ÷ total dispatchable generation (MWh) × 100. 'Dispatchable generation' counts solar, wind, hydro, bioenergy, coal, gas, and distillate. Battery storage, pumped hydro, imports/exports, and curtailment are excluded from both numerator and denominator — they would distort the calculation since they don't generate new energy, they store or move it."
      },
      {
        q: "What fuel types are classified as renewable?",
        a: "Renewable fuels: solar (utility and rooftop), wind, hydro, and bioenergy (biomass and biogas). Non-renewable: coal (black and brown), gas (CCGT, OCGT, recip, steam, waste coal mine gas), and distillate. Battery and pumped storage are tracked separately and excluded from the renewable share calculation."
      },
      {
        q: "Why do prices sometimes go negative?",
        a: "In the NEM, spot prices can go negative when there's more generation than demand — typically on sunny, windy days when solar and wind flood the grid. Generators with high shutdown costs (like coal) may pay to keep running rather than incur restart costs. South Australia experiences this most frequently due to its high renewable penetration."
      },
      {
        q: "What is emissions intensity?",
        a: "Emissions intensity = total emissions (tCO₂e) ÷ total generation (MWh). It measures how much CO₂-equivalent is emitted per unit of electricity generated. Lower is better. Tasmania has near-zero intensity (almost all hydro), while Victoria has the highest (large brown coal fleet)."
      },
    ]
  },
  {
    section: "Technical",
    items: [
      {
        q: "How is the backend built?",
        a: "The Python backend uses a hexagonal (ports-and-adapters) architecture with a pure domain core. Key modules: contracts/ (Reading types, fuel taxonomy, RegionSummary), domain/ (analytics, aggregation, Region aggregate), adapters/ (OpenElectricity API, CSV, JSON, SQLite, JSONL ledger), and a Flask web layer. The frontend is React + TypeScript + Recharts."
      },
      {
        q: "Can I download the raw data?",
        a: "Yes — go to the Data page, apply any filters you want, then click 'Export CSV'. This exports all readings matching your current filter (region, metric, fuel type, etc.) as a standard CSV file with columns: region, timestamp, metric, fuel_tech, fuel_category, is_renewable, value, unit, interval_minutes, energy_mwh."
      },
      {
        q: "Why only 7 days of data?",
        a: "The free OpenElectricity API endpoint provides 7 days of 5-minute data. Each region returns ~30 time series × 2,016 data points = ~60,000 readings. For all 5 NEM regions that's ~300,000 readings in the browser. Extending to longer periods would require the paid API tier or building a local data ledger (the Python backend supports JSONL and Parquet append-only ledgers for this)."
      },
    ]
  },
];

export default function FaqPage() {
  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold tracking-tight">FAQ</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Everything about GridWatch AU, the data, and how it works
        </p>
      </div>

      <div className="space-y-5">
        {FAQS.map(section => (
          <div key={section.section}>
            <div className="flex items-center gap-2 mb-3">
              <HelpCircle className="w-4 h-4 text-emerald-600" />
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">{section.section}</h2>
            </div>
            <Card>
              <CardContent className="p-0">
                <Accordion type="multiple" className="w-full">
                  {section.items.map((item, i) => (
                    <AccordionItem key={i} value={`${section.section}-${i}`} className="border-b last:border-0">
                      <AccordionTrigger className="px-5 py-3.5 text-sm font-medium hover:no-underline hover:bg-muted/30 text-left">
                        {item.q}
                      </AccordionTrigger>
                      <AccordionContent className="px-5 pb-4 pt-0 text-sm text-muted-foreground leading-relaxed">
                        {item.a}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              </CardContent>
            </Card>
          </div>
        ))}
      </div>

      {/* Links */}
      <Card className="bg-emerald-50 border-emerald-200">
        <CardContent className="pt-4 pb-3 space-y-2">
          <div className="text-xs font-semibold text-emerald-800 mb-2">Useful links</div>
          {[
            { label: "OpenElectricity", url: "https://openelectricity.org.au", desc: "Live NEM data source" },
            { label: "AEMO", url: "https://aemo.com.au", desc: "Australian Energy Market Operator" },
            { label: "UN SDG 7", url: "https://sdgs.un.org/goals/goal7", desc: "Affordable and Clean Energy" },
            { label: "GitHub Repo", url: "https://github.com/curlyjoeyaknow/gridwatch-au", desc: "Full source code" },
          ].map(link => (
            <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center justify-between text-xs text-emerald-700 hover:text-emerald-900 transition-colors group">
              <span className="flex items-center gap-1.5">
                <ExternalLink className="w-3 h-3" />
                <span className="font-medium">{link.label}</span>
                <span className="text-emerald-600/70">— {link.desc}</span>
              </span>
            </a>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
