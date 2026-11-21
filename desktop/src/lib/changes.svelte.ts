// The Changes list: change sets made by agents (newest first), and whether one is in progress now.
import type { ChangesetSummary } from "@core/index";
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";

class ChangesState {
  items = $state<ChangesetSummary[]>([]);
  open = $state<{ id: number; started: number; files: number } | null>(null);
  loading = $state(false);
  more = $state(true);
  allProjects = $state(false);
  unseen = $state(0);

  private filter() {
    return this.allProjects ? "" : ui.project;
  }

  async reload() {
    this.loading = true;
    try {
      const r = await session.api.changesets({ limit: 40, project: this.filter() }, true);
      this.items = r.changesets;
      this.open = r.open;
      this.more = r.changesets.length === 40;
    } catch {
      /* shown as empty */
    } finally {
      this.loading = false;
    }
  }

  async loadMore() {
    const last = this.items.at(-1);
    if (!last || this.loading) return;
    this.loading = true;
    try {
      const r = await session.api.changesets({ before: last.id, limit: 40, project: this.filter() });
      this.items = [...this.items, ...r.changesets];
      this.more = r.changesets.length === 40;
    } finally {
      this.loading = false;
    }
  }

  onClosed(cs: Partial<ChangesetSummary>) {
    this.open = null;
    if (cs.source !== "you") {
      if (!(ui.side === "changes" && ui.sideOpen)) this.unseen++;
      void this.reload();
    }
  }

  onOpened(id: number, started: number) {
    this.open = { id, started, files: 0 };
  }
}

export const changes = new ChangesState();

export const SOURCE_LABEL: Record<string, string> = {
  claude: "Claude", agy: "agy", shell: "Shell", unknown: "Outside the IDE", offline: "While the server was off",
  restore: "Restore", you: "You", agent: "Agent",
};
