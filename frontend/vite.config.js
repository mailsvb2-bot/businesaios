import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const e2eApiTarget = process.env.BAIOS_E2E_API_TARGET;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173
  },
  preview: {
    strictPort: true,
    proxy: e2eApiTarget ? {
      "/api": {
        target: e2eApiTarget,
        headers: { "X-Forwarded-Proto": "https" },
        rewrite: (path) => path.replace(/^\/api/, "")
      }
    } : undefined
  }
});
