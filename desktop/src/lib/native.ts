// The Tauri side: the device token in the system keychain. In a plain browser (npm run dev without
// Tauri) the token is kept in memory only, so nothing secret ever lands in web storage.
import { invoke } from "@tauri-apps/api/core";

const inTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
const memory = new Map<string, string>();

export async function tokenGet(server: string): Promise<string | null> {
  if (!inTauri) return memory.get(server) ?? null;
  return (await invoke<string | null>("token_get", { server })) ?? null;
}

export async function tokenSet(server: string, token: string): Promise<void> {
  if (!inTauri) { memory.set(server, token); return; }
  await invoke("token_set", { server, token });
}

export async function tokenDelete(server: string): Promise<void> {
  if (!inTauri) { memory.delete(server); return; }
  await invoke("token_delete", { server });
}

export async function deviceName(): Promise<string> {
  if (!inTauri) return "Browser";
  try { return await invoke<string>("device_name"); } catch { return "Laptop"; }
}

/** Sign out before the window closes (best effort; the server's idle timeout covers a crash). */
/** Runs `handler` when the window is asked to close; the window closes when it returns true, and stays open when it
 *  returns false (the user chose to keep it, e.g. because unsaved files didn't save). */
export async function onWindowClose(handler: () => Promise<boolean>): Promise<void> {
  if (!inTauri) {
    window.addEventListener("beforeunload", () => { void handler(); });
    return;
  }
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  const win = getCurrentWindow();
  await win.onCloseRequested(async (e) => {
    e.preventDefault();
    let close = true;
    try { close = await handler(); } catch { close = true; /* the handler shows its own errors; never trap the user */ }
    if (close) await win.destroy();
  });
}

/** Close the window (the close handler signs out first). */
export async function closeWindow(): Promise<void> {
  if (!inTauri) { window.close(); return; }
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  await getCurrentWindow().close();
}

/** Zoom the whole app (native web view zoom, so terminal and editor mouse positions stay right). */
export async function setZoom(factor: number): Promise<void> {
  if (!inTauri) { document.documentElement.style.zoom = String(factor); return; }
  const { getCurrentWebview } = await import("@tauri-apps/api/webview");
  await getCurrentWebview().setZoom(factor);
}

// ---- app testing (Rust side: src-tauri/src/tunnel.rs). Only in the desktop app. ----------------------
export const canTunnel = inTauri;
export const canAdb = inTauri;
export const canGui = inTauri;
export const canQrScan = false;
const needApp = () => { throw new Error("Only in the desktop app"); };

export async function tunnelSession(server: string, session: string | null): Promise<void> {
  if (inTauri) await invoke("tunnel_session", { server, session });
}
export async function portForward(remote: number, local: number): Promise<number> {
  return inTauri ? invoke<number>("port_forward", { remote, local }) : needApp();
}
export async function portUnforward(remote: number): Promise<void> {
  if (inTauri) await invoke("port_unforward", { remote });
}
export async function portForwards(): Promise<[number, number][]> {
  return inTauri ? invoke<[number, number][]>("port_forwards") : [];
}
export async function adbConnect(): Promise<void> {
  return inTauri ? invoke("adb_connect") : needApp();
}
export async function adbDisconnect(): Promise<void> {
  if (inTauri) await invoke("adb_disconnect");
}
export async function adbStatus(): Promise<boolean> {
  return inTauri ? invoke<boolean>("adb_status") : false;
}
export async function guiStart(runId: string): Promise<string> {
  return inTauri ? invoke<string>("gui_start", { runId }) : needApp();
}
export async function guiStop(runId: string): Promise<void> {
  if (inTauri) await invoke("gui_stop", { runId });
}
