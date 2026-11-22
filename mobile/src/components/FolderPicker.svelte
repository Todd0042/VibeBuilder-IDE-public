<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "./Icon.svelte";
  import { session } from "@state/session.svelte";
  import { ui } from "@state/ui.svelte";

  let path = $state(ui.project.includes("/") ? ui.project.slice(0, ui.project.lastIndexOf("/")) : "");
  let dirs = $state<string[]>([]);
  let loading = $state(false);
  let error = $state("");
  let filter = $state("");

  const crumbs = $derived(path ? path.split("/") : []);
  const shown = $derived(filter ? dirs.filter((d) => d.toLowerCase().includes(filter.toLowerCase())) : dirs);

  async function load(p: string) {
    loading = true;
    error = "";
    try {
      const r = await session.api.list(p);
      dirs = r.entries.filter((e) => e.kind === "dir" && e.name !== ".git").map((e) => e.name);
      path = p;
      filter = "";
    } catch (e) { error = e instanceof Error ? e.message : String(e); }
    finally { loading = false; }
  }

  function openHere(target = path) {
    ui.folderPicker = false;
    ui.openFolder(target);
    ui.mobileView = "files";
  }

  async function newFolder() {
    const name = await ui.prompt(`New folder in /workspace/${path}`, "", "folder name");
    if (!name) return;
    const p = path ? `${path}/${name}` : name;
    try {
      await session.api.create(p, "dir");
      await load(path);
    } catch (e) { ui.error(e); }
  }

  onMount(() => load(path));
</script>

<div class="back" role="presentation" onclick={() => (ui.folderPicker = false)}>
  <div class="box" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === "Escape" && (ui.folderPicker = false)}>
    <div class="head">
      <h3>Open Folder</h3>
      <div class="crumbs">
        <button class="crumb" onclick={() => load("")}>workspace</button>
        {#each crumbs as c, i}
          <span class="faint">/</span><button class="crumb" onclick={() => load(crumbs.slice(0, i + 1).join("/"))}>{c}</button>
        {/each}
      </div>
      <input class="field" placeholder="Filter folders" bind:value={filter} spellcheck="false" />
    </div>
    <div class="list">
      <div class="ws-pin" class:active={!path}>
        <button class="main" onclick={() => load("")}>
          <Icon name="folderOpen" size={16} /><span>Workspace</span>
        </button>
        <button class="btn small" onclick={() => openHere("")}>Open</button>
      </div>
      {#if path}
        <button class="row indent" onclick={() => load(path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "")}>
          <Icon name="folder" size={16} /><span>..</span>
        </button>
      {/if}
      {#each shown as d (d)}
        <div class="row indent">
          <button class="main" onclick={() => load(path ? `${path}/${d}` : d)}>
            <Icon name="folder" size={16} /><span>{d}</span>
          </button>
          <button class="btn small" onclick={() => openHere(path ? `${path}/${d}` : d)}>Open</button>
        </div>
      {/each}
      {#if !loading && !shown.length}<p class="faint pad indent">{error || "No folders here"}</p>{/if}
    </div>
    <div class="foot">
      <button class="btn small" onclick={newFolder}><Icon name="newFolder" size={14} /> New</button>
      <span class="grow"></span>
      <button class="btn small" onclick={() => (ui.folderPicker = false)}>Cancel</button>
      <button class="btn small primary" onclick={() => openHere()}>
        {path ? "Open current" : "Open Workspace"}
      </button>
    </div>
  </div>
</div>

<style>
  .back { position: fixed; inset: 0; z-index: 120; background: #0008; display: flex; justify-content: center; padding: 14px; }
  .box { width: min(520px, 100%); max-height: 78dvh; display: flex; flex-direction: column; background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 14px; overflow: hidden; align-self: flex-start; }
  .head { padding: 14px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--line); }
  h3 { margin: 0; font-size: 15px; }
  .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 2px; font-size: 13px; }
  .crumb { border: 0; background: none; padding: 2px 6px; border-radius: 4px; color: var(--accent); }
  .list { flex: 1; overflow: auto; padding: 0 10px 8px; min-height: 150px; }
  .ws-pin {
    position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 8px; min-height: 44px;
    padding: 4px 6px; background: var(--panel-2); border-bottom: 1px solid var(--line); font-weight: 700;
  }
  .ws-pin.active .main { color: var(--accent); }
  .row { width: 100%; min-height: 42px; display: flex; align-items: center; gap: 8px; padding: 4px 6px; border: 0; border-radius: 8px; background: none; text-align: left; }
  .indent { padding-left: calc(6px + 2ch); }
  .main { flex: 1; display: flex; align-items: center; gap: 8px; border: 0; background: none; padding: 6px 2px; text-align: left; }
  .ws-pin :global(svg), .row :global(svg) { color: #c9a95a; flex: none; }
  .pad { padding: 12px 6px; }
  .foot { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-top: 1px solid var(--line); }
  .grow { flex: 1; }
</style>
