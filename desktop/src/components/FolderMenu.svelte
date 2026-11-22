<script lang="ts">
  // The title bar's folder dropdown. Hover a folder and click the eye to hide it from this list (and the
  // File menu); "Hidden folders" at the bottom lists them with a button to show each again. Hiding
  // never touches the folder on disk, and Open Folder… still finds hidden folders.
  import { tick } from "svelte";
  import Icon from "./Icon.svelte";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";

  let open = $state(false);
  let filter = $state("");
  let sel = $state(0);
  let showHidden = $state(false);
  let root: HTMLDivElement | undefined = $state();
  let input: HTMLInputElement | undefined = $state();

  const match = (p: string) => !filter || p.toLowerCase().includes(filter.toLowerCase());
  const shown = $derived(ui.folderChoices.filter(match));
  const hidden = $derived(ui.hiddenFolders.filter(match));
  const label = $derived(ui.project ? ui.project.slice(ui.project.lastIndexOf("/") + 1) : "No folder");

  async function toggle() {
    open = !open;
    if (!open) return;
    filter = "";
    sel = Math.max(0, ui.folderChoices.indexOf(ui.project));
    showHidden = false;
    await tick();
    input?.focus();
  }

  function pick(p: string) {
    open = false;
    if (p !== ui.project) ui.openFolder(p);
  }

  async function setHidden(p: string, hide: boolean) {
    const before = ui.hiddenFolders;
    ui.hiddenFolders = hide ? [...before, p] : before.filter((x) => x !== p); // show it at once; undo if the server says no
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    try {
      ui.hiddenFolders = (await session.api.setHidden(p, hide)).hidden;
      if (hide) ui.toast(`Hid “${p}” from the folder list`, "info", { label: "Undo", run: () => void setHidden(p, false) });
    } catch (e) {
      ui.hiddenFolders = before;
      ui.error(e, hide ? `Couldn't hide ${p}` : `Couldn't unhide ${p}`);
    }
  }

  function key(e: KeyboardEvent) {
    if (e.key === "Escape") { e.preventDefault(); open = false; }
    else if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, shown.length - 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); }
    else if (e.key === "Enter") { e.preventDefault(); if (shown[sel]) pick(shown[sel]); }
    else if (e.key === "Delete" && shown[sel]) { e.preventDefault(); void setHidden(shown[sel], true); }
  }

  $effect(() => {
    if (!open) return;
    const away = (e: Event) => { if (!root?.contains(e.target as Node)) open = false; };
    window.addEventListener("pointerdown", away);
    return () => window.removeEventListener("pointerdown", away);
  });
</script>

<div class="wrap" bind:this={root}>
  <button class="project" class:open title={ui.project ? `/workspace/${ui.project}` : "Open a folder"} onclick={toggle}>
    <span class="name">{label}</span><Icon name="chevronDown" size={13} />
  </button>
  {#if open}
    <div class="pop" role="menu">
      <input bind:this={input} class="field" placeholder="Filter folders · Del: hide" bind:value={filter} onkeydown={key}
        oninput={() => (sel = 0)} spellcheck="false" />
      <div class="list">
        {#each shown as p, i (p)}
          <div class="row" class:sel={i === sel} role="menuitem" tabindex="-1" onmouseenter={() => (sel = i)}
            onclick={() => pick(p)} onkeydown={() => {}}>
            <span class="mark">{#if p === ui.project}<Icon name="check" size={13} />{/if}</span>
            <span class="path">{p}</span>
            <button class="act" title="Hide from this list (the folder stays on disk)" onclick={(e) => { e.stopPropagation(); void setHidden(p, true); }}>
              <Icon name="eyeOff" size={14} />
            </button>
          </div>
        {/each}
        {#if !shown.length}<p class="faint pad">{filter ? "No matching folders" : "No folders in the list"}</p>{/if}
      </div>
      {#if ui.hiddenFolders.length}
        <button class="section" onclick={() => (showHidden = !showHidden)}>
          <Icon name={showHidden ? "chevronDown" : "chevronRight"} size={12} />
          Hidden folders ({ui.hiddenFolders.length})
        </button>
        {#if showHidden}
          <div class="list hidden-list">
            {#each hidden as p (p)}
              <div class="row dim" role="menuitem" tabindex="-1" onclick={() => pick(p)} onkeydown={() => {}} title="Open without unhiding">
                <span class="mark">{#if p === ui.project}<Icon name="check" size={13} />{/if}</span>
                <span class="path">{p}</span>
                <button class="act show" title="Show in the list again" onclick={(e) => { e.stopPropagation(); void setHidden(p, false); }}>
                  <Icon name="eye" size={14} /> Unhide
                </button>
              </div>
            {/each}
            {#if !hidden.length}<p class="faint pad">No matching hidden folders</p>{/if}
          </div>
        {/if}
      {/if}
      <button class="section open-folder" onclick={() => { open = false; ui.folderPicker = true; }}>
        <Icon name="folderOpen" size={14} /> Open Folder…
      </button>
    </div>
  {/if}
</div>

<style>
  .wrap { position: relative; }
  .project { height: 28px; min-width: 140px; max-width: 260px; display: flex; align-items: center; gap: 6px; padding: 0 8px; border-radius: 6px; background: #1b1f27; border: 1px solid var(--line-2); font-weight: 600; color: var(--text); }
  .project:hover, .project.open { border-color: #3d4556; }
  .project .name { flex: 1; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pop { position: absolute; top: 32px; left: 0; z-index: 80; width: 340px; display: flex; flex-direction: column; padding: 6px; border-radius: 8px; background: #1e222b; border: 1px solid var(--line-2); box-shadow: 0 10px 40px #000b; }
  .pop > .field { margin: 0 0 6px; width: auto; }
  .list { max-height: 46vh; overflow: auto; }
  .hidden-list { max-height: 26vh; }
  .row { display: flex; align-items: center; gap: 6px; padding: 4px 6px; border-radius: 5px; cursor: pointer; }
  .row.sel, .row:hover { background: #2f4168; }
  .row.dim .path { color: var(--dim); }
  .mark { width: 14px; display: grid; place-items: center; color: var(--accent); flex: none; }
  .path { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .act { display: inline-flex; align-items: center; gap: 4px; height: 22px; padding: 0 5px; border: 0; border-radius: 4px; background: none; color: var(--dim); opacity: 0; font-size: 11.5px; }
  .row:hover .act, .row.sel .act, .act.show { opacity: 1; }
  .act:hover { background: #ffffff1c; color: var(--text); }
  .section { display: flex; align-items: center; gap: 6px; margin-top: 4px; padding: 6px; border: 0; border-top: 1px solid var(--line-2); border-radius: 0; background: none; color: var(--dim); text-align: left; font-size: 12px; }
  .section:hover { color: var(--text); }
  .open-folder { color: var(--accent); font-size: 12.5px; }
  .pad { padding: 8px 6px; margin: 0; }
</style>
