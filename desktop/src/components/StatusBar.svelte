<script lang="ts">
  import Icon from "./Icon.svelte";
  import { session } from "../lib/session.svelte";
  import { editors } from "../lib/editors.svelte";
  import { tree } from "../lib/tree.svelte";
  import { cursor } from "../lib/cursor.svelte";
  import { ui } from "../lib/ui.svelte";
  import { languageName } from "../lib/codemirror";
  import { checkpoints } from "../lib/checkpoints.svelte";
  import { problems } from "../lib/problems.svelte";

  let now = $state(Date.now());
  $effect(() => { const t = setInterval(() => (now = Date.now()), 1000); return () => clearInterval(t); });

  const active = $derived(editors.active);
  const autosaveIn = $derived(editors.autosaveDue ? Math.max(0, Math.round((editors.autosaveDue - now) / 1000)) : null);
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
</script>

<footer class="status">
  <span class="item conn" class:off={!session.connected} title={session.connected ? "Connected to the IDE server" : "Reconnecting…"}>
    <span class="led"></span>{session.connected ? session.api.server.replace(/^https?:\/\//, "") : "Reconnecting…"}
  </span>
  {#if tree.branch}
    <span class="item" title="Git branch in the builder"><Icon name="branch" size={13} /> {tree.branch}{tree.ahead ? ` ↑${tree.ahead}` : ""}{tree.behind ? ` ↓${tree.behind}` : ""}</span>
  {/if}
  {#if problems.items.length}
    <button class="item link warn" title="Problems the IDE server ran into — click for details" onclick={() => { ui.side = "devices"; ui.sideOpen = true; }}>
      <Icon name="warning" size={13} /> {problems.items.length} problem{problems.items.length === 1 ? "" : "s"}
    </button>
  {/if}
  {#if tree.gitError}
    <span class="item warn git-error" title={tree.gitError}><Icon name="warning" size={13} /> git error</span>
  {/if}
  {#if tree.branch && checkpoints.label}
    {#key now}
      <button class="item link checkpoint" class:off={!checkpoints.info?.enabled} title={checkpoints.detail}
        disabled={checkpoints.busy || !checkpoints.info?.enabled} onclick={() => checkpoints.now()}>
        <Icon name="clock" size={13} /> {checkpoints.busy ? "Checkpointing…" : checkpoints.label}
      </button>
    {/key}
  {/if}
  <span class="grow"></span>
  {#if autosaveIn !== null}
    <button class="item link" title="Unsaved files save 3 minutes after the last change. Click to save all now." onclick={() => editors.saveAll()}>
      Auto-save in {fmt(autosaveIn)}
    </button>
  {/if}
  {#if active?.kind === "file" && active.media}
    <span class="item">{active.media[0].toUpperCase() + active.media.slice(1)}</span>
  {:else if active?.kind === "file"}
    <span class="item">Ln {cursor.line}, Col {cursor.col}{cursor.selected ? ` (${cursor.selected} selected)` : ""}{cursor.cursors > 1 ? ` · ${cursor.cursors} cursors` : ""}</span>
    <span class="item">{languageName(active.path)}</span>
  {/if}
  <button class="item link" title="Toggle the terminal panel (Ctrl+`)" onclick={() => { ui.panelOpen = !ui.panelOpen; ui.persist(); }}><Icon name="panel" size={13} /></button>
</footer>

<style>
  .status { height: 24px; flex: none; display: flex; align-items: center; gap: 2px; padding: 0 6px; background: #0f1116; border-top: 1px solid var(--line); font-size: 11.5px; color: var(--dim); }
  .item { display: inline-flex; align-items: center; gap: 5px; height: 20px; padding: 0 7px; border-radius: 4px; white-space: nowrap; }
  .link { border: 0; background: none; color: inherit; font-size: inherit; }
  .link:hover { background: #ffffff10; color: var(--text); }
  .grow { flex: 1; }
  .checkpoint.off { opacity: .6; }
  .warn { color: var(--warn); }
  .led { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); }
  .conn.off { color: var(--warn); }
  .conn.off .led { background: var(--warn); animation: blink 1s infinite; }
  @keyframes blink { 50% { opacity: .3; } }
</style>
