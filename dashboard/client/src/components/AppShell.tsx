import { useState } from "react";
import { Link, useLocation } from "wouter";
import {
  LayoutDashboard, Zap, DollarSign, TrendingUp, Table2,
  BookOpen, HelpCircle, Menu, X, ExternalLink, RefreshCw
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, desc: "NEM overview & renewable %" },
  { href: "/usage", label: "Usage", icon: Zap, desc: "Generation by period & state" },
  { href: "/costs", label: "Costs", icon: DollarSign, desc: "Electricity price trends" },
  { href: "/trends", label: "Trends", icon: TrendingUp, desc: "Multi-region comparison" },
  { href: "/data", label: "Data", icon: Table2, desc: "Raw readings + CSV export" },
  { href: "/blog", label: "Blog", icon: BookOpen, desc: "Project write-up & insights" },
  { href: "/faq", label: "FAQ", icon: HelpCircle, desc: "About GridWatch & the data" },
];

function Logo() {
  return (
    <svg aria-label="GridWatch Australia" viewBox="0 0 32 32" width="28" height="28" fill="none">
      {/* Grid lines */}
      <rect x="2" y="2" width="28" height="28" rx="4" stroke="currentColor" strokeWidth="1.5" opacity="0.25"/>
      {/* Lightning bolt */}
      <path d="M18 4L10 18h7l-3 10 12-14h-7l3-10z" fill="currentColor" opacity="0.9"/>
      {/* Green dot accent */}
      <circle cx="26" cy="6" r="3" fill="#10b981"/>
    </svg>
  );
}

interface AppShellProps { children: React.ReactNode; }

export default function AppShell({ children }: AppShellProps) {
  const [location] = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const qc = useQueryClient();
  const { toast } = useToast();

  function handleRefresh() {
    qc.invalidateQueries();
    toast({ title: "Refreshing data…", description: "Fetching latest NEM readings from OpenElectricity." });
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* ── Sidebar (desktop) ── */}
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
        {/* Brand */}
        <div className="flex items-center gap-2.5 px-5 py-4 border-b border-sidebar-border">
          <span className="text-sidebar-primary"><Logo /></span>
          <div className="leading-tight">
            <div className="text-sm font-bold text-white tracking-tight">GridWatch</div>
            <div className="text-[10px] text-sidebar-foreground/60 uppercase tracking-widest">Australia</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href}>
              <a
                data-testid={`nav-${label.toLowerCase()}`}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  location === href
                    ? "bg-sidebar-accent text-white font-semibold"
                    : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-white"
                )}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {label}
              </a>
            </Link>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-sidebar-border space-y-2">
          <Button
            size="sm"
            variant="outline"
            className="w-full text-xs gap-1.5 border-sidebar-border text-sidebar-foreground hover:bg-sidebar-accent"
            onClick={handleRefresh}
            data-testid="btn-refresh"
          >
            <RefreshCw className="w-3 h-3" /> Refresh live data
          </Button>
          <a
            href="https://openelectricity.org.au"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-[10px] text-sidebar-foreground/50 hover:text-sidebar-foreground/80 transition-colors px-1"
          >
            <ExternalLink className="w-2.5 h-2.5" />
            Data: OpenElectricity
          </a>
          <p className="text-[9px] text-sidebar-foreground/35 px-1 leading-tight">
            UN SDG 7 · Computer Science Project
          </p>
        </div>
      </aside>

      {/* ── Mobile overlay sidebar ── */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-56 bg-sidebar text-sidebar-foreground flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-sidebar-border">
              <div className="flex items-center gap-2.5">
                <span className="text-sidebar-primary"><Logo /></span>
                <span className="text-sm font-bold text-white">GridWatch AU</span>
              </div>
              <button onClick={() => setMobileOpen(false)}><X className="w-4 h-4" /></button>
            </div>
            <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
              {NAV.map(({ href, label, icon: Icon }) => (
                <Link key={href} href={href}>
                  <a
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                      location === href
                        ? "bg-sidebar-accent text-white font-semibold"
                        : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-white"
                    )}
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" />
                    {label}
                  </a>
                </Link>
              ))}
            </nav>
          </aside>
        </div>
      )}

      {/* ── Main content ── */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Mobile header */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 border-b bg-sidebar text-white flex-shrink-0">
          <button data-testid="btn-mobile-menu" onClick={() => setMobileOpen(true)}>
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-bold text-sm">GridWatch AU</span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
