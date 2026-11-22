// Open tabs: files (one CodeMirror each, kept alive so undo history survives tab switches) and
// reviews (change sets / time ranges). Saving, auto-save, and files changed on disk by an agent.
import { ApiError, AutoSave, basename, type FileContent } from "@core/index";
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";
import { mediaKind, type MediaKind } from "./media";

export type EditorCommand = "undo" | "redo" | "selectAll" | "find" | "replace" | "gotoLine" | "toggleComment" | "cut" | "copy" | "paste";

export interface EditorHandle {
  exec(cmd: EditorCommand): void;
  getText(): string;
  setText(text: string, keepCursor: boolean): void;
  markSaved(): void;
  goTo(line: number, col?: number, length?: number): void;
  focus(): void;
}

export interface FileTab {
  kind: "file";
  id: string;
  path: string;
  title: string;
  etag: string | null;
  initial: string;
  binary: boolean;
  dirty: boolean;
  loading: boolean;
  pinned: boolean;
  /** Changed on disk while you had unsaved edits. */
  conflict: { etag: string; text: string } | null;
  deletedOnDisk: boolean;
  notice: string;
  handle: EditorHandle | null;
  pendingGoTo: { line: number; col?: number; length?: number } | null;
  /** Shown in the media viewer instead of the editor. */
  media: MediaKind | null;
  /** Bumped when the file changes on disk, so the viewer reloads it. */
  mediaRev: number;
}

export type ReviewSource = { type: "changeset"; id: number } | { type: "range"; since: number; label: string } |
  { type: "file"; path: string } | { type: "compare"; path: string; mine: string; theirs: string };

export interface ReviewTab { kind: "review"; id: string; title: string; source: ReviewSource; pinned: boolean }

export type Tab = FileTab | ReviewTab;

class Editors {
  tabs = $state<Tab[]>([]);
  activeId = $state<string | null>(null);
  saving = $state(false);
  autosaveDue = $state<number | null>(null);
  private autosave = new AutoSave((path) => { const t = this.file(path); if (t?.dirty) void this.save(t, { background: true }); });

  get active(): Tab | null {
    return this.tabs.find((t) => t.id === this.activeId) ?? null;
  }

  get dirtyTabs(): FileTab[] {
    return this.tabs.filter((t): t is FileTab => t.kind === "file" && t.dirty);
  }

  file(path: string): FileTab | undefined {
    return this.tabs.find((t): t is FileTab => t.kind === "file" && t.path === path);
  }

  // ---- opening ---------------------------------------------------------------------------------
  async open(path: string, goTo?: { line: number; col?: number; length?: number }, asText = false) {
    const existing = this.file(path);
    if (existing) {
      this.activeId = existing.id;
      if (goTo) existing.handle ? existing.handle.goTo(goTo.line, goTo.col, goTo.length) : (existing.pendingGoTo = goTo);
      else existing.handle?.focus();
      return;
    }
    const tab: FileTab = {
      kind: "file", id: path, path, title: basename(path), etag: null, initial: "", binary: false, dirty: false,
      loading: true, pinned: false, conflict: null, deletedOnDisk: false, notice: "", handle: null, pendingGoTo: goTo ?? null,
      media: asText ? null : mediaKind(path), mediaRev: 0,
    };
    const at = this.tabs.findIndex((t) => t.id === this.activeId);
    this.tabs.splice(at < 0 ? this.tabs.length : at + 1, 0, tab);
    this.activeId = tab.id;
    if (tab.media) { // the viewer loads it itself (any size, streamed)
      Object.assign(tab, { binary: true, loading: false });
      return;
    }
    try {
      const f = await session.api.read(path);
      const t = this.file(path);
      if (!t) return;
      Object.assign(t, { etag: f.etag, initial: f.content, binary: f.binary, loading: false });
    } catch (e) {
      this.tabs = this.tabs.filter((t) => t.id !== path);
      if (this.activeId === path) this.activeId = this.tabs.at(-1)?.id ?? null;
      ui.error(e, `Couldn't open ${basename(path)}`);
    }
  }

