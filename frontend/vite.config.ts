import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: vite on :5173 proxies /api to uvicorn on :8000. Prod: FastAPI serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
