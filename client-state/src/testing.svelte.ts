// App testing: run an app in the builder, forward dev-server ports locally, and optional desktop adb/waypipe.
import { session } from "./session.svelte";
import { terminals } from "./terminals.svelte";
import { ui } from "./ui.svelte";
import {
  adbConnect, adbDisconnect, adbStatus, canAdb, canGui, canPreview, canTunnel, guiStart, guiStop,
  portForward, portForwards, portUnforward,
} from "@platform";

const LAST_CMD = "vb.runCmd:"; // per folder

class Testing {
  /** Ports something listens on in the builder. */
  builderPorts = $state<{ port: number; process: string }[]>([]);
  /** Why the builder's port list couldn't be refreshed ("" when it could). */
  portsError = $state("");
  /** remote (builder) port -> local port */
  forwards = $state<Record<number, number>>({});
  adb = $state(false);
  busy = $state(false);
  readonly available = canTunnel;
  readonly adbAvailable = canAdb;
  readonly guiAvailable = canGui;
  readonly previewAvailable = canPreview;
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
    try {
      this.builderPorts = (await session.api.ports()).ports;
      this.portsError = "";
    } catch (e) {
      this.portsError = e instanceof Error ? e.message : String(e);
    }
    this.forwards = Object.fromEntries(await portForwards());
    this.adb = await adbStatus();
  }

  async forward(remote: number, local = remote): Promise<void> {
    try {
      const got = await portForward(remote, local);
      this.forwards = { ...this.forwards, [remote]: got };
      ui.toast(`Builder port ${remote} is now localhost:${got} on this device`, "ok");
    } catch (e) {
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
    if (!this.adbAvailable) return;
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

  /** Run App...: ask for the command (remembered per folder), then start it. */
  async runApp() {
    const key = LAST_CMD + ui.project;
    const r = await ui.ask({
      title: `Run an app in ${ui.project || "the workspace"}`,
      message: this.guiAvailable
        ? "Its windows (and dialogs) open on this laptop as their own windows. Its output goes to a ▶ terminal tab; close the tab to stop it."
        : this.previewAvailable
        ? "Runs the command with an in-app interactive screen preview tab to verify the UI. Close the tab to stop it."
        : "Runs the command in a ▶ terminal tab (close the tab to stop it). Forward any web port in the Ports tab to preview it here.",
      input: localStorage.getItem(key) ?? "",
      placeholder: "e.g. npm run dev · ./build/game · python app.py",
      buttons: [
        { label: "Cancel", value: "cancel" },
        ...(this.guiAvailable ? [{ label: "Run with windows", value: "gui", primary: true }] : []),
        ...(!this.guiAvailable && this.previewAvailable ? [{ label: "Run with preview", value: "preview", primary: true }] : []),
        { label: "Terminal only", value: "plain", primary: !this.guiAvailable && !this.previewAvailable },
      ],
    });
    const cmd = r.input.trim();
    if (r.button === "cancel" || !cmd) return;
    localStorage.setItem(key, cmd);
    await this.run(cmd, r.button === "gui" ? "gui" : r.button === "preview" ? "preview" : "plain");
  }

  async run(cmd: string, mode: "gui" | "preview" | "plain" | boolean) {
    const runId = Math.random().toString(16).slice(2, 12);
    let socket = "";
    const isGui = mode === "gui" || mode === true;
    const isPreview = mode === "preview";
    try {
      if (isGui) socket = await guiStart(runId);
      const t = await session.api.newTerminal("run", ui.project, 120, 30, {
        cmd,
        waypipeSocket: socket,
        preview: isPreview,
      });
      if (isGui) this.runs.set(t.id, runId);
      terminals.list = [...terminals.list, t];
      terminals.activeId = t.id;
      ui.panelOpen = true;
      ui.panelTab = "terminals";
      ui.mobileView = "terminal";
    } catch (e) {
      if (isGui) void guiStop(runId);
      ui.error(e, "Couldn't start the app");
    }
  }
}

export const testing = new Testing();
