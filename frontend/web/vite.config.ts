import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// В dev картинки и статика Django берутся с локального бэкенда; в prod их отдаёт nginx.
const backend = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [tailwindcss(), reactRouter()],
  resolve: { tsconfigPaths: true },
  server: {
    port: 3000,
    proxy: {
      "/media": backend,
      "/django-static": backend,
    },
  },
});
