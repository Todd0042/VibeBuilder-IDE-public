// Shared workspace loading, refresh, and live-event subscription for Desktop and Mobile workbenches.
import { session } from "./session.svelte";
import { ui } from "./ui.svelte";
import { tree } from "./tree.svelte";
import { editors } from "./editors.svelte";
import { changes } from "./changes.svelte";
import { terminals } from "./terminals.svelte";
import { checkpoints } from "./checkpoints.svelte";
import { problems } from "./problems.svelte";

export async function loadProjects() {
  try {
    const r = await session.api.projects();
    ui.projects = r.projects;
    ui.hiddenFolders = r.hidden ?? [];
    if (!ui.workspaceOpen && !ui.projects.includes(ui.project)) {
      let ok = false;
      if (ui.project.includes("/")) {
        try { await session.api.list(ui.project, true); ok = true; } catch { ok = false; }
      }
      if (!ok) {
        ui.recentFolders = ui.recentFolders.filter((p) => p !== ui.project);
        if (ui.projects[0]) ui.project = ui.projects[0];
        else ui.workspaceOpen = true;
      }
    }
  } catch (e) {
    ui.error(e, "Couldn't load projects");
  }
}

export async function refreshWorkspace() {
  await loadProjects();
  if (ui.workspaceOpen) {
    if (!tree.children[""]) await tree.load("");
    else for (const d of Object.keys(tree.children)) void tree.load(d, true);
    void tree.refreshGit();
  } else if (ui.project) {
    if (!tree.children[ui.project]) await tree.load(ui.project);
    else for (const d of Object.keys(tree.children)) void tree.load(d, true);
    tree.expanded[ui.project] = true;
    void tree.refreshGit();
  }
  void changes.reload();
  void checkpoints.load();
  void problems.load();
  void terminals.refresh();
  void editors.onDiskChange(editors.tabs.filter((t) => t.kind === "file").map((t) => (t as { path: string }).path));
}

export function subscribeWorkspaceLive() {
  return session.onLive((e) => {
    if (e.event === "fs") {
      tree.onDiskChange(e.paths);
      void editors.onDiskChange(e.paths);
      if (e.paths.some((p) => !p.includes("/"))) void loadProjects();
    } else if (e.event === "changeset") {
      changes.onClosed(e);
      tree.scheduleGit(100);
    } else if (e.event === "changeset.open") {
      changes.onOpened(e.id, e.started);
    } else if (e.event === "terminals") {
      void terminals.refresh();
    } else if (e.event === "problem") {
      problems.onProblem(e);
    } else if (e.event === "checkpoint") {
      checkpoints.onCheckpoint(e);
      tree.scheduleGit(100);
    }
  });
}
