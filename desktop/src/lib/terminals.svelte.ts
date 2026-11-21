// Terminal tabs. Terminals live in the builder and keep running while the app is closed or locked;
// this lists them, and keeps one xterm + connection per tab while you're signed in.
import { PtySocket, type TerminalInfo, type TerminalKind } from "@core/index";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { SearchAddon } from "@xterm/addon-search";
import { Unicode11Addon } from "@xterm/addon-unicode11";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { WebglAddon } from "@xterm/addon-webgl";
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";

export interface Live {
  term: Terminal;
  fit: FitAddon;
  search: SearchAddon;
  socket: PtySocket;
  host: HTMLDivElement;
  state: "connecting" | "open" | "closed";
  exited: number | null | undefined;
}

const THEME = {
  background: "#14161c", foreground: "#d4d7de", cursor: "#e8b04a", cursorAccent: "#14161c",
  selectionBackground: "#3a4a6a", black: "#1c1f26", red: "#f0707a", green: "#8fd18a", yellow: "#e8c46a",
  blue: "#6ea8ff", magenta: "#c792ea", cyan: "#6fd3d8", white: "#d4d7de", brightBlack: "#5c6370",
  brightRed: "#ff8b94", brightGreen: "#a8e6a3", brightYellow: "#f5d78a", brightBlue: "#8fbcff",
  brightMagenta: "#d7aefb", brightCyan: "#8ee8ec", brightWhite: "#ffffff",
};

class Terminals {
  list = $state<TerminalInfo[]>([]);
  activeId = $state<string | null>(null);
  states = $state<Record<string, Live["state"]>>({});
  exited = $state<Record<string, number | null>>({});
  private live = new Map<string, Live>();
  private closeHandlers = new Set<(id: string) => void>();

  /** Called when a terminal tab is closed (app testing stops a run's window forwarding). */
  onClose(h: (id: string) => void) { this.closeHandlers.add(h); }

  async refresh() {
    try {
      const r = await session.api.terminals();
      this.list = r.terminals;
      for (const id of [...this.live.keys()]) if (!this.list.some((t) => t.id === id)) this.dispose(id);
      if (!this.activeId || !this.list.some((t) => t.id === this.activeId)) this.activeId = this.list.at(-1)?.id ?? null;
    } catch {
      /* builder restarting */
    }
  }

  async create(kind: TerminalKind, cwd = ui.project) {
    try {
      const t = await session.api.newTerminal(kind, cwd, 120, 30);
      this.list = [...this.list, t];
      this.activeId = t.id;
      ui.panelOpen = true;
      setTimeout(() => this.focus(t.id), 120);
    } catch (e) {
      ui.error(e, "Couldn't start the terminal");
    }
  }

  async close(id: string) {
    const t = this.list.find((x) => x.id === id);
    if (t?.alive && t.kind !== "shell" && t.kind !== "run" && !(await ui.confirm(`Close ${t.title}?`, `${t.kind} is still running in it. Closing ends it.`, "Close", true))) return;
    try { await session.api.closeTerminal(id); } catch { /* gone already */ }
    this.dispose(id);
    for (const h of this.closeHandlers) h(id);
    const idx = this.list.findIndex((x) => x.id === id);
    this.list = this.list.filter((x) => x.id !== id);
    if (this.activeId === id) this.activeId = (this.list[idx] ?? this.list[idx - 1])?.id ?? null;
  }

