// The explorer: folders load when opened, refresh when something changes on disk, and carry git
// status colours (modified, added, untracked) from the builder.
import { dirname, type DirEntry } from "@core/index";
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";

class TreeState {
  children = $state<Record<string, DirEntry[]>>({});
  expanded = $state<Record<string, boolean>>({});
  selected = $state<string | null>(null);
  git = $state<Record<string, string>>({});
  branch = $state("");
  gitError = $state("");
  ahead = $state(0);
  behind = $state(0);
  private pending = new Set<string>();
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;
  private gitTimer: ReturnType<typeof setTimeout> | null = null;

  reset() {
    this.children = {};
    this.expanded = {};
    this.selected = null;
    this.git = {};
    this.branch = "";
  }

  async load(path: string, background = false) {
    try {
      const r = await session.api.list(path, background);
      this.children[path] = r.entries;
    } catch (e) {
      if (!background) ui.error(e);
      delete this.children[path];
    }
  }

  async toggle(path: string) {
    if (this.expanded[path]) {
      this.expanded[path] = false;
      return;
    }
    this.expanded[path] = true;
    if (!this.children[path]) await this.load(path);
  }

  async reveal(path: string) {
    const parts = path.split("/");
    for (let i = 1; i < parts.length; i++) {
      const dir = parts.slice(0, i).join("/");
      this.expanded[dir] = true;
      if (!this.children[dir]) await this.load(dir);
    }
    this.selected = path;
  }

  onDiskChange(paths: string[]) {
    for (const p of paths) {
      this.pending.add(dirname(p));
      this.pending.add(p);
    }
    if (this.refreshTimer) return;
    this.refreshTimer = setTimeout(() => {
      this.refreshTimer = null;
      const dirs = [...this.pending].filter((d) => this.children[d] !== undefined);
      this.pending.clear();
      for (const d of dirs) void this.load(d, true);
      this.scheduleGit();
    }, 300);
  }

  scheduleGit(delay = 600) {
    if (this.gitTimer) clearTimeout(this.gitTimer);
    this.gitTimer = setTimeout(() => void this.refreshGit(), delay);
  }

  async refreshGit() {
    const project = ui.project;
    if (!project) {
      this.git = {};
      this.branch = "";
      this.gitError = "";
      this.ahead = 0;
      this.behind = 0;
      return;
    }
    try {
      const g = await session.api.gitStatus(project);
      if (project !== ui.project) return;
      const map: Record<string, string> = {};
      if (g.repo) {
        const root = g.root ?? project;
        for (const f of g.files ?? []) {
          const full = root ? `${root}/${f.path}` : f.path;
          map[full] = f.xy;
          let d = dirname(full);
          while (d && d !== project && !map[d]) { map[d] = "dir"; d = dirname(d); }
        }
      }
      this.git = map;
      this.branch = g.repo ? g.branch ?? "" : "";
      this.gitError = g.error ?? "";
      this.ahead = g.ahead ?? 0;
      this.behind = g.behind ?? 0;
    } catch (e) {
      this.gitError = `Couldn't get git status from the builder: ${e instanceof Error ? e.message : String(e)}`;
    }
  }
}

export const tree = new TreeState();

export function gitClass(xy: string | undefined): string {
  if (!xy) return "";
  if (xy === "dir") return "git-dir";
  if (xy === "??") return "git-untracked";
  if (xy.includes("A")) return "git-added";
  if (xy.includes("D")) return "git-deleted";
  if (xy.includes("U")) return "git-conflict";
  return "git-modified";
}

export function gitLetter(xy: string | undefined): string {
  if (!xy || xy === "dir") return "";
  if (xy === "??") return "U";
  if (xy.includes("U")) return "!";
  for (const c of ["A", "D", "R", "M"]) if (xy.includes(c)) return c;
  return "M";
}
