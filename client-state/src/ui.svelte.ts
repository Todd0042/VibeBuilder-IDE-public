// Layout and app-wide UI state: which view is open, panel sizes, toasts, dialogs.

export type SideView = "explorer" | "search" | "changes" | "devices";
export type MobileView = "files" | "editor" | "changes" | "terminal" | "more";

interface Toast { id: number; text: string; kind: "info" | "error" | "ok"; action?: { label: string; run: () => void } }
export interface DialogCheck { id: string; label: string; checked: boolean }
interface Dialog {
  title: string; message?: string; input?: string; placeholder?: string;
  checks?: DialogCheck[];
  buttons: { label: string; value: string; primary?: boolean; danger?: boolean }[];
  resolve: (r: { button: string; input: string; checks: Record<string, boolean> }) => void;
}

function stored<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v === null ? fallback : (JSON.parse(v) as T); } catch { return fallback; }
}

class UiState {
  project = $state<string>(stored("vb.project", ""));
  workspaceOpen = $state<boolean>(stored("vb.workspaceOpen", false));
  projects = $state<string[]>([]);
  /** Folders hidden from the folder list (kept on the server, so every device agrees). */
  hiddenFolders = $state<string[]>([]);
  /** Folders opened with File -> Open Folder (any depth), most recent first. */
  recentFolders = $state<string[]>(stored("vb.recentFolders", []));
  side = $state<SideView>("explorer");
  sideOpen = $state(true);
  sideWidth = $state(stored("vb.sideWidth", 300));
  panelOpen = $state(stored("vb.panelOpen", true));
  panelHeight = $state(stored("vb.panelHeight", 300));
  panelMax = $state(false);
  panelTab = $state<"terminals" | "ports">("terminals");
  /** Mobile primary tab (used by the Android app). */
  mobileView = $state<MobileView>("files");
  mobileMore = $state<"menu" | "search" | "ports" | "devices">("menu");
  keyboardOpen = $state(false);
  quickOpen = $state(false);
  toasts = $state<Toast[]>([]);
  dialog = $state<Dialog | null>(null);
  searchSeed = $state<{ text: string; n: number }>({ text: "", n: 0 });
  private nextToast = 1;

  /** Open a folder ("" opens the /workspace root itself). */
  openFolder(path: string) {
    path = path.replace(/^\/+|\/+$/g, "");
    if (!path) {
      this.workspaceOpen = true;
      this.project = "";
      this.persist();
      return;
    }
    this.workspaceOpen = false;
    this.recentFolders = [path, ...this.recentFolders.filter((p) => p !== path)].slice(0, 8);
    localStorage.setItem("vb.recentFolders", JSON.stringify(this.recentFolders));
    this.project = path;
    this.persist();
  }

  /** What the folder dropdown and File menu list: recent nested folders, then the projects, minus hidden ones. */
  get folderChoices(): string[] {
    const hidden = new Set(this.hiddenFolders);
    const nested = this.recentFolders.filter((p) => p.includes("/") && !hidden.has(p));
    return [...nested, ...this.projects.filter((p) => !nested.includes(p) && !hidden.has(p))];
  }

  folderPicker = $state(false);

  persist() {
    localStorage.setItem("vb.project", JSON.stringify(this.project));
    localStorage.setItem("vb.workspaceOpen", JSON.stringify(this.workspaceOpen));
    localStorage.setItem("vb.sideWidth", JSON.stringify(this.sideWidth));
    localStorage.setItem("vb.panelOpen", JSON.stringify(this.panelOpen));
    localStorage.setItem("vb.panelHeight", JSON.stringify(this.panelHeight));
  }

  showSide(v: SideView) {
    if (this.side === v && this.sideOpen) this.sideOpen = false;
    else { this.side = v; this.sideOpen = true; }
  }

  toast(text: string, kind: Toast["kind"] = "info", action?: Toast["action"], ms = 4500) {
    const id = this.nextToast++;
    this.toasts = [...this.toasts, { id, text, kind, action }];
    setTimeout(() => (this.toasts = this.toasts.filter((t) => t.id !== id)), kind === "error" ? ms * 2 : ms);
  }

  error(e: unknown, prefix = "") {
    const msg = e instanceof Error ? e.message : String(e);
    this.toast(prefix ? `${prefix}: ${msg}` : msg, "error");
  }

  ask(d: Omit<Dialog, "resolve">): Promise<{ button: string; input: string; checks: Record<string, boolean> }> {
    return new Promise((resolve) => {
      this.dialog = { ...d, resolve: (r) => { this.dialog = null; resolve(r); } };
    });
  }

  async confirm(title: string, message: string, ok = "OK", danger = false): Promise<boolean> {
    const r = await this.ask({ title, message, buttons: [{ label: "Cancel", value: "cancel" }, { label: ok, value: "ok", primary: !danger, danger }] });
    return r.button === "ok";
  }

  async prompt(title: string, value = "", placeholder = ""): Promise<string | null> {
    const r = await this.ask({ title, input: value, placeholder, buttons: [{ label: "Cancel", value: "cancel" }, { label: "OK", value: "ok", primary: true }] });
    return r.button === "ok" ? r.input.trim() : null;
  }
}

export const ui = new UiState();
