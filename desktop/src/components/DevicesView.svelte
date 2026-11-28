<script lang="ts">
  import { onMount } from "svelte";
  import type { DeviceInfo } from "@core/index";
  import { relativeTime } from "@core/index";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";
  import { checkpoints } from "../lib/checkpoints.svelte";
  import { problems } from "../lib/problems.svelte";

  let devices = $state<DeviceInfo[]>([]);
  let max = $state(3);
  let usageError = $state("");
  let usage = $state<{ stored_bytes: number; cap_bytes: number; versions: number } | null>(null);
  let capGb = $state(10);
  let pruning = $state(false);

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
      capGb = Math.max(1, Math.round(usage.cap_bytes / 1024 ** 3));
      usageError = "";
    } catch (e) {
      usageError = e instanceof Error ? e.message : String(e);
    }
  }

  async function pruneNow() {
    pruning = true;
    try {
      const res = await session.api.pruneHistory(capGb);
      usage = res.usage;
      ui.toast(`History cap set to ${capGb} GB`);
    } catch (e) {
      ui.error(e, "Couldn't prune history");
    } finally {
      pruning = false;
    }
  }

  async function revoke(d: DeviceInfo) {
    const msg = d.current ? "This is the device you're using: you'll be signed out and will reconnect via Cloudflare Access." : "It's signed out right away.";
    if (!(await ui.confirm(`Remove ${d.name}?`, msg, "Remove", true))) return;
    try {
      await session.api.revokeDevice(d.id);
      if (d.current) await session.lock();
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
  {#if problems.items.length}
    <h4 class="problems-title">Problems</h4>
    {#each problems.items as p (p.key)}
      <div class="problem">
        <div>{p.message}</div>
        {#if p.fix}<div class="small"><b>Fix:</b> {p.fix}</div>{/if}
        <details class="small faint"><summary>Details{p.count > 1 ? ` (happened ${p.count} times, last ${relativeTime(p.last)})` : ""}</summary><code>{p.detail}</code></details>
        <button class="btn small" onclick={() => problems.dismiss(p.key)}>Dismiss</button>
      </div>
    {/each}
  {/if}
  <p class="faint">Authenticated via Cloudflare Zero Trust Access (up to {max} active sessions).</p>
  {#each devices as d (d.id)}
    <div class="dev" class:current={d.current}>
      <div class="name">{d.name}{#if d.current}<span class="badge">this device</span>{/if}</div>
      <div class="faint small">Last used {relativeTime(d.last_seen)} · {d.last_ip || "—"}</div>
      <div class="faint small">Paired {new Date(d.created * 1000).toLocaleDateString()}</div>
      <button class="btn small danger" onclick={() => revoke(d)}>Remove</button>
    </div>
  {/each}

  {#if checkpoints.info}
    <h4>Checkpoints</h4>
    <label class="toggle">
      <input type="checkbox" checked={checkpoints.info.enabled} onchange={(e) => checkpoints.setEnabled(e.currentTarget.checked)} />
      Automatic checkpoint commits for <b>{checkpoints.project}</b>
    </label>
    <p class="faint small">A few minutes after changes settle, the work in progress is committed to the branch
      <code>checkpoints/&lt;branch&gt;</code>, with a message Claude writes from the changes. Your branch, staged changes and files
      aren't touched, nothing is pushed, and secrets (<code>.env</code>, keys) and dependency folders are left out.
      It starts over on top of each real commit. To get a file back: <code>git checkout checkpoints/main -- path</code>.</p>
    <button class="btn small" disabled={!checkpoints.info.enabled || checkpoints.busy} onclick={() => checkpoints.now()}>Checkpoint now</button>
  {/if}

  <h4>Session</h4>
  <p class="faint small">Signed in as <b>{session.deviceName}</b>. You sign in when the app opens, and closing it signs you out. If the app disappears without signing out (crash, laptop asleep), the server ends the session after 10 minutes.</p>
  <button class="btn small" onclick={() => session.lock("Locked.")}>Lock now</button>

  {#if usageError}
    <h4>Change history</h4>
    <p class="small warn-text">Couldn't load the change history's size: {usageError}</p>
  {/if}
  {#if usage}
    <h4>Change history</h4>
    <div class="meter"><div style:width="{Math.min(100, (usage.stored_bytes / usage.cap_bytes) * 100)}%"></div></div>
    <p class="faint small">{gb(usage.stored_bytes)} GB of {gb(usage.cap_bytes)} GB · {usage.versions} versions kept. When full, files that haven't changed for the longest lose their history first.</p>
    <div class="cap-row">
      <select class="field small" bind:value={capGb} aria-label="History storage cap">
        {#each [2, 5, 10, 25] as g}
          <option value={g}>{g} GB cap</option>
        {/each}
      </select>
      <button class="btn small" disabled={pruning} onclick={pruneNow}>{pruning ? "Pruning…" : "Apply & Prune"}</button>
    </div>
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
  .cap-row { display: flex; gap: 8px; align-items: center; }
  .keys { display: grid; grid-template-columns: 1fr; gap: 5px; font-size: 12px; color: var(--dim); }
  code { font-family: var(--mono); font-size: 11.5px; background: #0e1015; padding: 1px 5px; border-radius: 4px; color: var(--text); }
  .toggle { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .problem { border: 1px solid var(--warn); border-radius: 6px; padding: 8px; margin: 6px 0; display: grid; gap: 4px; }
  .problem code { white-space: pre-wrap; word-break: break-word; }
  .warn-text { color: var(--warn); }
</style>
