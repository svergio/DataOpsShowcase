import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8012,
    proxy: {
      "/api": "http://localhost:8010",
      "/metrics": "http://localhost:8010"
    }
  }
});
