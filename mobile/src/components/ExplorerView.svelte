<script lang="ts">
  import Icon from "./Icon.svelte";
  import TreeNode from "./TreeNode.svelte";
  import ActionSheet, { type SheetItem } from "./ActionSheet.svelte";
  import { dirname } from "@core/index";
  import { tree } from "@state/tree.svelte";
  import { ui } from "@state/ui.svelte";
  import { editors } from "@state/editors.svelte";
  import { terminals } from "@state/terminals.svelte";
  import { searchRoot } from "@state/searchRoot";
  import { session } from "@state/session.svelte";
  import { deleteItem as remove, newItem, renameItem as rename, downloadFile } from "@state/fileOps";

  let sheet = $state<{ title: string; items: SheetItem[] } | null>(null);
  let wsExpanded = $state(true);

  const wsEntries = $derived(tree.children[""] ?? []);
  const otherProjects = $derived(
    ui.projects.filter((p) => p !== ui.project && !ui.hiddenFolders.includes(p))
  );

  async function newProject() {
    const raw = await ui.prompt("New folder in /workspace", "", "folder-name");
    const name = raw?.replace(/^\/+|\/+$/g, "");
    if (!name) return;
    try {
      await session.api.create(name, "dir");
      const r = await session.api.projects();
      ui.projects = r.projects;
      ui.hiddenFolders = r.hidden ?? [];
      if (ui.workspaceOpen) await tree.load("");
      else ui.openFolder(name);
    } catch (e) {
      ui.error(e);
    }
  }

  function openWorkspaceMenu() {
    sheet = {
      title: "/workspace",
      items: [
        ...(!ui.workspaceOpen ? [{ label: "Open Workspace", run: () => ui.openFolder("") }] : []),
        { label: "Open Shell in Workspace", run: () => terminals.create("shell", "") },
        { label: "New Folder in Workspace…", run: () => newProject() },
        { label: "Browse All Folders…", run: () => (ui.folderPicker = true) },
        { sep: true as const },
        { label: "Refresh", run: async () => {
          const r = await session.api.projects();
          ui.projects = r.projects;
          ui.hiddenFolders = r.hidden ?? [];
          if (ui.workspaceOpen) await tree.load("");
        } },
      ],
    };
  }

  function openMenu(path: string, kind: string) {
    const dir = kind === "dir" ? path : dirname(path);
    const isWsRoot = !path;
    sheet = {
      title: path,
      items: [
        ...(kind === "file" ? [
          { label: "Open in Editor", run: () => editors.open(path) },
          { label: "Download", run: () => downloadFile(path) },
        ] : []),
        ...(kind === "dir" && ui.workspaceOpen ? [{ label: "Open Folder as Root", run: () => ui.openFolder(path) }] : []),
        { label: "New File…", run: () => newItem("file", dir) },
        { label: "New Folder…", run: () => newItem("dir", dir) },
        { sep: true as const },
        { label: "Search in Folder", run: () => { searchRoot.set(dir); ui.mobileView = "more"; ui.mobileMore = "search"; } },
        { label: "Open Shell Here", run: () => terminals.create("shell", dir) },
        { label: "Copy Path", run: () => navigator.clipboard?.writeText(`/workspace/${path}`) },
        ...(isWsRoot ? [] : [
          { sep: true as const },
          { label: "Rename…", run: () => rename(path) },
          { label: "Delete", danger: true, run: () => remove(path) },
        ]),
      ],
    };
  }
</script>

