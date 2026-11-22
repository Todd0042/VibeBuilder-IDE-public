import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";

// Tauri serves the built files; `npm run tauri dev` uses this dev server on 1420.
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
  // pre-bundled up front, so the first `vb-app` run doesn't reload mid-start when these are first imported
  optimizeDeps: { include: ["@tauri-apps/api/core", "@tauri-apps/api/window", "@tauri-apps/api/webview"] },
  clearScreen: false,
  server: { port: 1420, strictPort: true, fs: { allow: [".."] } },
  build: { target: "es2022", sourcemap: false, chunkSizeWarningLimit: 4000 },
});
