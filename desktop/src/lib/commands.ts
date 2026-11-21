// Every user action in one place: the menus and the keyboard shortcuts both run these, so a menu item
// and its shortcut can never do different things. `keys` is shown in menus; `global` shortcuts are
// handled app-wide (the rest, like Ctrl+Z or Ctrl+F, belong to the focused editor/terminal and the
// menu just calls the same action).
import { changes } from "./changes.svelte";
import { editors, type EditorCommand } from "./editors.svelte";
import { deleteItem, newItem, renameItem } from "./fileOps";
import { closeWindow, setZoom } from "./native";
import { session } from "./session.svelte";
import { terminals } from "./terminals.svelte";
import { testing } from "./testing.svelte";
import { tree } from "./tree.svelte";
import { ui } from "./ui.svelte";

export interface Command {
  label: string;
  keys?: string;
  global?: boolean;
  run: () => unknown;
  enabled?: () => boolean;
  checked?: () => boolean;
}

const hasFile = () => !!editors.activeFile;
const hasTab = () => !!editors.active;

/** Where keyboard focus is: menu actions like Copy go to whichever had it last. */
export function focusIn(): "terminal" | "editor" | "other" {
  const el = document.activeElement;
  if (el?.closest(".xterm")) return "terminal";
  if (el?.closest(".cm-editor")) return "editor";
  return lastFocus;
}
let lastFocus: "terminal" | "editor" | "other" = "other";
if (typeof window !== "undefined") {
  window.addEventListener("focusin", (e) => {
    const t = e.target as HTMLElement | null;
    if (t?.closest(".xterm")) lastFocus = "terminal";
    else if (t?.closest(".cm-editor")) lastFocus = "editor";
  });
}

function edit(cmd: EditorCommand) {
  editors.activeFile?.handle?.exec(cmd);
}

function showSide(v: typeof ui.side) {
  ui.side = v;
  ui.sideOpen = true;
  if (v === "changes") changes.unseen = 0;
}

function folderSearch() {
  const sel = window.getSelection()?.toString() ?? "";
  showSide("search");
  ui.searchSeed = { text: sel.includes("\n") ? "" : sel, n: ui.searchSeed.n + 1 };
}

function toggleTerminal() {
  ui.panelOpen = !ui.panelOpen;
  ui.persist();
  if (ui.panelOpen && terminals.activeId) setTimeout(() => terminals.focus(terminals.activeId!), 30);
}

function openRange(label: string, sec: number) {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const since = sec < 0 ? start.getTime() / 1000 : Date.now() / 1000 - sec;
  editors.openReview({ type: "range", since, label }, `Changes: ${label.toLowerCase()}`);
}

let zoom = Number(localStorage.getItem("vb.zoom") || "1");
function zoomBy(d: number | null) {
  zoom = d === null ? 1 : Math.min(2, Math.max(0.6, Math.round((zoom + d) * 10) / 10));
  localStorage.setItem("vb.zoom", String(zoom));
  void setZoom(zoom);
}
export function restoreZoom() {
  if (zoom !== 1) void setZoom(zoom);
}

