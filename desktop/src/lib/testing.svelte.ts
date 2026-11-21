// App testing: run an app in the builder with its windows on this laptop (waypipe), forward the
// builder's dev-server ports here, and let the builder's adb reach a phone plugged into this laptop.
// The tunnels themselves live in the native side (src-tauri/src/tunnel.rs).
import { session } from "./session.svelte";
import { terminals } from "./terminals.svelte";
import { ui } from "./ui.svelte";
import {
  adbConnect, adbDisconnect, adbStatus, canTunnel, guiStart, guiStop, portForward, portForwards, portUnforward,
} from "./native";

const LAST_CMD = "vb.runCmd:"; // per folder

class Testing {
  /** Ports something listens on in the builder. */
  builderPorts = $state<{ port: number; process: string }[]>([]);
  /** remote (builder) port -> local (laptop) port */
  forwards = $state<Record<number, number>>({});
  adb = $state(false);
  busy = $state(false);
  readonly available = canTunnel;
  private runs = new Map<string, string>(); // terminal id -> run id (GUI runs)

  constructor() {
    terminals.onClose((id) => {
      const run = this.runs.get(id);
      if (run) {
        this.runs.delete(id);
        void guiStop(run);
      }
    });
    session.onSignedOut(() => { this.forwards = {}; this.adb = false; this.runs.clear(); });
  }

  async refresh() {
    try { this.builderPorts = (await session.api.ports()).ports; } catch { /* builder restarting */ }
    this.forwards = Object.fromEntries(await portForwards());
    this.adb = await adbStatus();
  }

  async forward(remote: number, local = remote): Promise<void> {
    try {
      const got = await portForward(remote, local);
      this.forwards = { ...this.forwards, [remote]: got };
      ui.toast(`Builder port ${remote} is now localhost:${got} on this laptop`, "ok");
    } catch (e) {
      // the same port number may be taken here: fall back to any free one
      if (local !== 0 && String(e).includes("busy")) return this.forward(remote, 0);
      ui.error(e, `Couldn't forward ${remote}`);
    }
  }

  async unforward(remote: number) {
    await portUnforward(remote);
    const { [remote]: _, ...rest } = this.forwards;
    this.forwards = rest;
  }

  async toggleAdb() {
    this.busy = true;
    try {
      if (this.adb) { await adbDisconnect(); this.adb = false; }
      else {
        await adbConnect();
        this.adb = true;
        ui.toast("Phone connected: in a shell, adb devices / ./gradlew installDebug go to the phone on this laptop", "ok", undefined, 7000);
      }
    } catch (e) {
      ui.error(e, "Phone");
    } finally {
      this.busy = false;
    }
  }

  /** Terminal → Run App…: ask for the command (remembered per folder), then start it. */
  async runApp() {
    const key = LAST_CMD + ui.project;
    const r = await ui.ask({
      title: `Run an app in ${ui.project || "the workspace"}`,
      message: this.available
        ? "Its windows (and dialogs) open on this laptop as their own windows. Its output goes to a ▶ terminal tab; close the tab to stop it."
        : "Showing the app's windows needs the desktop app; in a browser it runs in a terminal tab only.",
      input: localStorage.getItem(key) ?? "",
      placeholder: "e.g. npm run tauri dev · ./build/game · python app.py",
      buttons: [
        { label: "Cancel", value: "cancel" },
        { label: "Terminal only", value: "plain" },
        ...(this.available ? [{ label: "Run with windows", value: "gui", primary: true }] : []),
      ],
    });
    const cmd = r.input.trim();
    if (r.button === "cancel" || !cmd) return;
    localStorage.setItem(key, cmd);
    await this.run(cmd, r.button === "gui");
  }

  async run(cmd: string, gui: boolean) {
    const runId = Math.random().toString(16).slice(2, 12);
    let socket = "";
    try {
      if (gui) socket = await guiStart(runId);
      const t = await session.api.newTerminal("run", ui.project, 120, 30, { cmd, waypipeSocket: socket });
      if (gui) this.runs.set(t.id, runId);
      terminals.list = [...terminals.list, t];
      terminals.activeId = t.id;
      ui.panelOpen = true;
      ui.panelTab = "terminals";
    } catch (e) {
      if (gui) void guiStop(runId);
      ui.error(e, "Couldn't start the app");
    }
  }
}

export const testing = new Testing();
