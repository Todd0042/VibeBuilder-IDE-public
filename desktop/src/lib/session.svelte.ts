// Signing in and staying signed in: pairing, and the authenticator code when the app opens.
// No idle lock: while the app is open it checks in with the server every 2 minutes; the server ends a
// session it hasn't heard from in 10 minutes (an app that crashed, lost power, or a laptop asleep).
import { Api, ApiError, LiveSocket, normalizeServer, type LiveEvent } from "@core/index";
import { tokenDelete, tokenGet, tokenSet, tunnelSession } from "./native";
import { ui } from "./ui.svelte";

// Built in from VB_PUBLIC_URL in vibebuilder.env (bin/vb-app); empty = the sign-in screen asks for it.
export const DEFAULT_SERVER: string = import.meta.env.VITE_DEFAULT_SERVER ?? "";
const KEEPALIVE_MS = 2 * 60 * 1000;

type Phase = "starting" | "pair" | "code" | "ready";

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

  /** Run before a lock or app close signs out (the editors save unsaved files here). Return false when something
   *  couldn't be done (e.g. a file didn't save): the user is then asked before locking or closing. */
  beforeLock(h: () => Promise<boolean | void>) {
    this.beforeLockHandlers.add(h);
    return () => this.beforeLockHandlers.delete(h);
  }

  async init() {
    this.api = this.makeApi(this.server);
    if (!this.server) {
      this.phase = "pair";  // no server yet: the sign-in screen asks for its address first
      return;
    }
    const token = await tokenGet(this.api.server).catch(() => null);
    this.phase = token ? "code" : "pair";
  }

  private makeApi(server: string): Api {
    const api = new Api(server);
    api.onSignedOut = () => this.signedOut("You were signed out (this device was removed, the app was away for over 10 minutes, or the server restarted).");
    return api;
  }

  async setServer(url: string) {
    this.server = normalizeServer(url);
    localStorage.setItem("vb.server", this.server);
    this.api = this.makeApi(this.server);
    const token = await tokenGet(this.api.server).catch(() => null);
    this.phase = token ? "code" : "pair";
  }

  async pair(code: string, name: string) {
    const r = await this.api.pair(code, name);
    await tokenSet(this.api.server, r.device_token);
    this.deviceName = r.device_name;
    this.phase = "code";
  }

  async login(code: string) {
    const token = await tokenGet(this.api.server);
    if (!token) {
      this.phase = "pair";
      throw new ApiError(401, "This device isn't paired yet.");
    }
    try {
      const r = await this.api.login(token, code);
      this.deviceName = r.device_name;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401 && /isn't paired|removed/.test(e.message)) {
        await tokenDelete(this.api.server);
        this.phase = "pair";
      }
      throw e;
    }
    this.lockReason = "";
    void tunnelSession(this.api.server, this.api.session);
    this.phase = "ready";
    this.startLive();
    this.startKeepalive();
  }

  async forgetDevice() {
    await tokenDelete(this.api.server);
    this.phase = "pair";
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
    await Promise.race([this.api.logout(), new Promise((r) => setTimeout(r, 3000))]);  // signing out anyway
    this.lockReason = reason;
    if (this.phase === "ready") this.phase = "code";
    return true;
  }

  private signedOut(reason: string) {
    this.stopBackground();
    this.lockReason = reason;
    if (this.phase === "ready") this.phase = "code";
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
    void tunnelSession(this.api.server, null); // port forwards, phone and app windows stop with the session
    this.live?.stop();
    this.live = null;
    this.connected = false;
    if (this.keepalive) clearInterval(this.keepalive);
    this.keepalive = null;
  }
}

export const session = new SessionState();
