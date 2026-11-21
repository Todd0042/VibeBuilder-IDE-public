<script lang="ts">
  // Ports & Phone: what's listening in the builder (forward it to this laptop with one click), any
  // other port by number, and the phone toggle (the builder's adb uses this laptop's USB).
  import Icon from "./Icon.svelte";
  import { testing } from "../lib/testing.svelte";

  let { visible }: { visible: boolean } = $props();
  let manual = $state("");

  $effect(() => {
    if (!visible) return;
    void testing.refresh();
    const t = setInterval(() => void testing.refresh(), 3000);
    return () => clearInterval(t);
  });

  function addManual() {
    const n = Number(manual);
    if (Number.isInteger(n) && n > 0 && n < 65536) {
      void testing.forward(n);
      manual = "";
    }
  }

  const forwardedOnly = $derived(Object.keys(testing.forwards).map(Number).filter((p) => !testing.builderPorts.some((b) => b.port === p)));
</script>

<div class="ports">
  {#if !testing.available}
    <p class="note">Port forwarding, the phone and app windows need the desktop app (<code>bin/vb-app</code> or the AppImage); a browser can't open local ports.</p>
  {/if}

  <section>
    <h4>Phone</h4>
    <div class="row">
      <span class="dot" class:on={testing.adb}></span>
      <span class="grow">{testing.adb ? "Connected: the builder's adb sees devices plugged into this laptop" : "A phone plugged into this laptop (USB debugging on)"}</span>
      <button class="btn small" class:primary={!testing.adb} disabled={!testing.available || testing.busy} onclick={() => testing.toggleAdb()}>
        {testing.adb ? "Disconnect" : "Connect"}
      </button>
    </div>
    {#if testing.adb}<p class="faint hint">In a shell: <code>adb devices</code>, <code>./gradlew installDebug</code>, <code>adb logcat</code>.</p>{/if}
  </section>

  <section>
    <h4>Listening in the builder</h4>
    {#each testing.builderPorts as p (p.port)}
      <div class="row">
        <span class="mono port">{p.port}</span>
        <span class="faint proc">{p.process}</span>
        <span class="grow"></span>
        {#if testing.forwards[p.port]}
          <span class="mono local">→ localhost:{testing.forwards[p.port]}</span>
          <button class="btn small" onclick={() => navigator.clipboard.writeText(`http://localhost:${testing.forwards[p.port]}`)} title="Copy the address"><Icon name="open" size={12} /></button>
          <button class="btn small" onclick={() => testing.unforward(p.port)}>Stop</button>
        {:else}
          <button class="btn small primary" disabled={!testing.available} onclick={() => testing.forward(p.port)}>Forward</button>
        {/if}
      </div>
    {:else}
      <p class="faint hint">Nothing is listening yet. Start a dev server in a terminal and it shows up here.</p>
    {/each}
    {#each forwardedOnly as p}
      <div class="row">
        <span class="mono port">{p}</span><span class="faint proc">(not listening right now)</span><span class="grow"></span>
        <span class="mono local">→ localhost:{testing.forwards[p]}</span>
        <button class="btn small" onclick={() => testing.unforward(p)}>Stop</button>
      </div>
    {/each}
    <div class="row add">
      <input class="field" placeholder="Forward another port (number)" bind:value={manual} inputmode="numeric" onkeydown={(e) => e.key === "Enter" && addManual()} />
      <button class="btn small" disabled={!testing.available} onclick={addManual}>Forward</button>
    </div>
  </section>

  <p class="faint hint">Desktop apps: <b>Terminal → Run App…</b> (F5) runs a command in the builder and opens its windows on this laptop.</p>
</div>

<style>
  .ports { position: absolute; inset: 0; overflow: auto; padding: 10px 16px 20px; display: flex; flex-direction: column; gap: 14px; font-size: 12.5px; }
  section { display: flex; flex-direction: column; gap: 5px; max-width: 760px; }
  h4 { margin: 0 0 2px; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--dim); }
  .row { display: flex; align-items: center; gap: 9px; padding: 5px 8px; border-radius: 6px; background: #ffffff05; }
  .row.add { background: none; padding: 4px 0; }
  .row.add .field { max-width: 260px; height: 26px; }
  .grow { flex: 1; }
  .port { min-width: 56px; font-weight: 600; }
  .proc { min-width: 80px; }
  .local { color: var(--ok); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: #3a404c; flex: none; }
  .dot.on { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .hint { margin: 0; font-size: 12px; }
  .note { margin: 0; padding: 8px 10px; border-radius: 6px; background: #2a2619; color: #ffe2b0; }
  code { font-family: var(--mono); font-size: 11.5px; background: #0e1015; padding: 1px 5px; border-radius: 4px; color: var(--text); }
</style>
