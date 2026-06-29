import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * Vite config — works in three modes:
 *
 * 1. Local dev         →  npm run dev           (Express backend on :5000)
 * 2. Express build     →  npm run build         (output: dist/public, served by Express)
 * 3. GitHub Pages      →  npm run build:pages   (output: dist/public, fully static)
 *
 * The only difference for Pages is:
 *   - base is set to "./" (relative) so asset paths work under any repo subpath
 *   - VITE_STATIC_DATA_MODE=true so queryClient.ts serves /data/views/*.json directly
 */
export default defineConfig(({ mode }) => {
  const isPages = process.env.VITE_STATIC_DATA_MODE === "true";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "client", "src"),
        "@shared": path.resolve(import.meta.dirname, "shared"),
        "@assets": path.resolve(import.meta.dirname, "attached_assets"),
      },
    },
    root: path.resolve(import.meta.dirname, "client"),
    // "./" works for both Pages (any subpath) and the Express file server
    base: "./",
    build: {
      outDir: path.resolve(import.meta.dirname, "dist/public"),
      emptyOutDir: true,
    },
    define: {
      // Expose the static mode flag to the frontend bundle
      "import.meta.env.VITE_STATIC_DATA_MODE": JSON.stringify(
        process.env.VITE_STATIC_DATA_MODE ?? ""
      ),
    },
    server: {
      fs: {
        strict: true,
        deny: ["**/.*"],
      },
    },
  };
});
