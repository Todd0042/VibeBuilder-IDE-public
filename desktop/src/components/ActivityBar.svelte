<script lang="ts">
  import Icon from "./Icon.svelte";
  import { ui, type SideView } from "../lib/ui.svelte";
  import { changes } from "../lib/changes.svelte";

  const items: { id: SideView; icon: string; label: string }[] = [
    { id: "explorer", icon: "files", label: "Explorer (Ctrl+Shift+E)" },
    { id: "search", icon: "search", label: "Search in folder (Ctrl+Shift+F)" },
    { id: "changes", icon: "changes", label: "Changes by agents (Ctrl+Shift+G)" },
  ];

  function pick(id: SideView) {
    ui.showSide(id);
    if (id === "changes") changes.unseen = 0;
  }
</script>

<nav class="bar">
  {#each items as it}
    <button class="act" class:on={ui.sideOpen && ui.side === it.id} title={it.label} onclick={() => pick(it.id)}>
      <Icon name={it.icon} size={21} />
      {#if it.id === "changes" && changes.unseen}<span class="dot">{changes.unseen > 9 ? "9+" : changes.unseen}</span>{/if}
    </button>
  {/each}
  <div class="grow"></div>
  <button class="act" class:on={ui.sideOpen && ui.side === "devices"} title="Devices and settings" onclick={() => pick("devices")}>
    <Icon name="devices" size={20} />
  </button>
</nav>

<style>
  .bar { width: 46px; flex: none; display: flex; flex-direction: column; align-items: center; padding: 6px 0; gap: 2px; background: #0f1116; border-right: 1px solid var(--line); }
  .grow { flex: 1; }
  .act { position: relative; width: 38px; height: 40px; display: grid; place-items: center; border: 0; background: none; color: var(--faint); border-left: 2px solid transparent; }
  .act:hover { color: var(--text); }
  .act.on { color: var(--text); border-left-color: var(--accent); }
  .dot { position: absolute; top: 5px; right: 3px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px; background: var(--save); color: #1d1405; font-size: 10px; font-weight: 800; display: grid; place-items: center; }
</style>
