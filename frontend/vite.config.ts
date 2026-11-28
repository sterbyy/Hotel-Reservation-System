import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on http://127.0.0.1:8000 by default (see ../README.md).
// Requests to /api and /health are proxied in dev so the browser stays on one origin.
const backend = process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/health": { target: backend, changeOrigin: true },
    },
  },
});
