// Problems the server hit in the background (server/src/vbide/problems.py): shown in the status bar and the
// Devices view, and as a notice when a new one arrives.
import type { Problem } from "@core/index";
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";

class ProblemsState {
  items = $state<Problem[]>([]);

  async load() {
    try {
      this.items = (await session.api.problems()).problems;
    } catch (e) {
      ui.error(e, "Couldn't load the problem list");
    }
  }

  /** Live "problem" event: new, or back after a while. */
  onProblem(p: Problem) {
    this.items = [p, ...this.items.filter((i) => i.key !== p.key)];
    ui.toast(`${p.message}${p.fix ? ` Fix: ${p.fix}` : ""}`, "error", { label: "Details", run: () => { ui.side = "devices"; ui.sideOpen = true; } }, 12000);
  }

  async dismiss(key: string) {
    try {
      await session.api.dismissProblem(key);
      this.items = this.items.filter((i) => i.key !== key);
    } catch (e) {
      ui.error(e, "Couldn't dismiss it");
    }
  }
}

export const problems = new ProblemsState();
