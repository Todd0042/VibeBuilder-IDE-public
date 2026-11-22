import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [svelte()],
  resolve: {
    alias: {
      "@core": fileURLToPath(new URL("../client-core/src", import.meta.url)),
      "@state": fileURLToPath(new URL("../client-state/src", import.meta.url)),
      "@platform": fileURLToPath(new URL("./src/lib/native.ts", import.meta.url)),
      "@xterm": fileURLToPath(new URL("./node_modules/@xterm", import.meta.url)),
      "@codemirror": fileURLToPath(new URL("./node_modules/@codemirror", import.meta.url)),
      "@lezer": fileURLToPath(new URL("./node_modules/@lezer", import.meta.url)),
    },
  },
  optimizeDeps: {
    include: ["@tauri-apps/api/core", "@tauri-apps/plugin-opener", "@tauri-apps/plugin-barcode-scanner"],
  },
  clearScreen: false,
  server: {
    port: 1421,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: "ws", host, port: 1422 } : undefined,
    fs: { allow: [".."] },
  },
  build: { target: "es2022", sourcemap: false, chunkSizeWarningLimit: 4000 },
});
