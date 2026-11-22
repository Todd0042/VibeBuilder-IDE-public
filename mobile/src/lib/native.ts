// Mobile/Android native bridge implementing PlatformBridge (@platform).
import { invoke } from "@tauri-apps/api/core";
import { parsePairingQr } from "@core/index";

const inTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
const memory = new Map<string, string>();

export const canTunnel = inTauri;
export const canAdb = false;
export const canGui = false;
export const canQrScan = inTauri;

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
  if (!inTauri) return "Mobile Browser";
  try { return await invoke<string>("device_name"); } catch { return "Android Phone"; }
}

export async function onWindowClose(_handler: () => Promise<boolean>): Promise<void> {
  // Android handles background/resume lifecycle rather than window close.
}

export async function closeWindow(): Promise<void> {}

export async function setZoom(factor: number): Promise<void> {
  document.documentElement.style.setProperty("--text-scale", String(factor));
}

export async function tunnelSession(server: string, session: string | null): Promise<void> {
  if (inTauri) await invoke("tunnel_session", { server, session });
}

export async function portForward(remote: number, local: number): Promise<number> {
  if (!inTauri) throw new Error("Only in the Android app");
  return invoke<number>("port_forward", { remote, local });
}

export async function portUnforward(remote: number): Promise<void> {
  if (inTauri) await invoke("port_unforward", { remote });
}

export async function portForwards(): Promise<[number, number][]> {
  return inTauri ? invoke<[number, number][]>("port_forwards") : [];
}

export async function adbConnect(): Promise<void> {
  throw new Error("USB ADB host passthrough is only available in the desktop app.");
}

export async function adbDisconnect(): Promise<void> {}
export async function adbStatus(): Promise<boolean> { return false; }

export async function guiStart(_runId: string): Promise<string> {
  throw new Error("Wayland window streaming is only available in the desktop app.");
}

export async function guiStop(_runId: string): Promise<void> {}

export { parsePairingQr };

export async function scanPairingQr(): Promise<{ server: string; code: string } | null> {
  if (!inTauri) return null;
  const { scan, Format, checkPermissions, requestPermissions } = await import("@tauri-apps/plugin-barcode-scanner");
  let perm = await checkPermissions();
  if (perm !== "granted") {
    perm = await requestPermissions();
    if (perm !== "granted") throw new Error("Camera permission is needed to scan the pairing QR code.");
  }
  const res = await scan({ windowed: false, formats: [Format.QRCode] });
  const parsed = parsePairingQr(res.content);
  if (!parsed) throw new Error("That QR code isn't a VibeBuilder pairing code (run `vibebuilder pair` on your desktop).");
  return parsed;
}

export async function openExternal(url: string): Promise<void> {
  if (!inTauri) { window.open(url, "_blank", "noopener"); return; }
  const { openUrl } = await import("@tauri-apps/plugin-opener");
  await openUrl(url);
}
