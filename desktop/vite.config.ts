import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";

// Tauri serves the built files; `npm run tauri dev` uses this dev server on 1420.
export default defineConfig({
  plugins: [svelte()],
  resolve: { alias: { "@core": fileURLToPath(new URL("../client-core/src", import.meta.url)) } },
  // pre-bundled up front, so the first `vb-app` run doesn't reload mid-start when these are first imported
  optimizeDeps: { include: ["@tauri-apps/api/core", "@tauri-apps/api/window", "@tauri-apps/api/webview"] },
  clearScreen: false,
  server: { port: 1420, strictPort: true, fs: { allow: [".."] } },
  build: { target: "es2022", sourcemap: false, chunkSizeWarningLimit: 4000 },
});
