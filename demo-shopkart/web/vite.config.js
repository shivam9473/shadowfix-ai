import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5184,
    strictPort: true,
    proxy: { "/checkout": "http://127.0.0.1:8010", "/health": "http://127.0.0.1:8010" },
  },
});
