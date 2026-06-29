import { Switch, Route, Router } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import AppShell from "@/components/AppShell";
import Dashboard from "@/pages/Dashboard";
import UsagePage from "@/pages/Usage";
import CostsPage from "@/pages/Costs";
import TrendsPage from "@/pages/Trends";
import DataPage from "@/pages/DataTable";
import BlogPage from "@/pages/Blog";
import FaqPage from "@/pages/Faq";
import NotFound from "@/pages/not-found";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router hook={useHashLocation}>
        <AppShell>
          <Switch>
            <Route path="/" component={Dashboard} />
            <Route path="/usage" component={UsagePage} />
            <Route path="/costs" component={CostsPage} />
            <Route path="/trends" component={TrendsPage} />
            <Route path="/data" component={DataPage} />
            <Route path="/blog" component={BlogPage} />
            <Route path="/faq" component={FaqPage} />
            <Route component={NotFound} />
          </Switch>
        </AppShell>
      </Router>
      <Toaster />
    </QueryClientProvider>
  );
}