  /** Attach a tab's xterm to a DOM element (created once, then moved between mounts). */
  attach(id: string, el: HTMLElement): Live {
    let l = this.live.get(id);
    if (!l) {
      const host = document.createElement("div");
      host.className = "xterm-host";
      const term = new Terminal({
        fontFamily: "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace", fontSize: 13.5, lineHeight: 1.15,
        cursorBlink: true, scrollback: 20000, allowProposedApi: true, theme: THEME, macOptionIsMeta: true,
      });
      const fit = new FitAddon(), search = new SearchAddon();
      term.loadAddon(fit); term.loadAddon(search); term.loadAddon(new WebLinksAddon());
      const u = new Unicode11Addon(); term.loadAddon(u); term.unicode.activeVersion = "11";
      term.open(host);
      try { term.loadAddon(new WebglAddon()); } catch { /* falls back to the DOM renderer */ }
      // Copy with Ctrl+Shift+C, paste with Ctrl+Shift+V (Ctrl+C stays "interrupt" for the shell).
      term.attachCustomKeyEventHandler((ev) => {
        if (ev.type !== "keydown") return true;
        if (ev.ctrlKey && ev.shiftKey && ev.code === "KeyC") { void navigator.clipboard.writeText(term.getSelection()); return false; }
        if (ev.ctrlKey && ev.shiftKey && ev.code === "KeyV") { void navigator.clipboard.readText().then((t) => socket.input(t)); return false; }
        if (ev.ctrlKey && ev.code === "KeyC" && term.hasSelection()) { void navigator.clipboard.writeText(term.getSelection()); term.clearSelection(); return false; }
        return true;
      });
      const socket = new PtySocket(session.api, id, {
        onData: (d) => term.write(d),
        onExit: (code) => { this.exited[id] = code; },
        onState: (s) => { this.states[id] = s; const lv = this.live.get(id); if (lv) lv.state = s; },
      });
      socket.onReconnect = () => term.reset();
      term.onData((d) => socket.input(d));
      term.onResize(({ cols, rows }) => socket.resize(cols, rows));
      l = { term, fit, search, socket, host, state: "connecting", exited: undefined };
      this.live.set(id, l);
      socket.start();
    }
    if (l.host.parentElement !== el) el.appendChild(l.host);
    return l;
  }

  fit(id: string) {
    const l = this.live.get(id);
    if (!l || !l.host.isConnected || l.host.clientWidth === 0) return;
    try { l.fit.fit(); l.socket.resize(l.term.cols, l.term.rows); } catch { /* not laid out yet */ }
  }

  focus(id: string) {
    this.live.get(id)?.term.focus();
  }

  private activeTerm() {
    return this.activeId ? this.live.get(this.activeId)?.term : undefined;
  }

  /** Edit-menu actions when a terminal has the focus. */
  copySelection() {
    const t = this.activeTerm();
    if (t?.hasSelection()) void navigator.clipboard.writeText(t.getSelection());
  }

  async paste() {
    const id = this.activeId;
    const l = id ? this.live.get(id) : undefined;
    if (!l) return;
    try { l.socket.input(await navigator.clipboard.readText()); } catch { ui.toast("Paste with Ctrl+Shift+V in the terminal", "error"); }
  }

  selectAll() { this.activeTerm()?.selectAll(); }
  clear() { this.activeTerm()?.clear(); }

  cycle(dir: 1 | -1) {
    if (!this.list.length) return;
    const i = this.list.findIndex((t) => t.id === this.activeId);
    this.activeId = this.list[(i + dir + this.list.length) % this.list.length].id;
    ui.panelOpen = true;
    const id = this.activeId;
    setTimeout(() => { this.fit(id); this.focus(id); }, 30);
  }

  get(id: string) {
    return this.live.get(id);
  }

  private dispose(id: string) {
    const l = this.live.get(id);
    if (!l) return;
    l.socket.stop();
    l.term.dispose();
    l.host.remove();
    this.live.delete(id);
  }

  /** Signed out: drop connections (the terminals keep running in the builder). */
  disconnectAll() {
    for (const id of [...this.live.keys()]) this.dispose(id);
  }
}

export const terminals = new Terminals();

// Dev builds only: lets the UI end-to-end test read a terminal's text (the WebGL renderer draws to a
// canvas, so there is no DOM text to look at). Not present in the built app.
if (import.meta.env.DEV) {
  (window as any).__vbTerminalText = () => {
    const t = terminals.activeId ? terminals.get(terminals.activeId)?.term : undefined;
    if (!t) return "";
    const b = t.buffer.active, out: string[] = [];
    for (let i = 0; i < b.length; i++) out.push(b.getLine(i)?.translateToString(true) ?? "");
    return out.join("\n");
  };
}