<div class="explorer">
  <div class="bar">
    <span class="title">EXPLORER</span>
    {#if tree.branch}
      <span class="branch"><Icon name="branch" size={13} /> {tree.branch}</span>
    {/if}
    <div class="grow"></div>
    <button class="icon-btn" title="New file" onclick={() => newItem("file")}><Icon name="newFile" size={18} /></button>
    <button class="icon-btn" title="New folder" onclick={() => (ui.project ? newItem("dir") : newProject())}><Icon name="newFolder" size={18} /></button>
    <button class="icon-btn" title="Refresh" onclick={() => { for (const d of Object.keys(tree.children)) void tree.load(d); void tree.refreshGit(); }}>
      <Icon name="refresh" size={18} />
    </button>
    <button class="icon-btn" title="Collapse" onclick={() => (tree.expanded = ui.project ? { [ui.project]: true } : {})}><Icon name="collapseAll" size={18} /></button>
  </div>

  <div class="list">
    <div class="ws-row" class:active={ui.workspaceOpen}>
      <button class="ws-main" onclick={() => (wsExpanded = !wsExpanded)}>
        <span class="chev"><Icon name={wsExpanded ? "chevronDown" : "chevronRight"} size={15} /></span>
        <span class="ficon"><Icon name={wsExpanded ? "folderOpen" : "folder"} size={16} /></span>
        <span class="ws-name">Workspace</span>
      </button>
      {#if !ui.workspaceOpen}
        <button class="btn small ws-open" onclick={() => ui.openFolder("")}>Open</button>
      {/if}
      <button class="ws-more" aria-label="Workspace actions" onclick={openWorkspaceMenu}>
        <Icon name="more" size={16} />
      </button>
    </div>

    {#if wsExpanded}
      {#if ui.workspaceOpen}
        {#each wsEntries as e (e.name)}
          <TreeNode path={e.name} name={e.name} kind={e.kind} depth={0} onmenu={openMenu} />
        {:else}
          <p class="faint pad">Workspace is empty. Open a Terminal to start a new app.</p>
        {/each}
      {:else}
        {#if ui.project}
          <TreeNode path={ui.project} name={ui.project} kind="dir" depth={0} onmenu={openMenu} />
        {/if}
        {#each otherProjects as p (p)}
          <div class="proj-row">
            <button class="proj-main" onclick={() => ui.openFolder(p)}>
              <span class="chev"><Icon name="chevronRight" size={15} /></span>
              <span class="ficon dim"><Icon name="folder" size={16} /></span>
              <span class="proj-name">{p}</span>
            </button>
            <button class="more" aria-label="Project actions" onclick={(e) => { e.stopPropagation(); openMenu(p, "dir"); }}>
              <Icon name="more" size={16} />
            </button>
          </div>
        {/each}
        {#if !ui.project && !otherProjects.length}
          <p class="faint pad">No projects in /workspace yet. Tap Open on Workspace to use terminals there.</p>
        {/if}
      {/if}
    {/if}
  </div>
</div>

{#if sheet}<ActionSheet {...sheet} onclose={() => (sheet = null)} />{/if}

<style>
  .explorer { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .bar { height: 42px; flex: none; display: flex; align-items: center; gap: 6px; padding: 0 8px 0 14px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .title { font-size: 11.5px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .branch { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--dim); background: #232833; padding: 2px 8px; border-radius: 10px; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .grow { flex: 1; }
  .list { flex: 1; overflow: auto; padding-bottom: 24px; }
  .ws-row {
    position: sticky; top: 0; z-index: 3; display: flex; align-items: center; gap: 4px; min-height: 42px;
    padding: 0 4px 0 10px; background: var(--bg); border-bottom: 1px solid var(--line);
  }
  .ws-row.active { border-left: 3px solid var(--accent); padding-left: 7px; }
  .ws-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 7px; border: 0; background: none; padding: 6px 4px; text-align: left; }
  .ws-name { font-weight: 700; font-size: 14px; color: var(--text); }
  .ws-row.active .ws-name { color: var(--accent); }
  .ws-open { min-height: 28px; padding: 0 10px; font-size: 12px; flex: none; }
  .ws-more {
    width: 36px; height: 36px; display: grid; place-items: center;
    border: 0; background: none; color: var(--dim); border-radius: 8px; flex: none;
  }
  .ws-more:active { background: #ffffff14; color: var(--text); }
  .proj-row {
    display: flex; align-items: center; min-height: 40px;
    padding-left: calc(10px + 2ch); padding-right: 4px; border-bottom: 1px solid #ffffff05;
  }
  .proj-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 7px; border: 0; background: none; padding: 6px 4px; text-align: left; color: var(--dim); }
  .proj-main:active { color: var(--text); }
  .proj-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
  .chev { width: 16px; display: grid; place-items: center; color: var(--dim); flex: none; }
  .ficon { display: grid; color: #c9a95a; flex: none; }
  .ficon.dim { opacity: .75; }
  .pad { padding: 14px 16px 14px calc(16px + 2ch); }
</style>