export const commands = {
  // ---- File -----------------------------------------------------------------------------------
  newFile: { label: "New File…", keys: "Ctrl+N", global: true, run: () => newItem("file") },
  newFolder: { label: "New Folder…", run: () => newItem("dir") },
  openFolder: { label: "Open Folder…", keys: "Ctrl+Alt+O", global: true, run: () => (ui.folderPicker = true) },
  openFile: { label: "Open File…", keys: "Ctrl+P", global: true, run: () => (ui.quickOpen = true) },
  save: { label: "Save", keys: "Ctrl+S", global: true, enabled: hasFile, run: () => { const t = editors.activeFile; if (t) void editors.save(t); } },
  saveAll: { label: "Save All", keys: "Ctrl+Alt+S", global: true, enabled: () => editors.dirtyTabs.length > 0, run: () => editors.saveAll() },
  revert: { label: "Revert File", enabled: hasFile, run: () => { const t = editors.activeFile; if (t) void editors.revert(t); } },
  renameFile: { label: "Rename File…", enabled: hasFile, run: () => { const t = editors.activeFile; if (t) void renameItem(t.path); } },
  deleteFile: { label: "Delete File…", enabled: hasFile, run: () => { const t = editors.activeFile; if (t) void deleteItem(t.path); } },
  closeTab: { label: "Close Tab", keys: "Ctrl+W", global: true, enabled: hasTab, run: () => { if (editors.activeId) void editors.close(editors.activeId); } },
  closeAll: { label: "Close All Tabs", enabled: hasTab, run: () => editors.closeAll() },
  lock: { label: "Lock", keys: "Ctrl+Alt+L", global: true, run: () => session.lock("Locked.") },
  quit: { label: "Quit", keys: "Ctrl+Q", global: true, run: () => closeWindow() },

  // ---- Edit -----------------------------------------------------------------------------------
  undo: { label: "Undo", keys: "Ctrl+Z", enabled: hasFile, run: () => edit("undo") },
  redo: { label: "Redo", keys: "Ctrl+Shift+Z", enabled: hasFile, run: () => edit("redo") },
  cut: { label: "Cut", keys: "Ctrl+X", enabled: hasFile, run: () => edit("cut") },
  copy: { label: "Copy", keys: "Ctrl+C", run: () => (focusIn() === "terminal" ? terminals.copySelection() : edit("copy")) },
  paste: { label: "Paste", keys: "Ctrl+V", run: () => (focusIn() === "terminal" ? terminals.paste() : edit("paste")) },
  selectAll: { label: "Select All", keys: "Ctrl+A", run: () => (focusIn() === "terminal" ? terminals.selectAll() : edit("selectAll")) },
  find: { label: "Find", keys: "Ctrl+F", enabled: hasFile, run: () => edit("find") },
  replace: { label: "Replace", keys: "Ctrl+H", enabled: hasFile, run: () => edit("replace") },
  findInFolder: { label: "Find in Folder", keys: "Ctrl+Shift+F", global: true, run: folderSearch },
  toggleComment: { label: "Toggle Comment", keys: "Ctrl+/", enabled: hasFile, run: () => edit("toggleComment") },

  // ---- View -----------------------------------------------------------------------------------
  explorer: { label: "Explorer", keys: "Ctrl+Shift+E", global: true, checked: () => ui.sideOpen && ui.side === "explorer", run: () => showSide("explorer") },
  search: { label: "Search", checked: () => ui.sideOpen && ui.side === "search", run: () => showSide("search") },
  changesView: { label: "Changes", keys: "Ctrl+Shift+G", global: true, checked: () => ui.sideOpen && ui.side === "changes", run: () => showSide("changes") },
  devices: { label: "Devices & Settings", checked: () => ui.sideOpen && ui.side === "devices", run: () => showSide("devices") },
  toggleSide: { label: "Side Bar", keys: "Ctrl+B", global: true, checked: () => ui.sideOpen, run: () => (ui.sideOpen = !ui.sideOpen) },
  toggleTerminal: { label: "Terminal Panel", keys: "Ctrl+`", global: true, checked: () => ui.panelOpen, run: toggleTerminal },
  maximizeTerminal: { label: "Maximize Terminal Panel", checked: () => ui.panelOpen && ui.panelMax, run: () => { ui.panelOpen = true; ui.panelMax = !ui.panelMax; } },
  zoomIn: { label: "Zoom In", keys: "Ctrl+=", global: true, run: () => zoomBy(0.1) },
  zoomOut: { label: "Zoom Out", keys: "Ctrl+-", global: true, run: () => zoomBy(-0.1) },
  zoomReset: { label: "Reset Zoom", keys: "Ctrl+0", global: true, run: () => zoomBy(null) },

  // ---- Go -------------------------------------------------------------------------------------
  goToFile: { label: "Go to File…", keys: "Ctrl+P", run: () => (ui.quickOpen = true) },
  goToLine: { label: "Go to Line…", keys: "Ctrl+G", enabled: hasFile, run: () => edit("gotoLine") },
  nextTab: { label: "Next Tab", keys: "Ctrl+Tab", global: true, enabled: hasTab, run: () => editors.cycle(1) },
  prevTab: { label: "Previous Tab", keys: "Ctrl+Shift+Tab", global: true, enabled: hasTab, run: () => editors.cycle(-1) },
  reveal: { label: "Reveal File in Explorer", enabled: hasFile, run: () => { const t = editors.activeFile; if (t) { showSide("explorer"); void tree.reveal(t.path); } } },
  fileHistory: { label: "File History", enabled: hasFile, run: () => { const t = editors.activeFile; if (t) editors.openReview({ type: "file", path: t.path }, `History: ${t.title}`); } },
  changes15: { label: "Changes: Last 15 Minutes", run: () => openRange("Last 15 minutes", 900) },
  changesHour: { label: "Changes: Last Hour", run: () => openRange("Last hour", 3600) },
  changesToday: { label: "Changes: Today", run: () => openRange("Today", -1) },

  // ---- Terminal -------------------------------------------------------------------------------
  newClaude: { label: "New Claude Terminal", run: () => terminals.create("claude") },
  newAgy: { label: "New agy Terminal", run: () => terminals.create("agy") },
  newShell: { label: "New Shell", keys: "Ctrl+Shift+`", global: true, run: () => terminals.create("shell") },
  closeTerminal: { label: "Close Terminal", enabled: () => !!terminals.activeId, run: () => { if (terminals.activeId) void terminals.close(terminals.activeId); } },
  nextTerminal: { label: "Next Terminal", enabled: () => terminals.list.length > 1, run: () => terminals.cycle(1) },
  prevTerminal: { label: "Previous Terminal", enabled: () => terminals.list.length > 1, run: () => terminals.cycle(-1) },
  runApp: { label: "Run App…", keys: "F5", global: true, run: () => testing.runApp() },
  ports: { label: "Ports & Phone", checked: () => ui.panelOpen && ui.panelTab === "ports", run: () => { ui.panelOpen = true; ui.panelTab = "ports"; } },
  phone: { label: "Connect Phone (adb)", enabled: () => testing.available, checked: () => testing.adb, run: () => testing.toggleAdb() },
  clearTerminal: { label: "Clear Terminal", enabled: () => !!terminals.activeId, run: () => terminals.clear() },

  // ---- Help -----------------------------------------------------------------------------------
  shortcuts: { label: "Keyboard Shortcuts", run: () => showSide("devices") },
  about: {
    label: "About VibeBuilder IDE",
    run: () => ui.ask({
      title: "VibeBuilder IDE 0.1.0",
      message: `Connected to ${session.api.server.replace(/^https?:\/\//, "")} as ${session.deviceName || "this device"}.`,
      buttons: [{ label: "OK", value: "ok", primary: true }],
    }),
  },
} satisfies Record<string, Command>;