  openReview(source: ReviewSource, title: string) {
    const id = source.type === "changeset" ? `review:cs:${source.id}` : source.type === "range" ? `review:range:${source.label}`
      : `review:${source.type}:${source.path}`;
    const existing = this.tabs.find((t) => t.id === id);
    if (existing) {
      if (existing.kind === "review") existing.source = source;
      this.activeId = id;
      return;
    }
    const at = this.tabs.findIndex((t) => t.id === this.activeId);
    this.tabs.splice(at < 0 ? this.tabs.length : at + 1, 0, { kind: "review", id, title, source, pinned: false });
    this.activeId = id;
  }

  register(tab: FileTab, handle: EditorHandle | null) {
    tab.handle = handle;
    if (handle && tab.pendingGoTo) {
      const g = tab.pendingGoTo;
      tab.pendingGoTo = null;
      requestAnimationFrame(() => handle.goTo(g.line, g.col, g.length));
    }
  }

  // ---- editing and saving ------------------------------------------------------------------------
  changed(tab: FileTab, dirty: boolean) {
    tab.dirty = dirty;
    tab.notice = "";
    if (dirty) this.autosave.touch(tab.path);
    else this.autosave.cancel(tab.path);
    this.autosaveDue = this.autosave.nextDue();
  }

  async save(tab: FileTab, opts: { force?: boolean; background?: boolean } = {}): Promise<boolean> {
    if (!tab.handle || tab.binary) return false;
    if (session.phase !== "ready") {
      if (opts.background) this.autosave.touch(tab.path); // try again once you're signed back in
      return false;
    }
    const text = tab.handle.getText();
    this.autosave.cancel(tab.path);
    this.autosaveDue = this.autosave.nextDue();
    try {
      const r = await session.api.save(tab.path, text, tab.deletedOnDisk ? null : tab.etag, opts.force, opts.background);
      tab.etag = r.etag;
      tab.conflict = null;
      tab.deletedOnDisk = false;
      if (tab.handle.getText() === text) {
        tab.handle.markSaved();
        tab.dirty = false;
      } else {
        this.autosave.touch(tab.path); // typed more while saving
      }
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        await this.loadConflict(tab);
        ui.toast(`${tab.title} changed on disk. Choose which version to keep.`, "error");
      } else {
        ui.error(e, `Couldn't save ${tab.title}`);
        if (opts.background) this.autosave.touch(tab.path);
      }
      return false;
    }
  }

  /** Saves every unsaved tab. True when all of them saved (each failure was already shown with its reason). */
  async saveAll(): Promise<boolean> {
    this.saving = true;
    try {
      const results = await Promise.all(this.dirtyTabs.map((t) => this.save(t)));
      const failed = results.filter((ok) => !ok).length;
      if (results.length && !failed) ui.toast(`Saved ${results.length} file${results.length > 1 ? "s" : ""}`, "ok", undefined, 1800);
      return failed === 0;
    } finally {
      this.saving = false;
    }
  }

  // ---- files changed on disk (agents) ------------------------------------------------------------
  async onDiskChange(paths: string[]) {
    for (const p of paths) {
      const tab = this.file(p);
      if (tab?.media) { tab.mediaRev++; continue; }
      if (!tab || tab.loading || tab.binary) continue;
      let f: FileContent;
      try {
        f = await session.api.read(p, true);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          tab.deletedOnDisk = true;
        }
        continue;
      }
      tab.deletedOnDisk = false;
      if (f.etag === tab.etag) continue;
      if (!tab.dirty) {
        tab.etag = f.etag;
        tab.handle?.setText(f.content, true);
        tab.handle?.markSaved();
        tab.notice = "Updated from disk (changed outside the editor)";
      } else {
        tab.conflict = { etag: f.etag, text: f.content };
      }
    }
  }

  private async loadConflict(tab: FileTab) {
    try {
      const f = await session.api.read(tab.path, true);
      tab.conflict = { etag: f.etag, text: f.content };
    } catch {
      tab.deletedOnDisk = true;
    }
  }

  async keepMine(tab: FileTab) {
    if (!tab.conflict) return;
    tab.etag = tab.conflict.etag;
    tab.conflict = null;
    await this.save(tab);
  }

  takeTheirs(tab: FileTab) {
    if (!tab.conflict) return;
    tab.etag = tab.conflict.etag;
    tab.handle?.setText(tab.conflict.text, true);
    tab.handle?.markSaved();
    tab.conflict = null;
    this.changed(tab, false);
  }

  compare(tab: FileTab) {
    if (!tab.conflict || !tab.handle) return;
    this.openReview({ type: "compare", path: tab.path, mine: tab.handle.getText(), theirs: tab.conflict.text }, `${tab.title}: disk ↔ yours`);
  }

  // ---- closing -----------------------------------------------------------------------------------
  async close(id: string, ask = true): Promise<boolean> {
    const tab = this.tabs.find((t) => t.id === id);
    if (!tab) return true;
    if (tab.kind === "file" && tab.dirty && ask) {
      const r = await ui.ask({
        title: `Save changes to ${tab.title}?`, message: "Your changes will be lost if you don't save them.",
        buttons: [{ label: "Cancel", value: "cancel" }, { label: "Don't save", value: "discard", danger: true }, { label: "Save", value: "save", primary: true }],
      });
      if (r.button === "cancel") return false;
      if (r.button === "save" && !(await this.save(tab))) return false;
    }
    if (tab.kind === "file") this.autosave.cancel(tab.path);
    this.autosaveDue = this.autosave.nextDue();
    const idx = this.tabs.indexOf(tab);
    this.tabs = this.tabs.filter((t) => t !== tab);
    if (this.activeId === id) this.activeId = (this.tabs[idx] ?? this.tabs[idx - 1])?.id ?? null;
    return true;
  }

  async closeOthers(id: string) {
    for (const t of this.tabs.filter((t) => t.id !== id)) if (!(await this.close(t.id))) return;
  }

  async closeAll() {
    for (const t of [...this.tabs]) if (!(await this.close(t.id))) return;
  }

  /** Throw away unsaved edits and reload the file from disk. */
  async revert(tab: FileTab) {
    if (tab.media) { tab.mediaRev++; return; }
    if (tab.dirty && !(await ui.confirm(`Revert ${tab.title}?`, "Your unsaved changes are thrown away and the file is reloaded from disk.", "Revert", true))) return;
    try {
      const f = await session.api.read(tab.path);
      tab.etag = f.etag;
      tab.conflict = null;
      tab.deletedOnDisk = false;
      tab.handle?.setText(f.content, true);
      tab.handle?.markSaved();
      this.changed(tab, false);
    } catch (e) {
      ui.error(e, `Couldn't reload ${tab.title}`);
    }
  }

  get activeFile(): FileTab | null {
    const t = this.active;
    return t?.kind === "file" ? t : null;
  }

  cycle(dir: 1 | -1) {
    if (!this.tabs.length) return;
    const i = this.tabs.findIndex((t) => t.id === this.activeId);
    this.activeId = this.tabs[(i + dir + this.tabs.length) % this.tabs.length].id;
  }

  /** Files renamed or deleted from the explorer. */
  renamed(src: string, dst: string) {
    for (const t of this.tabs) {
      if (t.kind !== "file") continue;
      if (t.path === src || t.path.startsWith(src + "/")) {
        const np = dst + t.path.slice(src.length);
        t.path = np; t.id = np; t.title = basename(np);
        if (this.activeId === src) this.activeId = np;
      }
    }
  }
}

export const editors = new Editors();
