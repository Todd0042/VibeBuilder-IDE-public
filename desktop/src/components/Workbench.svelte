<script lang="ts">
  import { onMount } from "svelte";
  import TitleBar from "./TitleBar.svelte";
  import ActivityBar from "./ActivityBar.svelte";
  import Explorer from "./Explorer.svelte";
  import SearchView from "./SearchView.svelte";
  import ChangesView from "./ChangesView.svelte";
  import DevicesView from "./DevicesView.svelte";
  import EditorArea from "./EditorArea.svelte";
  import TerminalPanel from "./TerminalPanel.svelte";
  import StatusBar from "./StatusBar.svelte";
  import QuickOpen from "./QuickOpen.svelte";
  import FolderPicker from "./FolderPicker.svelte";
  import Splitter from "./Splitter.svelte";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";
  import { tree } from "../lib/tree.svelte";
  import { editors } from "../lib/editors.svelte";
  import { changes } from "../lib/changes.svelte";
  import { terminals } from "../lib/terminals.svelte";
  import { checkpoints } from "../lib/checkpoints.svelte";
  import { problems } from "../lib/problems.svelte";
  import { focusIn, keyName, restoreZoom, runShortcut } from "../lib/commands";

  async function loadProjects() {
    try {
      ui.projects = (await session.api.projects()).projects;
      if (!ui.projects.includes(ui.project)) {
        // a nested folder from Open Folder: keep it if it still exists
        let ok = false;
        if (ui.project.includes("/")) {
          try { await session.api.list(ui.project, true); ok = true; } catch { ok = false; }
        }
        if (!ok) {
          ui.recentFolders = ui.recentFolders.filter((p) => p !== ui.project);
          ui.project = ui.projects[0] ?? "";
        }
      }
    } catch (e) {
      ui.error(e, "Couldn't load projects");
    }
  }

  async function refreshAll() {
    await loadProjects();
    if (ui.project) {
      if (!tree.children[ui.project]) await tree.load(ui.project);
      else for (const d of Object.keys(tree.children)) void tree.load(d, true);
      tree.expanded[ui.project] = true;
      void tree.refreshGit();
    }
    void changes.reload();
    void checkpoints.load();
    void problems.load();
    void terminals.refresh();
    // anything that changed while locked
    void editors.onDiskChange(editors.tabs.filter((t) => t.kind === "file").map((t) => (t as { path: string }).path));
  }

  onMount(() => {
    const off = session.onLive((e) => {
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
    const offOut = session.onSignedOut(() => terminals.disconnectAll());
    return () => { off(); offOut(); };
  });

  // Each time you sign in (first time, or after a lock): reload what's on screen.
  $effect(() => {
    if (session.phase === "ready") void refreshAll();
    else terminals.disconnectAll();
  });

  let lastProject = "";
  $effect(() => {
    const p = ui.project;
    ui.persist();
    if (!p || p === lastProject || session.phase !== "ready") return;
    lastProject = p;
    tree.reset();
    tree.expanded[p] = true;
    void tree.load(p).then(() => tree.refreshGit());
    void changes.reload();
    void checkpoints.load();
    void checkpoints.ensureRules();
  });

  function key(e: KeyboardEvent) {
    if (session.phase !== "ready" || ui.dialog) return;
    // In a terminal, plain Ctrl+letter belongs to the shell (Ctrl+W, Ctrl+P, Ctrl+B, Ctrl+N …).
    if (focusIn() === "terminal" && /^Ctrl\+[A-Z]$/.test(keyName(e))) return;
    runShortcut(e);
  }

  onMount(restoreZoom);
</script>

<svelte:window onkeydowncapture={key} />

<div class="wb">
  <TitleBar />
  <div class="body">
    <ActivityBar />
    {#if ui.sideOpen}
      <aside class="side" style:width="{ui.sideWidth}px">
        <div class="side-inner" class:hidden={ui.side !== "explorer"}><Explorer /></div>
        <div class="side-inner" class:hidden={ui.side !== "search"}><SearchView /></div>
        <div class="side-inner" class:hidden={ui.side !== "changes"}><ChangesView /></div>
        {#if ui.side === "devices"}<div class="side-inner"><DevicesView /></div>{/if}
      </aside>
      <Splitter dir="x" value={ui.sideWidth} min={180} max={700} onchange={(v) => { ui.sideWidth = v; ui.persist(); }} />
    {/if}
    <main class="main">
      <section class="editor" class:hidden={ui.panelOpen && ui.panelMax}><EditorArea /></section>
      {#if ui.panelOpen}
        {#if !ui.panelMax}
          <Splitter dir="y" value={ui.panelHeight} min={120} max={1400} invert onchange={(v) => { ui.panelHeight = v; ui.persist(); }} />
        {/if}
        <section class="panel" style:height={ui.panelMax ? "100%" : `${ui.panelHeight}px`}><TerminalPanel /></section>
      {/if}
    </main>
  </div>
  <StatusBar />
  {#if ui.quickOpen}<QuickOpen />{/if}
  {#if ui.folderPicker}<FolderPicker />{/if}
</div>

<style>
  .wb { height: 100%; display: flex; flex-direction: column; }
  .body { flex: 1; min-height: 0; display: flex; }
  .side { flex: none; background: var(--panel); border-right: 1px solid var(--line); min-width: 0; position: relative; }
  .side-inner { position: absolute; inset: 0; display: flex; flex-direction: column; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .editor { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .panel { flex: none; min-height: 0; border-top: 1px solid var(--line); background: var(--editor-bg); display: flex; flex-direction: column; }
  .hidden { display: none !important; }
</style>
