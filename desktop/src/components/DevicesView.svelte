<script lang="ts">
  import { onMount } from "svelte";
  import type { DeviceInfo } from "@core/index";
  import { relativeTime } from "@core/index";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";

  let devices = $state<DeviceInfo[]>([]);
  let max = $state(3);
  let usage = $state<{ stored_bytes: number; cap_bytes: number; versions: number } | null>(null);

  async function load() {
    try {
      const r = await session.api.devices();
      devices = r.devices;
      max = r.max;
    } catch (e) {
      ui.error(e);
    }
    try {
      usage = await session.api.historyUsage();
    } catch { /* optional */ }
  }

  async function revoke(d: DeviceInfo) {
    const msg = d.current ? "This is the device you're using: you'll be signed out and need to pair again." : "It's signed out right away and has to pair again to come back.";
    if (!(await ui.confirm(`Remove ${d.name}?`, msg, "Remove", true))) return;
    try {
      await session.api.revokeDevice(d.id);
      if (d.current) await session.forgetDevice();
      else await load();
    } catch (e) {
      ui.error(e);
    }
  }

  const gb = (b: number) => (b / 1024 ** 3).toFixed(b < 1024 ** 3 ? 2 : 1);
  onMount(load);
</script>

<div class="head"><span class="label">DEVICES</span></div>
<div class="body">
  <p class="faint">Up to {max} devices can be paired. To add one, run <code>vibebuilder pair</code> on the desktop.</p>
  {#each devices as d (d.id)}
    <div class="dev" class:current={d.current}>
      <div class="name">{d.name}{#if d.current}<span class="badge">this device</span>{/if}</div>
      <div class="faint small">Last used {relativeTime(d.last_seen)} · {d.last_ip || "—"}</div>
      <div class="faint small">Paired {new Date(d.created * 1000).toLocaleDateString()}</div>
      <button class="btn small danger" onclick={() => revoke(d)}>Remove</button>
    </div>
  {/each}

  <h4>Session</h4>
  <p class="faint small">Signed in as <b>{session.deviceName}</b>. You sign in when the app opens, and closing it signs you out. If the app disappears without signing out (crash, laptop asleep), the server ends the session after 10 minutes.</p>
  <button class="btn small" onclick={() => session.lock("Locked.")}>Lock now</button>

  {#if usage}
    <h4>Change history</h4>
    <div class="meter"><div style:width="{Math.min(100, (usage.stored_bytes / usage.cap_bytes) * 100)}%"></div></div>
    <p class="faint small">{gb(usage.stored_bytes)} GB of {gb(usage.cap_bytes)} GB · {usage.versions} versions kept. When full, files that haven't changed for the longest lose their history first.</p>
  {/if}

  <h4>Shortcuts</h4>
  <div class="keys">
    <span><kbd>Ctrl P</kbd> go to file</span><span><kbd>Ctrl Shift F</kbd> search folder</span>
    <span><kbd>Ctrl F</kbd> find in file</span><span><kbd>Ctrl H</kbd> replace in file</span>
    <span><kbd>Ctrl S</kbd> save</span><span><kbd>Ctrl Alt S</kbd> save all</span>
    <span><kbd>Ctrl `</kbd> terminal</span><span><kbd>Ctrl B</kbd> side bar</span>
    <span><kbd>Ctrl W</kbd> close tab</span><span><kbd>Ctrl Tab</kbd> next tab</span>
    <span><kbd>Ctrl Shift E</kbd> explorer</span><span><kbd>Ctrl Shift G</kbd> changes</span>
    <span><kbd>Ctrl Shift C/V</kbd> terminal copy/paste</span><span><kbd>Alt G</kbd> go to line</span>
  </div>
</div>

<style>
  .head { height: 36px; flex: none; display: flex; align-items: center; padding: 0 14px; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .body { flex: 1; overflow: auto; padding: 0 14px 20px; display: flex; flex-direction: column; gap: 8px; }
  p { margin: 0; }
  .small { font-size: 11.5px; }
  .dev { padding: 10px; border-radius: 8px; border: 1px solid var(--line-2); display: flex; flex-direction: column; gap: 3px; align-items: flex-start; }
  .dev.current { border-color: #3a5a8a; }
  .name { font-weight: 600; display: flex; gap: 6px; align-items: center; }
  .dev .btn { margin-top: 5px; }
  h4 { margin: 10px 0 0; font-size: 12px; color: var(--dim); letter-spacing: .04em; }
  .meter { height: 6px; border-radius: 3px; background: #262b35; overflow: hidden; }
  .meter div { height: 100%; background: var(--accent-2); }
  .keys { display: grid; grid-template-columns: 1fr; gap: 5px; font-size: 12px; color: var(--dim); }
  code { font-family: var(--mono); font-size: 11.5px; background: #0e1015; padding: 1px 5px; border-radius: 4px; color: var(--text); }
</style>
