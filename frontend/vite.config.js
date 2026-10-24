import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the API runs separately on :8000, so proxy /api through to it.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": process.env.API_URL || "http://localhost:8000" },
  },
});
