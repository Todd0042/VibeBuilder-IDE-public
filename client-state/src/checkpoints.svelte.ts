// Checkpoint commits for the open project and one-time starter agent rules.
import type { CheckpointInfo, CheckpointResult, CheckpointRun } from "@core/index";
import { relativeTime } from "@core/index";
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";
import { editors } from "./editors.svelte";

const topProject = (folder: string) => folder.split("/")[0];

class CheckpointsState {
  project = $state("");
  info = $state<CheckpointInfo | null>(null);
  busy = $state(false);
  private warned = new Set<string>();
  private rulesAsked = new Set<string>();

  async load() {
    const p = topProject(ui.project);
    this.project = p;
    if (!p) { this.info = null; return; }
    try {
      const info = await session.api.checkpoints(p);
      if (p === this.project) this.info = info;
    } catch {
      if (p === this.project) this.info = null;
    }
  }

  onCheckpoint(e: { project: string } & CheckpointRun) {
    if (e.project === this.project && this.info) this.info = { ...this.info, pending_since: null, last: { at: e.at, results: e.results } };
    this.notify(e.results);
  }

  async setEnabled(on: boolean) {
    if (!this.project) return;
    try {
      this.info = await session.api.setCheckpoints(this.project, on);
      ui.toast(on ? `Checkpoints on for ${this.project}.` : `Checkpoints off for ${this.project}.`, "ok");
    } catch (e) {
      ui.error(e, "Couldn't change checkpoints");
    }
  }

  async now() {
    if (!this.project || this.busy) return;
    this.busy = true;
    try {
      const run = await session.api.checkpointNow(this.project);
      if (this.info) this.info = { ...this.info, pending_since: null, last: run };
      const done = run.results.filter((r) => r.status === "committed");
      if (done.length) ui.toast(`Checkpoint: ${done[0].title}`, "ok");
      else if (!run.results.length) ui.toast("This project isn't a git repository, so there's nothing to checkpoint.");
      else if (run.results.every((r) => r.status === "unchanged")) ui.toast("Nothing changed since the last checkpoint.");
      this.notify(run.results);
    } catch (e) {
      ui.error(e, "Couldn't make a checkpoint");
    } finally {
      this.busy = false;
    }
  }

  get label(): string {
    const i = this.info;
    if (!i) return "";
    if (!i.enabled) return "Checkpoints off";
    const made = i.last?.results.find((r) => r.status === "committed");
    return made && i.last ? `Checkpoint ${relativeTime(i.last.at)}` : "No checkpoint yet";
  }

  get detail(): string {
    const r = this.info?.last?.results[0];
    if (!this.info?.enabled) return "Automatic checkpoint commits are off for this project (turn them on in Devices & Settings).";
    if (!r) return "When changes settle, the work in progress is committed to the branch checkpoints/<branch>. Tap to checkpoint now.";
    const what = r.status === "committed" ? `${r.title}\non ${r.ref}` : r.status === "skipped" ? `Skipped: ${r.reason}`
      : r.status === "failed" ? `Failed: ${r.reason}` : "Nothing had changed.";
    return `${what}\n\nTap to checkpoint now.`;
  }

  async ensureRules() {
    const p = topProject(ui.project);
    if (!p || this.rulesAsked.has(p)) return;
    this.rulesAsked.add(p);
    try {
      const { created, failed } = await session.api.ensureAgentRules(p);
      if (created.length) {
        ui.toast(`Added starter agent rules to ${p} (AGENTS.md): security, file size, commits, testing. Edit them, or delete the file if you don't want them.`,
          "info", { label: "Open", run: () => void editors.open(created[0]) }, 12000);
      }
      if (failed?.length) ui.toast(`Couldn't add the starter agent rules to ${p}: ${failed.map((f) => `${f.path} (${f.reason})`).join(", ")}`, "error");
    } catch (e) {
      this.rulesAsked.delete(p);
      ui.error(e, `Couldn't check ${p} for agent rules`);
    }
  }

  private notify(results: CheckpointResult[]) {
    for (const r of results) {
      if (r.status === "failed") ui.toast(`Checkpoint failed${r.repo ? ` in ${r.repo}` : ""}: ${r.reason}`, "error");
      const fresh = r.left_out.filter((x) => !this.warned.has(`${r.repo}/${x.path}`));
      for (const x of fresh) this.warned.add(`${r.repo}/${x.path}`);
      if (fresh.length) {
        const names = fresh.slice(0, 3).map((x) => `${x.path} (${x.reason})`).join(", ") + (fresh.length > 3 ? ` and ${fresh.length - 3} more` : "");
        ui.toast(`Left out of the checkpoint: ${names}. If it holds secrets, add it to .gitignore so it's never committed.`, "info", undefined, 12000);
      }
    }
  }
}

export const checkpoints = new CheckpointsState();
