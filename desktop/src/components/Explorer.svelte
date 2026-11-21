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
  import { deleteItem as remove, newItem, renameItem as rename } from "../lib/fileOps";

  let menu = $state<{ x: number; y: number; items: MenuItem[] } | null>(null);

  function openMenu(e: MouseEvent, path: string, kind: string) {
    e.preventDefault();
    tree.selected = path;
    const dir = kind === "dir" ? path : dirname(path);
    const isRoot = path === ui.project;
    menu = {
      x: e.clientX, y: e.clientY, items: [
        ...(kind === "file" ? [{ label: "Open", run: () => editors.open(path) }] : []),
        { label: "New File…", run: () => newItem("file", dir) },
        { label: "New Folder…", run: () => newItem("dir", dir) },
        { sep: true as const },
        { label: "Search in Folder", run: () => searchRoot.set(dir) },
        { label: "Open Terminal Here", run: () => terminals.create("shell", dir) },
        { label: "Copy Path", run: () => navigator.clipboard.writeText(`/workspace/${path}`) },
        { label: "Copy Relative Path", run: () => navigator.clipboard.writeText(path.split("/").slice(1).join("/")) },
        ...(isRoot ? [] : [{ sep: true as const }, { label: "Rename…", hint: "F2", run: () => rename(path) },
          { label: "Delete", hint: "Del", danger: true, run: () => remove(path) }]),
      ],
    };
  }

  function key(e: KeyboardEvent) {
    const sel = tree.selected;
    if (!sel || sel === ui.project) return;
    if (e.key === "F2") { e.preventDefault(); void rename(sel); }
    if (e.key === "Delete") { e.preventDefault(); void remove(sel); }
  }

  function collapseAll() {
    tree.expanded = { [ui.project]: true };
  }

</script>

<div class="head">
  <span class="label">EXPLORER</span>
  <div class="tools">
    <button class="icon-btn" title="New file" onclick={() => newItem("file")}><Icon name="newFile" /></button>
    <button class="icon-btn" title="New folder" onclick={() => newItem("dir")}><Icon name="newFolder" /></button>
    <button class="icon-btn" title="Refresh" onclick={() => { for (const d of Object.keys(tree.children)) void tree.load(d); void tree.refreshGit(); }}><Icon name="refresh" /></button>
    <button class="icon-btn" title="Collapse folders" onclick={collapseAll}><Icon name="collapseAll" /></button>
  </div>
</div>
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="tree" tabindex="0" role="tree" onkeydown={key}>
  {#if ui.project}
    <TreeNode path={ui.project} name={ui.project} kind="dir" depth={0} onmenu={openMenu} />
  {:else}
    <p class="faint pad">No projects in the workspace yet. Make a folder in /workspace (or clone a repo from a terminal).</p>
  {/if}
</div>

{#if menu}<ContextMenu {...menu} onclose={() => (menu = null)} />{/if}

<style>
  .head { height: 36px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 8px 0 14px; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .tools { display: flex; gap: 1px; }
  .tree { flex: 1; overflow: auto; outline: none; padding-bottom: 20px; }
  .pad { padding: 12px 14px; }
</style>
