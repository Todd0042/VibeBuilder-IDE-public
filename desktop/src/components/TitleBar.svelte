<script lang="ts">
  import logo from "../assets/logo.png";
  import Icon from "./Icon.svelte";
  import MenuBar from "./MenuBar.svelte";
  import { ui } from "../lib/ui.svelte";
  import { editors } from "../lib/editors.svelte";
  import { session } from "../lib/session.svelte";
  import { changes } from "../lib/changes.svelte";

  const dirtyCount = $derived(editors.dirtyTabs.length);
</script>

<header class="title">
  <div class="left">
    <img class="logo" src={logo} alt="VibeBuilder" />
    <MenuBar />
    <select class="project" value={ui.project} title="Folder" onchange={(e) => {
      const v = (e.currentTarget as HTMLSelectElement).value;
      if (v === "\u0000open") { (e.currentTarget as HTMLSelectElement).value = ui.project; ui.folderPicker = true; }
      else ui.openFolder(v);
    }}>
      {#each ui.folderChoices as p}<option value={p}>{p}</option>{/each}
      <option value={"\u0000open"}>Open Folder…</option>
    </select>
  </div>

  <button class="quick" onclick={() => (ui.quickOpen = true)}>
    <Icon name="search" size={14} />
    <span>Go to file…</span>
    <kbd>Ctrl P</kbd>
  </button>

  <div class="right">
    {#if changes.open}
      <button class="agent-live" onclick={() => { ui.side = "changes"; ui.sideOpen = true; }} title="An agent is changing files right now">
        <span class="pulse"></span> Agent editing…
      </button>
    {/if}
    <button class="save-all" disabled={!dirtyCount || editors.saving} onclick={() => editors.saveAll()} title="Save all changed files (Ctrl+Alt+S)">
      <Icon name="saveall" size={16} />
      Save All{#if dirtyCount}<span class="count">{dirtyCount}</span>{/if}
    </button>
    <button class="icon-btn" title="Lock (sign out; your open files stay)" onclick={() => session.lock("Locked.")}>
      <Icon name="lock" />
    </button>
  </div>
</header>

<style>
  .title { height: 40px; flex: none; display: grid; grid-template-columns: 1fr minmax(220px, 460px) 1fr; align-items: center; gap: 12px; padding: 0 10px; background: #0f1116; border-bottom: 1px solid var(--line); }
  .left, .right { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .right { justify-content: flex-end; }
  .logo { width: 24px; height: 24px; border-radius: 6px; flex: none; }
  .project { height: 28px; min-width: 140px; max-width: 260px; padding: 0 8px; border-radius: 6px; background: #1b1f27; border: 1px solid var(--line-2); font-weight: 600; }
  .quick { height: 28px; display: flex; align-items: center; gap: 8px; padding: 0 10px; border-radius: 6px; background: #1b1f27; border: 1px solid var(--line-2); color: var(--dim); }
  .quick span { flex: 1; text-align: left; }
  .quick:hover { border-color: #3d4556; color: var(--text); }
  .save-all {
    display: inline-flex; align-items: center; gap: 7px; height: 30px; padding: 0 14px; border-radius: 7px; font-weight: 700;
    background: var(--save); border: 1px solid var(--save); color: #1d1405; box-shadow: 0 0 0 0 #f0a63a00; transition: box-shadow .2s;
  }
  .save-all:not(:disabled):hover { background: var(--save-2); box-shadow: 0 0 0 3px #f0a63a33; }
  .save-all:disabled { background: #2a2620; border-color: #3a3326; color: #7c6e57; cursor: default; }
  .count { min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; background: #1d1405; color: var(--save-2); font-size: 11px; display: grid; place-items: center; }
  .agent-live { display: inline-flex; align-items: center; gap: 7px; height: 26px; padding: 0 10px; border-radius: 13px; background: #2a2219; border: 1px solid #4a3a22; color: #ffcf8a; font-size: 12px; }
  .pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--save); animation: pulse 1.2s infinite; }
  @keyframes pulse { 50% { opacity: .3; } }
</style>