export type CommandId = keyof typeof commands;

export type MenuEntry = CommandId | "-" | { projects: true };
export const MENUS: { label: string; key: string; items: MenuEntry[] }[] = [
  { label: "File", key: "f", items: ["newFile", "newFolder", "-", "openFolder", "openFile", "-", { projects: true }, "-", "save", "saveAll", "revert", "-", "renameFile", "deleteFile", "-", "closeTab", "closeAll", "-", "lock", "quit"] },
  { label: "Edit", key: "e", items: ["undo", "redo", "-", "cut", "copy", "paste", "selectAll", "-", "find", "replace", "findInFolder", "-", "toggleComment"] },
  { label: "View", key: "v", items: ["explorer", "search", "changesView", "devices", "-", "toggleSide", "toggleTerminal", "maximizeTerminal", "-", "zoomIn", "zoomOut", "zoomReset"] },
  { label: "Go", key: "g", items: ["goToFile", "goToLine", "-", "nextTab", "prevTab", "-", "reveal", "fileHistory", "-", "changes15", "changesHour", "changesToday"] },
  { label: "Terminal", key: "t", items: ["newClaude", "newAgy", "newShell", "-", "runApp", "ports", "phone", "-", "nextTerminal", "prevTerminal", "clearTerminal", "closeTerminal"] },
  { label: "Help", key: "h", items: ["shortcuts", "about"] },
];

/** "Ctrl+Shift+F" style name for a key event (layout-independent for symbols). */
export function keyName(e: KeyboardEvent): string {
  const codeKeys: Record<string, string> = { Backquote: "`", Equal: "=", Minus: "-", Slash: "/", Digit0: "0", NumpadAdd: "=", NumpadSubtract: "-", Numpad0: "0" };
  let k = codeKeys[e.code] ?? (e.key.length === 1 ? e.key.toUpperCase() : e.key);
  if (k === "+") k = "=";
  return [e.ctrlKey || e.metaKey ? "Ctrl" : "", e.altKey ? "Alt" : "", e.shiftKey ? "Shift" : "", k].filter(Boolean).join("+");
}

const byKey = new Map<string, Command>();
for (const c of Object.values(commands) as Command[]) if (c.global && c.keys) byKey.set(c.keys, c);

/** App-wide shortcuts; returns true if one ran. */
export function runShortcut(e: KeyboardEvent): boolean {
  const c = byKey.get(keyName(e));
  if (!c || (c.enabled && !c.enabled())) return false;
  e.preventDefault();
  e.stopPropagation();
  void c.run();
  return true;
}
