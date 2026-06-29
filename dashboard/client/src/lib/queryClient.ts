import { QueryClient } from "@tanstack/react-query";

/**
 * URL resolution strategy — works in three environments:
 *
 * 1. Local dev (Express on :5000)
 *    → API_BASE = ""  → fetch("/api/views/summary")
 *
 * 2. Perplexity Computer preview (deploy_website proxy)
 *    → API_BASE = __PORT_5000__ token replaced at deploy time
 *    → fetch("/__port/5000/api/views/summary")
 *
 * 3. GitHub Pages (fully static, no Express)
 *    → VITE_STATIC_DATA_MODE = "true"
 *    → /api/views/:name  →  ./data/views/<name>.json  (relative to page)
 *    → /api/live         →  hits free OE endpoint directly (CORS-friendly)
 *    → /api/status       →  synthesised from last_updated.json
 */

const IS_STATIC = import.meta.env.VITE_STATIC_DATA_MODE === "true";

// __PORT_5000__ is replaced at Perplexity deploy time; falls back to ""
const EXPRESS_BASE: string = (globalThis as any).__PORT_5000__ ?? "";

/**
 * Map an API path to the correct URL for the current environment.
 *
 * Static mode (GitHub Pages):
 *   /api/views/summary   →  ./data/views/summary.json
 *   /api/views/daily     →  ./data/views/daily.json
 *   /api/live            →  null  (caller falls back to cached or empty)
 *   /api/status          →  ./data/views/last_updated.json
 *
 * Express mode:
 *   /api/...             →  {EXPRESS_BASE}/api/...
 */
export function resolveUrl(path: string): string | null {
  if (!IS_STATIC) {
    return `${EXPRESS_BASE}${path}`;
  }

  // /api/views/:name  →  static JSON file
  const viewsMatch = path.match(/^\/api\/views\/(.+)$/);
  if (viewsMatch) {
    const name = viewsMatch[1];
    return `./data/views/${name}.json`;
  }

  // /api/status  →  derive from last_updated.json
  if (path === "/api/status") {
    return `./data/views/last_updated.json`;
  }

  // /api/live  →  not available in static mode
  // Return null; hooks will fall back to empty / live free endpoint
  return null;
}

export async function apiRequest(
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  const url = resolveUrl(path);
  if (!url) {
    // Static mode with no equivalent — return a synthetic empty 503
    return new Response(JSON.stringify({ error: "not available in static mode" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }

  const res = await fetch(url, {
    method: IS_STATIC ? "GET" : method,   // static files are always GET
    headers: body ? { "Content-Type": "application/json" } : {},
    body: !IS_STATIC && body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }
  return res;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: async ({ queryKey }) => {
        const [path] = queryKey as string[];
        const res = await apiRequest("GET", path);
        return res.json();
      },
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});
