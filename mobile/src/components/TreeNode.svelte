<script lang="ts">
  import Icon from "./Icon.svelte";
  import TreeNode from "./TreeNode.svelte";
  import { tree, gitClass, gitLetter } from "@state/tree.svelte";
  import { editors } from "@state/editors.svelte";
  import { fileColor } from "@state/fileIcons";
  import { join } from "@core/index";

  let { path, name, kind, depth, onmenu }: {
    path: string; name: string; kind: string; depth: number;
    onmenu: (path: string, kind: string) => void;
  } = $props();

  const expanded = $derived(!!tree.expanded[path]);
  const children = $derived(tree.children[path] ?? []);
  const selected = $derived(tree.selected === path);
  const gxy = $derived(tree.git[path]);
  const letter = $derived(gitLetter(gxy));

  function tap() {
    tree.selected = path;
    if (kind === "dir") void tree.toggle(path);
    else void editors.open(path);
  }
</script>

<div class="row" class:selected style:padding-left="calc(10px + 2ch + {depth * 16}px)">
  <button class="main" onclick={tap}>
    {#if kind === "dir"}
      <span class="chev"><Icon name={expanded ? "chevronDown" : "chevronRight"} size={15} /></span>
      <span class="ficon"><Icon name={expanded ? "folderOpen" : "folder"} size={16} /></span>
    {:else}
      <span class="chev"></span>
      <span class="dot" style:background={fileColor(name)}></span>
    {/if}
    <span class="name {gitClass(gxy)}">{depth === 0 ? name.slice(name.lastIndexOf("/") + 1) : name}</span>
    {#if letter}<span class="git {gitClass(gxy)}">{letter}</span>{/if}
  </button>
  <button class="more" aria-label="File actions" onclick={(e) => { e.stopPropagation(); tree.selected = path; onmenu(path, kind); }}>
    <Icon name="more" size={16} />
  </button>
</div>

{#if kind === "dir" && expanded}
  {#each children as ch (ch.name)}
    <TreeNode path={join(path, ch.name)} name={ch.name} kind={ch.kind} depth={depth + 1} {onmenu} />
  {/each}
{/if}

<style>
  .row { display: flex; align-items: center; min-height: 40px; padding-right: 4px; border-bottom: 1px solid #ffffff05; }
  .row.selected { background: #26334d; }
  .main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 7px; border: 0; background: none; padding: 6px 4px; text-align: left; }
  .chev { width: 16px; display: grid; place-items: center; color: var(--dim); flex: none; }
  .ficon { display: grid; color: #c9a95a; flex: none; }
  .dot { width: 9px; height: 9px; border-radius: 2px; flex: none; margin: 0 3px; }
  .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
  .git { font: 700 11px var(--mono); padding: 0 6px; flex: none; }
  .more { width: 38px; height: 38px; display: grid; place-items: center; border: 0; background: none; color: var(--dim); border-radius: 8px; flex: none; }
  .more:active { background: #ffffff14; color: var(--text); }
</style>
