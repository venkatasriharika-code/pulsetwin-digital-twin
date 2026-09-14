import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.GITHUB_ACTIONS ? "/pulsetwin-digital-twin/" : "/",
  server: {
    port: 5173
  }
});
