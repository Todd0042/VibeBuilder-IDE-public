<script lang="ts">
  import Icon from "./Icon.svelte";
  import SearchView from "./SearchView.svelte";
  import PortsView from "./PortsView.svelte";
  import DevicesView from "./DevicesView.svelte";
  import { ui } from "@state/ui.svelte";
  import { problems } from "@state/problems.svelte";
  import { testing } from "@state/testing.svelte";
  import { checkpoints } from "@state/checkpoints.svelte";
  import { session } from "@state/session.svelte";
</script>

<div class="more">
  {#if ui.mobileMore === "menu"}
    <div class="bar"><span class="title">TOOLS & SETTINGS</span></div>
    <div class="grid">
      <button class="card" onclick={() => (ui.mobileMore = "search")}>
        <Icon name="search" size={22} />
        <div>
          <b>Search in Folder</b>
          <div class="faint">ripgrep across {ui.project || "workspace"}</div>
        </div>
      </button>

      <button class="card" onclick={() => (ui.mobileMore = "ports")}>
        <Icon name="ports" size={22} />
        <div>
          <b>Ports & Preview</b>
          <div class="faint">
            {#if Object.keys(testing.forwards).length}
              {Object.keys(testing.forwards).length} forwarded to localhost
            {:else}
              Forward builder dev servers
            {/if}
          </div>
        </div>
      </button>

      <button class="card" onclick={() => (ui.mobileMore = "devices")}>
        <Icon name="devices" size={22} />
        <div>
          <b>Devices, Checkpoints & Problems</b>
          <div class="faint">
            {#if problems.items.length}
              <span class="warn">{problems.items.length} server problem{problems.items.length === 1 ? "" : "s"}</span>
            {:else if checkpoints.label}
              {checkpoints.label}
            {:else}
              Manage paired devices & history
            {/if}
          </div>
        </div>
      </button>

      <button class="card" onclick={() => testing.runApp()}>
        <Icon name="terminal" size={22} />
        <div>
          <b>Run App Command…</b>
          <div class="faint">Start a dev server or test command</div>
        </div>
      </button>

      <button class="card" onclick={() => (ui.folderPicker = true)}>
        <Icon name="folder" size={22} />
        <div>
          <b>Open Folder…</b>
          <div class="faint">Current: {ui.project || "none"}</div>
        </div>
      </button>

      <button class="card" onclick={() => session.lock("Locked.")}>
        <Icon name="lock" size={22} />
        <div>
          <b>Lock Session</b>
          <div class="faint">Sign out while keeping open tabs</div>
        </div>
      </button>
    </div>
  {:else}
    <div class="bar">
      <button class="icon-btn" aria-label="Back" onclick={() => (ui.mobileMore = "menu")}><Icon name="back" size={20} /></button>
      <span class="title">
        {ui.mobileMore === "search" ? "SEARCH" : ui.mobileMore === "ports" ? "PORTS & PREVIEW" : "DEVICES & SETTINGS"}
      </span>
    </div>
    {#if ui.mobileMore === "search"}
      <SearchView />
    {:else if ui.mobileMore === "ports"}
      <PortsView visible={true} />
    {:else}
      <DevicesView />
    {/if}
  {/if}
</div>

<style>
  .more { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .bar { height: 42px; flex: none; display: flex; align-items: center; gap: 6px; padding: 0 12px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .title { font-size: 11.5px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .grid { flex: 1; overflow: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .card {
    display: flex; align-items: center; gap: 14px; padding: 14px; border-radius: 12px;
    background: var(--panel); border: 1px solid var(--line); text-align: left;
  }
  .card:active { background: #232833; }
  .card b { display: block; font-size: 14.5px; }
  .card .faint { font-size: 12.5px; margin-top: 2px; }
  .warn { color: var(--warn); }
</style>
