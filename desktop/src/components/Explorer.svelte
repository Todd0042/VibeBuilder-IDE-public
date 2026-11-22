<script lang="ts">
  import Icon from "./Icon.svelte";
  import TreeNode from "./TreeNode.svelte";
  import ContextMenu, { type MenuItem } from "./ContextMenu.svelte";
  import { dirname } from "@core/index";
  import { tree } from "../lib/tree.svelte";
  import { ui } from "../lib/ui.svelte";
  import { editors } from "../lib/editors.svelte";
  import { terminals } from "../lib/terminals.svelte";
  import { searchRoot } from "../lib/searchRoot";
  import { session } from "../lib/session.svelte";
  import { deleteItem as remove, newItem, renameItem as rename, downloadFile } from "../lib/fileOps";

  let menu = $state<{ x: number; y: number; items: MenuItem[] } | null>(null);
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

  function openWorkspaceMenu(e: MouseEvent) {
    e.preventDefault();
    menu = {
      x: e.clientX, y: e.clientY, items: [
        ...(!ui.workspaceOpen ? [{ label: "Open Workspace", run: () => ui.openFolder("") }] : []),
        { label: "Open Terminal in Workspace", run: () => terminals.create("shell", "") },
        { label: "New Folder in Workspace…", run: () => newProject() },
        { label: "Open Folder…", run: () => (ui.folderPicker = true) },
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

  function openMenu(e: MouseEvent, path: string, kind: string) {
    e.preventDefault();
    tree.selected = path;
    const dir = kind === "dir" ? path : dirname(path);
    const isWsRoot = !path;
    menu = {
      x: e.clientX, y: e.clientY, items: [
        ...(kind === "file" ? [
          { label: "Open", run: () => editors.open(path) },
          { label: "Download", run: () => downloadFile(path) },
        ] : []),
        ...(kind === "dir" && ui.workspaceOpen ? [{ label: "Open Folder as Root", run: () => ui.openFolder(path) }] : []),
        { label: "New File…", run: () => newItem("file", dir) },
        { label: "New Folder…", run: () => newItem("dir", dir) },
        { sep: true as const },
        { label: "Search in Folder", run: () => searchRoot.set(dir) },
        { label: "Open Terminal Here", run: () => terminals.create("shell", dir) },
        { label: "Copy Path", run: () => navigator.clipboard.writeText(`/workspace/${path}`) },
        { label: "Copy Relative Path", run: () => navigator.clipboard.writeText(ui.project && path.startsWith(ui.project + "/") ? path.slice(ui.project.length + 1) : path.includes("/") ? path.slice(path.indexOf("/") + 1) : path) },
        ...(isWsRoot ? [] : [{ sep: true as const }, { label: "Rename…", hint: "F2", run: () => rename(path) },
          { label: "Delete", hint: "Del", danger: true, run: () => remove(path) }]),
      ],
    };
  }

  function key(e: KeyboardEvent) {
    const sel = tree.selected;
    if (!sel) return;
    if (e.key === "F2") { e.preventDefault(); void rename(sel); }
    if (e.key === "Delete") { e.preventDefault(); void remove(sel); }
  }

  function collapseAll() {
    tree.expanded = ui.project ? { [ui.project]: true } : {};
  }
</script>

<div class="head">
  <span class="label">EXPLORER</span>
  <div class="tools">
    <button class="icon-btn" title="New file" onclick={() => newItem("file")}><Icon name="newFile" /></button>
    <button class="icon-btn" title="New folder" onclick={() => (ui.project ? newItem("dir") : newProject())}><Icon name="newFolder" /></button>
    <button class="icon-btn" title="Refresh" onclick={() => { for (const d of Object.keys(tree.children)) void tree.load(d); void tree.refreshGit(); }}><Icon name="refresh" /></button>
    <button class="icon-btn" title="Collapse folders" onclick={collapseAll}><Icon name="collapseAll" /></button>
  </div>
</div>
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="tree" tabindex="0" role="tree" onkeydown={key}>
  <div class="ws-row" class:active={ui.workspaceOpen} role="treeitem" aria-selected={ui.workspaceOpen} aria-expanded={wsExpanded} tabindex="-1"
    onclick={() => (wsExpanded = !wsExpanded)} oncontextmenu={openWorkspaceMenu} onkeydown={() => {}}>
    <span class="chev"><Icon name={wsExpanded ? "chevronDown" : "chevronRight"} size={13} /></span>
    <span class="ico dir"><Icon name={wsExpanded ? "folderOpen" : "folder"} size={15} /></span>
    <span class="ws-name">WORKSPACE</span>
    {#if !ui.workspaceOpen}
      <button class="ws-open" title="Open Workspace root (for terminals & search)" onclick={(e) => { e.stopPropagation(); ui.openFolder(""); }}>
        Open
      </button>
    {/if}
  </div>

  {#if wsExpanded}
    {#if ui.workspaceOpen}
      {#each wsEntries as e (e.name)}
        <TreeNode path={e.name} name={e.name} kind={e.kind} depth={0} onmenu={openMenu} />
      {:else}
        <p class="faint pad">Workspace is empty. Open a terminal to start a new app.</p>
      {/each}
    {:else}
      {#if ui.project}
        <TreeNode path={ui.project} name={ui.project} kind="dir" depth={0} onmenu={openMenu} />
      {/if}
      {#each otherProjects as p (p)}
        <button class="proj-row" onclick={() => ui.openFolder(p)} oncontextmenu={(e) => openMenu(e, p, "dir")} title="Open {p}">
          <span class="chev"><Icon name="chevronRight" size={13} /></span>
          <span class="ico dir dim"><Icon name="folder" size={15} /></span>
          <span class="proj-name">{p}</span>
        </button>
      {/each}
      {#if !ui.project && !otherProjects.length}
        <p class="faint pad">No projects in the workspace yet. Click Open on Workspace to use terminals there.</p>
      {/if}
    {/if}
  {/if}
</div>

{#if menu}<ContextMenu {...menu} onclose={() => (menu = null)} />{/if}

<style>
  .head { height: 36px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 8px 0 14px; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .tools { display: flex; gap: 1px; }
  .tree { flex: 1; overflow: auto; outline: none; padding-bottom: 20px; }
  .ws-row {
    position: sticky; top: 0; z-index: 3; height: 26px; display: flex; align-items: center; gap: 4px;
    padding: 0 6px; background: var(--panel); border-bottom: 1px solid var(--line); cursor: pointer; user-select: none;
  }
  .ws-row:hover { background: #1e222b; }
  .ws-row.active { border-left: 2px solid var(--accent); padding-left: 4px; }
  .ws-name { flex: 1; font-size: 11px; font-weight: 700; letter-spacing: .06em; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ws-row.active .ws-name { color: var(--accent); }
  .ws-open {
    height: 18px; padding: 0 7px; border-radius: 4px; border: 1px solid var(--line-2);
    background: #232833; color: var(--dim); font-size: 10.5px; font-weight: 600;
  }
  .ws-open:hover { background: var(--accent-2); border-color: var(--accent-2); color: #fff; }
  .proj-row {
    width: 100%; height: 23px; display: flex; align-items: center; gap: 3px;
    padding: 0 8px 0 calc(6px + 2ch); border: 0; background: none; text-align: left; color: var(--dim);
  }
  .proj-row:hover { background: #ffffff09; color: var(--text); }
  .proj-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
  .chev { width: 14px; display: grid; place-items: center; color: var(--faint); flex: none; }
  .ico { display: grid; place-items: center; color: var(--dim); flex: none; }
  .ico.dir { color: #c9a95a; }
  .ico.dir.dim { opacity: .75; }
  .pad { padding: 12px 14px 12px calc(14px + 2ch); }
</style>
