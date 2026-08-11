import { defineConfig } from "vite";

// The development server proxies API and health requests to the backend so the
// browser issues same-origin calls. This mirrors the production reverse-proxy
// topology and removes any need for cross-origin configuration in development.
const DEV_BACKEND_TARGET = "http://localhost:8000";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": { target: DEV_BACKEND_TARGET, changeOrigin: true },
      "/health": { target: DEV_BACKEND_TARGET, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    target: "es2022",
    sourcemap: false,
  },
});
