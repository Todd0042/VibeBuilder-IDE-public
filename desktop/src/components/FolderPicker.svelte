<script lang="ts">
  // File → Open Folder: browse the workspace's folders and open one (any depth) as the explorer's
  // root. Double-click or Enter goes into a folder; "Open" opens the folder you're in.
  import { onMount, tick } from "svelte";
  import Icon from "./Icon.svelte";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";

  let path = $state(ui.project.includes("/") ? ui.project.slice(0, ui.project.lastIndexOf("/")) : "");
  let dirs = $state<string[]>([]);
  let sel = $state(0);
  let loading = $state(false);
  let error = $state("");
  let filter = $state("");
  let input: HTMLInputElement | undefined = $state();

  const crumbs = $derived(path ? path.split("/") : []);
  const shown = $derived(filter ? dirs.filter((d) => d.toLowerCase().includes(filter.toLowerCase())) : dirs);

  async function load(p: string) {
    loading = true;
    error = "";
    try {
      const r = await session.api.list(p);
      dirs = r.entries.filter((e) => e.kind === "dir" && e.name !== ".git").map((e) => e.name);
      path = p;
      sel = 0;
      filter = "";
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
      void tick().then(() => input?.focus());
    }
  }

  function enter(name: string) {
    void load(path ? `${path}/${name}` : name);
  }

  function up() {
    if (path) void load(path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");
  }

  function openHere(target = path) {
    if (!target) return;
    ui.folderPicker = false;
    ui.openFolder(target);
  }

  async function newFolder() {
    const name = await ui.prompt(`New folder in /workspace/${path}`, "", "folder name");
    if (!name) return;
    const p = path ? `${path}/${name}` : name;
    try {
      await session.api.create(p, "dir");
      await load(path);
      sel = Math.max(0, shown.indexOf(name));
    } catch (e) {
      ui.error(e);
    }
  }

  function key(e: KeyboardEvent) {
    if (ui.dialog) return;
    if (e.key === "Escape") { e.preventDefault(); ui.folderPicker = false; }
    else if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, shown.length - 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); }
    else if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); openHere(shown[sel] ? (path ? `${path}/${shown[sel]}` : shown[sel]) : path); }
    else if (e.key === "Enter") { e.preventDefault(); if (shown[sel]) enter(shown[sel]); }
    else if (e.key === "Backspace" && !filter) { e.preventDefault(); up(); }
  }

  onMount(() => load(path));
</script>

<div class="back" role="presentation" onclick={() => (ui.folderPicker = false)}>
  <div class="box" role="dialog" aria-label="Open folder" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={() => {}}>
    <div class="head">
      <h3>Open Folder</h3>
      <div class="crumbs">
        <button class="crumb" onclick={() => load("")}>workspace</button>
        {#each crumbs as c, i}
          <span class="faint">/</span><button class="crumb" onclick={() => load(crumbs.slice(0, i + 1).join("/"))}>{c}</button>
        {/each}
      </div>
    </div>
    <input bind:this={input} class="field" placeholder="Type to filter · Enter: go in · Ctrl+Enter: open · Backspace: up" bind:value={filter} onkeydown={key} spellcheck="false" />
    <div class="list">
      {#if path}<button class="row" ondblclick={up} onclick={up}><Icon name="folder" size={15} /><span>..</span></button>{/if}
      {#each shown as d, i (d)}
        <button class="row" class:sel={i === sel} onclick={() => (sel = i)} ondblclick={() => enter(d)} onmouseenter={() => (sel = i)}>
          <Icon name="folder" size={15} /><span>{d}</span>
          <span class="go" role="presentation" onclick={(e) => { e.stopPropagation(); enter(d); }}><Icon name="chevronRight" size={13} /></span>
        </button>
      {/each}
      {#if !loading && !shown.length}<p class="faint pad">{error || (filter ? "No matching folders" : "No folders here")}</p>{/if}
    </div>
    <div class="foot">
      <button class="btn" onclick={newFolder}><Icon name="newFolder" size={14} /> New Folder</button>
      <span class="grow"></span>
      <button class="btn" onclick={() => (ui.folderPicker = false)}>Cancel</button>
      {#if shown[sel]}
        <button class="btn" onclick={() => openHere(path ? `${path}/${shown[sel]}` : shown[sel])}>Open “{shown[sel]}”</button>
      {/if}
      <button class="btn primary" disabled={!path} onclick={() => openHere()} title={path ? "" : "Pick a folder inside the workspace"}>
        Open {path ? `“${path.slice(path.lastIndexOf("/") + 1)}”` : ""}
      </button>
    </div>
  </div>
</div>

<style>
  .back { position: fixed; inset: 0; z-index: 85; background: #0006; display: flex; justify-content: center; padding-top: 70px; }
  .box { width: 640px; max-height: 70vh; display: flex; flex-direction: column; background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 10px; box-shadow: 0 20px 60px #000b; align-self: flex-start; overflow: hidden; }
  .head { padding: 14px 16px 8px; display: flex; flex-direction: column; gap: 6px; }
  h3 { margin: 0; font-size: 14px; }
  .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 2px; font-size: 12.5px; }
  .crumb { border: 0; background: none; padding: 1px 4px; border-radius: 4px; color: var(--accent); }
  .crumb:hover { background: #ffffff10; }
  .box > .field { margin: 0 16px 8px; width: auto; }
  .list { overflow: auto; padding: 0 8px; min-height: 160px; }
  .row { width: 100%; display: flex; align-items: center; gap: 8px; padding: 5px 8px; border: 0; border-radius: 6px; background: none; text-align: left; color: var(--text); }
  .row :global(svg) { color: #c9a95a; flex: none; }
  .row span:not(.go) { flex: 1; }
  .row.sel { background: #2f4168; }
  .go { color: var(--dim); display: grid; place-items: center; width: 22px; height: 22px; border-radius: 4px; }
  .go:hover { background: #ffffff18; }
  .pad { padding: 12px 8px; margin: 0; }
  .foot { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--line); }
  .grow { flex: 1; }
</style>
