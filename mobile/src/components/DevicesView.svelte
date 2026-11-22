<script lang="ts">
  import { onMount } from "svelte";
  import { relativeTime, type DeviceInfo } from "@core/index";
  import { session } from "@state/session.svelte";
  import { ui } from "@state/ui.svelte";
  import { checkpoints } from "@state/checkpoints.svelte";
  import { problems } from "@state/problems.svelte";

  let devices = $state<DeviceInfo[]>([]);
  let max = $state(3);
  let usageError = $state("");
  let usage = $state<{ stored_bytes: number; cap_bytes: number; versions: number } | null>(null);

  async function load() {
    try {
      const r = await session.api.devices();
      devices = r.devices;
      max = r.max;
    } catch (e) { ui.error(e); }
    try {
      usage = await session.api.historyUsage();
      usageError = "";
    } catch (e) { usageError = e instanceof Error ? e.message : String(e); }
  }

  async function revoke(d: DeviceInfo) {
    const msg = d.current ? "This is this phone: you'll be signed out and need to pair again." : "It's signed out right away and must pair again.";
    if (!(await ui.confirm(`Remove ${d.name}?`, msg, "Remove", true))) return;
    try {
      await session.api.revokeDevice(d.id);
      if (d.current) await session.forgetDevice();
      else await load();
    } catch (e) { ui.error(e); }
  }

  const gb = (b: number) => (b / 1024 ** 3).toFixed(b < 1024 ** 3 ? 2 : 1);
  onMount(load);
</script>

<div class="devices">
  {#if problems.items.length}
    <h4>Server Problems</h4>
    {#each problems.items as p (p.key)}
      <div class="problem">
        <div>{p.message}</div>
        {#if p.fix}<div class="small"><b>Fix:</b> {p.fix}</div>{/if}
        <details class="small faint"><summary>Details</summary><code>{p.detail}</code></details>
        <button class="btn small" onclick={() => problems.dismiss(p.key)}>Dismiss</button>
      </div>
    {/each}
  {/if}

  {#if checkpoints.info}
    <h4>Checkpoints</h4>
    <label class="toggle">
      <input type="checkbox" checked={checkpoints.info.enabled} onchange={(e) => checkpoints.setEnabled(e.currentTarget.checked)} />
      <span>Automatic checkpoint commits for <b>{checkpoints.project}</b></span>
    </label>
    <p class="faint small">Commits work in progress to <code>checkpoints/&lt;branch&gt;</code> when edits settle.</p>
    <button class="btn" disabled={!checkpoints.info.enabled || checkpoints.busy} onclick={() => checkpoints.now()}>
      {checkpoints.busy ? "Checkpointing…" : "Checkpoint now"}
    </button>
  {/if}

  <h4>Paired Devices (max {max})</h4>
  {#each devices as d (d.id)}
    <div class="dev" class:current={d.current}>
      <div class="name">{d.name}{#if d.current}<span class="badge">this phone</span>{/if}</div>
      <div class="faint small">Last used {relativeTime(d.last_seen)} · {d.last_ip || "—"}</div>
      <button class="btn small danger" onclick={() => revoke(d)}>Remove</button>
    </div>
  {/each}

  <h4>Session</h4>
  <p class="faint small">Signed in as <b>{session.deviceName}</b>. Inactive sessions end after 10 minutes.</p>
  <button class="btn" onclick={() => session.lock("Locked.")}>Lock now</button>

  {#if usageError}
    <h4>Change history</h4>
    <p class="small warn-text">{usageError}</p>
  {:else if usage}
    <h4>Change history</h4>
    <div class="meter"><div style:width="{Math.min(100, (usage.stored_bytes / usage.cap_bytes) * 100)}%"></div></div>
    <p class="faint small">{gb(usage.stored_bytes)} GB of {gb(usage.cap_bytes)} GB · {usage.versions} versions</p>
  {/if}
</div>

<style>
  .devices { flex: 1; overflow: auto; padding: 14px 14px 30px; display: flex; flex-direction: column; gap: 10px; }
  h4 { margin: 10px 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--dim); }
  p { margin: 0; }
  .small { font-size: 12.5px; }
  .dev { padding: 12px; border-radius: 10px; border: 1px solid var(--line-2); display: flex; flex-direction: column; gap: 4px; align-items: flex-start; }
  .dev.current { border-color: #3a5a8a; }
  .name { font-weight: 600; display: flex; gap: 8px; align-items: center; }
  .toggle { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
  .meter { height: 8px; border-radius: 4px; background: #262b35; overflow: hidden; }
  .meter div { height: 100%; background: var(--accent-2); }
  .problem { border: 1px solid var(--warn); border-radius: 8px; padding: 10px; display: grid; gap: 6px; }
  .problem code { white-space: pre-wrap; word-break: break-word; }
  code { font-family: var(--mono); font-size: 12px; background: #0e1015; padding: 1px 5px; border-radius: 4px; }
  .warn-text { color: var(--warn); }
</style>
