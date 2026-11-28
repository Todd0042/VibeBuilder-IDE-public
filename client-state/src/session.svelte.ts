// Signing in and staying signed in via Cloudflare Zero Trust Access (/api/v1/auth/cf-login).
// No idle lock: while the app is open it checks in with the server every 2 minutes; the server ends a
// session it hasn't heard from in 10 minutes (an app that crashed, lost power, or a device asleep).
import { Api, LiveSocket, normalizeServer, type LiveEvent } from "@core/index";
import { tunnelSession } from "@platform";
import { ui } from "./ui.svelte";

// Built in from VB_PUBLIC_URL in vibebuilder.env; falls back to window.location.origin when served over http(s).
export const DEFAULT_SERVER: string = import.meta.env.VITE_DEFAULT_SERVER ?? "";
const KEEPALIVE_MS = 2 * 60 * 1000;

export type Phase = "starting" | "auth" | "ready";

class SessionState {
  phase = $state<Phase>("starting");
  server = $state(localStorage.getItem("vb.server") || DEFAULT_SERVER);
  deviceName = $state("");
  connected = $state(false);
  lockReason = $state("");
  api = $state(new Api(DEFAULT_SERVER));

  private live: LiveSocket | null = null;
  private listeners = new Set<(e: LiveEvent) => void>();
  private keepalive: ReturnType<typeof setInterval> | null = null;
  private signedOutHandlers = new Set<() => void>();
  private beforeLockHandlers = new Set<() => Promise<boolean | void>>();
  private resumeHandlers = new Set<() => void>();

  /** Run before a lock or app close signs out (the editors save unsaved files here). Return false when something
   *  couldn't be done (e.g. a file didn't save): the user is then asked before locking or closing. */
  beforeLock(h: () => Promise<boolean | void>) {
    this.beforeLockHandlers.add(h);
    return () => this.beforeLockHandlers.delete(h);
  }

  /** Run when the app returns to the foreground while ready (mobile lifecycle). */
  onResume(h: () => void) {
    this.resumeHandlers.add(h);
    return () => this.resumeHandlers.delete(h);
  }

  async init() {
    if (!this.server && typeof window !== "undefined" && window.location.protocol.startsWith("http")) {
      this.server = window.location.origin;
    }
    this.api = this.makeApi(this.server);
    if (!this.server) {
      this.phase = "auth";
      return;
    }
    try {
      const res = await fetch(`${this.api.server}/api/v1/auth/cf-login`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const d = await res.json();
        this.api.session = d.session;
        this.deviceName = d.device_name || "Browser";
        this.lockReason = "";
        void tunnelSession(this.api.server, this.api.session);
        this.phase = "ready";
        this.startLive();
        this.startKeepalive();
        return;
      }
      this.lockReason = `Server returned ${res.status} — sign in via Cloudflare Access to continue.`;
    } catch {
      this.lockReason = "Couldn't reach the server or Cloudflare Access session expired.";
    }
    this.phase = "auth";
  }

  private makeApi(server: string): Api {
    const api = new Api(server);
    api.onSignedOut = () => this.signedOut("Session ended — reconnect via Cloudflare Access.");
    return api;
  }

  async setServer(url: string) {
    this.server = normalizeServer(url);
    localStorage.setItem("vb.server", this.server);
    this.lockReason = "";
    await this.init();
  }

  async reconnect() {
    this.lockReason = "";
    this.phase = "starting";
    await this.init();
  }

  /** Called when a mobile app returns from background: check session validity & refresh sockets. */
  async resumeFromBackground() {
    if (this.phase !== "ready" || !this.api.session) return;
    try {
      await this.api.ping();
      if (!this.live?.connected) this.startLive();
      for (const h of this.resumeHandlers) h();
    } catch {
      /* 401 triggers api.onSignedOut automatically; transient network errors let LiveSocket retry */
    }
  }

  /** The lock button and closing the app end up here. Returns false when the user chose to stay (a file didn't
   *  save), in which case nothing happened. */
  async lock(reason = "", opts: { closing?: boolean } = {}): Promise<boolean> {
    if (this.phase === "ready") {
      let ok = true;
      for (const h of this.beforeLockHandlers) {
        try {
          const timedOut = new Promise<false>((r) => setTimeout(() => r(false), 10_000));
          if ((await Promise.race([h(), timedOut])) === false) ok = false;
        } catch (e) {
          ok = false;
          ui.error(e, "Couldn't finish before signing out");
        }
      }
      if (!ok) {
        const go = opts.closing
          ? await ui.confirm("Some files didn't save", "If you close now, those unsaved edits are lost. The reason is in the error above. Keep the app open to fix it and save again.", "Close anyway", true)
          : await ui.confirm("Some files didn't save", "They stay unsaved in their tabs while locked, and you can save them after signing back in.", "Lock anyway");
        if (!go) return false;
      }
    }
    this.stopBackground();
    await Promise.race([this.api.logout(), new Promise((r) => setTimeout(r, 3000))]);
    this.lockReason = reason;
    if (this.phase === "ready") this.phase = "auth";
    return true;
  }

  private signedOut(reason: string) {
    this.stopBackground();
    this.lockReason = reason;
    if (this.phase === "ready") this.phase = "auth";
    for (const h of this.signedOutHandlers) h();
  }

  onSignedOut(h: () => void) {
    this.signedOutHandlers.add(h);
    return () => this.signedOutHandlers.delete(h);
  }

  // ---- live events -----------------------------------------------------------------------------
  onLive(fn: (e: LiveEvent) => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private startLive() {
    this.live?.stop();
    this.live = new LiveSocket(this.api, (e) => { for (const l of this.listeners) l(e); });
    this.live.onStatus = (c) => (this.connected = c);
    this.live.start();
  }

  // ---- keepalive -------------------------------------------------------------------------------
  private startKeepalive() {
    if (this.keepalive) clearInterval(this.keepalive);
    this.keepalive = setInterval(() => {
      if (this.phase === "ready") this.api.ping().catch(() => {});
    }, KEEPALIVE_MS);
  }

  private stopBackground() {
    void tunnelSession(this.api.server, null);
    this.live?.stop();
    this.live = null;
    this.connected = false;
    if (this.keepalive) clearInterval(this.keepalive);
    this.keepalive = null;
  }
}

export const session = new SessionState();
