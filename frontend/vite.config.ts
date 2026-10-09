import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the API runs on its own port; the dev server forwards /api to it, so the app
// always calls the same relative paths as in production (where nginx does the forwarding).
const API_URL = process.env.API_URL ?? "http://localhost:5000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": { target: API_URL, rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
  test: { environment: "node" },
});
