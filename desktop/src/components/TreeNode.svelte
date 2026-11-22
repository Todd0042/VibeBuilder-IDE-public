<script lang="ts">
  import Icon from "./Icon.svelte";
  import TreeNode from "./TreeNode.svelte";
  import { tree, gitClass, gitLetter } from "../lib/tree.svelte";
  import { editors } from "../lib/editors.svelte";
  import { fileColor } from "../lib/fileIcons";

  let { path, name, kind, depth, onmenu }:
    { path: string; name: string; kind: string; depth: number; onmenu: (e: MouseEvent, path: string, kind: string) => void } = $props();

  const open = $derived(!!tree.expanded[path]);
  const kids = $derived(tree.children[path]);
  const git = $derived(tree.git[path]);
  const active = $derived(editors.activeId === path);

  function click(e: MouseEvent) {
    tree.selected = path;
    if (kind === "dir") void tree.toggle(path);
    else if (kind === "file") void editors.open(path);
    (e.currentTarget as HTMLElement).closest<HTMLElement>("[role=tree]")?.focus();
  }
</script>

<div class="row" class:sel={tree.selected === path} class:active class:root={depth === 0} style:padding-left="calc(6px + 2ch + {depth * 12}px)"
  role="treeitem" aria-selected={tree.selected === path} aria-expanded={kind === "dir" ? open : undefined} tabindex="-1"
  onclick={click} oncontextmenu={(e) => onmenu(e, path, kind)} onkeydown={() => {}}
  title={kind === "symlink" ? "Symlink: the IDE doesn't follow links (open the target instead)" : path}>
  {#if kind === "dir"}
    <span class="chev"><Icon name={open ? "chevronDown" : "chevronRight"} size={13} /></span>
    <span class="ico dir"><Icon name={open ? "folderOpen" : "folder"} size={15} /></span>
  {:else}
    <span class="chev"></span>
    <span class="ico" style:color={fileColor(name)}><Icon name="file" size={14} /></span>
  {/if}
  <span class="name {gitClass(git)}" class:link={kind === "symlink"}>{depth === 0 ? name.slice(name.lastIndexOf("/") + 1).toUpperCase() : name}</span>
  {#if gitLetter(git)}<span class="git {gitClass(git)}">{gitLetter(git)}</span>{/if}
</div>

{#if kind === "dir" && open && kids}
  {#each kids as e (e.name)}
    <TreeNode path="{path}/{e.name}" name={e.name} kind={e.kind} depth={depth + 1} {onmenu} />
  {/each}
  {#if kids.length === 0}<div class="empty" style:padding-left="calc(26px + 2ch + {(depth + 1) * 12}px)">empty</div>{/if}
{/if}

<style>
  .row { height: 23px; display: flex; align-items: center; gap: 3px; padding-right: 8px; cursor: pointer; white-space: nowrap; user-select: none; }
  .row:hover { background: #ffffff09; }
  .row.active { background: #ffffff0f; }
  .row.sel { background: #2a3a5a88; outline: 1px solid #4d8df066; outline-offset: -1px; }
  .row.root .name { font-size: 11px; font-weight: 700; letter-spacing: .06em; }
  .chev { width: 14px; display: grid; place-items: center; color: var(--faint); flex: none; }
  .ico { display: grid; place-items: center; color: var(--dim); flex: none; }
  .ico.dir { color: #c9a95a; }
  .name { overflow: hidden; text-overflow: ellipsis; flex: 1; }
  .name.link { font-style: italic; color: var(--faint); }
  .git { font: 600 10.5px var(--mono); flex: none; }
  .empty { height: 22px; line-height: 22px; color: var(--faint); font-style: italic; font-size: 12px; }
</style>
