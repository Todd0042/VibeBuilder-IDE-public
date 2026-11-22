<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "./Icon.svelte";
  import ExplorerView from "./ExplorerView.svelte";
  import EditorTabArea from "./EditorTabArea.svelte";
  import ChangesView from "./ChangesView.svelte";
  import TerminalArea from "./TerminalArea.svelte";
  import MoreView from "./MoreView.svelte";
  import QuickOpen from "./QuickOpen.svelte";
  import FolderPicker from "./FolderPicker.svelte";
  import { session } from "@state/session.svelte";
  import { ui, type MobileView } from "@state/ui.svelte";
  import { tree } from "@state/tree.svelte";
  import { editors } from "@state/editors.svelte";
  import { changes } from "@state/changes.svelte";
  import { terminals } from "@state/terminals.svelte";
  import { checkpoints } from "@state/checkpoints.svelte";
  import { problems } from "@state/problems.svelte";

  const NAV: { id: MobileView; icon: string; label: string }[] = [
    { id: "files", icon: "files", label: "Files" },
    { id: "editor", icon: "code", label: "Editor" },
    { id: "changes", icon: "changes", label: "Changes" },
    { id: "terminal", icon: "terminal", label: "Terminal" },
    { id: "more", icon: "menu", label: "More" },
  ];

  const dirtyCount = $derived(editors.dirtyTabs.length);

  async function loadProjects() {
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
    } catch (e) { ui.error(e, "Couldn't load projects"); }
  }

  async function refreshAll() {
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

  function pickTab(id: MobileView) {
    ui.mobileView = id;
    if (id === "changes") changes.unseen = 0;
    if (id === "terminal" && terminals.activeId) {
      setTimeout(() => terminals.fit(terminals.activeId!), 30);
    }
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
    const offRes = session.onResume(() => void refreshAll());
    return () => { off(); offOut(); offRes(); };
  });

  $effect(() => {
    if (session.phase === "ready") void refreshAll();
    else terminals.disconnectAll();
  });

  let lastKey = "";
  $effect(() => {
    const p = ui.project;
    const key = ui.workspaceOpen ? "__ws__" : p;
    ui.persist();
    if ((!p && !ui.workspaceOpen) || key === lastKey || session.phase !== "ready") return;
    lastKey = key;
    tree.reset();
    if (ui.workspaceOpen) {
      void tree.load("").then(() => tree.refreshGit());
      void changes.reload();
      void checkpoints.load();
    } else {
      tree.expanded[p] = true;
      void tree.load(p).then(() => tree.refreshGit());
      void changes.reload();
      void checkpoints.load();
      void checkpoints.ensureRules();
    }
  });
</script>

<div class="wb">
  <header class="top">
    <span class="conn" class:off={!session.connected} title={session.connected ? "Connected" : "Reconnecting…"}></span>
    <button class="proj" onclick={() => (ui.folderPicker = true)}>
      <Icon name="folder" size={16} />
      <span>{ui.workspaceOpen ? "Workspace" : ui.project || "Open Folder"}</span>
      <Icon name="chevronDown" size={14} />
    </button>
    {#if changes.open}
      <button class="pulse-pill" onclick={() => pickTab("changes")}>
        <span class="pulse"></span> Editing
      </button>
    {/if}
    <div class="grow"></div>
    {#if dirtyCount}
      <button class="save-all" disabled={editors.saving} onclick={() => editors.saveAll()}>
        Save <span class="cnt">{dirtyCount}</span>
      </button>
    {/if}
    <button class="icon-btn" aria-label="Go to file" onclick={() => (ui.quickOpen = true)}><Icon name="search" size={18} /></button>
    <button class="icon-btn" aria-label="Lock" onclick={() => session.lock("Locked.")}><Icon name="lock" size={18} /></button>
  </header>

  <main class="stage">
    <div class="view" class:hidden={ui.mobileView !== "files"}><ExplorerView /></div>
    <div class="view" class:hidden={ui.mobileView !== "editor"}><EditorTabArea /></div>
    <div class="view" class:hidden={ui.mobileView !== "changes"}><ChangesView /></div>
    <div class="view" class:hidden={ui.mobileView !== "terminal"}><TerminalArea /></div>
    <div class="view" class:hidden={ui.mobileView !== "more"}><MoreView /></div>
  </main>

  {#if !ui.keyboardOpen}
  <nav class="nav">
    {#each NAV as n}
      <button class="navbtn" class:on={ui.mobileView === n.id} onclick={() => pickTab(n.id)}>
        <div class="ico">
          <Icon name={n.icon} size={20} />
          {#if n.id === "changes" && changes.unseen}
            <span class="badge-dot">{changes.unseen > 9 ? "9+" : changes.unseen}</span>
          {:else if n.id === "editor" && dirtyCount}
            <span class="badge-dot">{dirtyCount}</span>
          {:else if n.id === "terminal" && terminals.list.length}
            <span class="badge-dot ok">{terminals.list.length}</span>
          {/if}
        </div>
        <span>{n.label}</span>
      </button>
    {/each}
  </nav>
  {/if}

  {#if ui.quickOpen}<QuickOpen />{/if}
  {#if ui.folderPicker}<FolderPicker />{/if}
</div>

<style>
  .wb {
    height: 100%; display: flex; flex-direction: column;
  }
  .top {
    height: 46px; flex: none; display: flex; align-items: center; gap: 6px; padding: 0 8px;
    background: #0f1116; border-bottom: 1px solid var(--line);
  }
  .conn { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); flex: none; margin-left: 2px; }
  .conn.off { background: var(--warn); animation: pulse 1s infinite; }
  .proj {
    display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 10px; max-width: 50vw;
    border-radius: 8px; border: 1px solid var(--line-2); background: #181c24; font-weight: 600; font-size: 13.5px;
  }
  .proj span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .proj :global(svg:first-child) { color: #c9a95a; flex: none; }
  .pulse-pill {
    display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 9px; border-radius: 14px;
    background: #2a2219; border: 1px solid #4a3a22; color: #ffcf8a; font-size: 12px; flex: none;
  }
  .pulse { width: 7px; height: 7px; border-radius: 50%; background: var(--save); animation: pulse 1.2s infinite; }
  @keyframes pulse { 50% { opacity: .3; } }
  .grow { flex: 1; }
  .save-all {
    display: inline-flex; align-items: center; gap: 5px; height: 32px; padding: 0 10px; border-radius: 8px;
    border: 0; background: var(--save); color: #1d1405; font-weight: 700; font-size: 13px; flex: none;
  }
  .cnt { min-width: 18px; height: 18px; padding: 0 4px; border-radius: 9px; background: #1d1405; color: var(--save-2); font-size: 11px; display: grid; place-items: center; }

  .stage { flex: 1; min-height: 0; position: relative; }
  .view { position: absolute; inset: 0; display: flex; flex-direction: column; }
  .hidden { display: none; }

  .nav {
    height: 56px; flex: none; display: grid; grid-template-columns: repeat(5, 1fr);
    background: #0f1116; border-top: 1px solid var(--line);
  }
  .navbtn {
    border: 0; background: none; color: var(--dim);
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    font-size: 11px; padding: 4px 0;
  }
  .navbtn.on { color: var(--accent); }
  .ico { position: relative; display: grid; place-items: center; }
  .badge-dot {
    position: absolute; top: -4px; right: -10px; min-width: 16px; height: 16px; padding: 0 4px;
    border-radius: 8px; background: var(--save); color: #1d1405; font-size: 10px; font-weight: 800; display: grid; place-items: center;
  }
  .badge-dot.ok { background: #2d4c2e; color: #b8e6b3; }
</style>
