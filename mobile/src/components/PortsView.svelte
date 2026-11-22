<script lang="ts">
  import Icon from "./Icon.svelte";
  import { testing } from "@state/testing.svelte";
  import { openExternal } from "@platform";

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
    <p class="note">Port forwarding requires the installed Android app.</p>
  {/if}

  <section>
    <div class="head-row">
      <h4>Listening in the builder</h4>
      <label class="auto-toggle"><input type="checkbox" bind:checked={testing.autoForward} onchange={() => testing.toggleAutoForward()} /> Auto-forward</label>
    </div>
    {#if testing.portsError}
      <div class="stale">⚠ Builder isn't answering ({testing.portsError}).</div>
    {/if}
    {#each testing.builderPorts as p (p.port)}
      <div class="row">
        <div class="info">
          <span class="mono port">{p.port}</span>
          <span class="faint">{p.process}</span>
        </div>
        {#if testing.forwards[p.port]}
          <button class="btn small primary" onclick={() => openExternal(`http://127.0.0.1:${testing.forwards[p.port]}`)}>
            <Icon name="open" size={14} /> Open :{testing.forwards[p.port]}
          </button>
          <button class="btn small" onclick={() => testing.unforward(p.port)}>Stop</button>
        {:else}
          <button class="btn small primary" disabled={!testing.available} onclick={() => testing.forward(p.port)}>Forward</button>
        {/if}
      </div>
    {:else}
      <p class="faint hint">No listening ports yet. Start a dev server in a terminal to see it here.</p>
    {/each}

    {#each forwardedOnly as p}
      <div class="row">
        <span class="mono port">{p}</span>
        <button class="btn small primary" onclick={() => openExternal(`http://127.0.0.1:${testing.forwards[p]}`)}>
          <Icon name="open" size={14} /> Open :{testing.forwards[p]}
        </button>
        <button class="btn small" onclick={() => testing.unforward(p)}>Stop</button>
      </div>
    {/each}

    <div class="add">
      <input class="field" placeholder="Forward port number" bind:value={manual} inputmode="numeric" onkeydown={(e) => e.key === "Enter" && addManual()} />
      <button class="btn" disabled={!testing.available} onclick={addManual}>Forward</button>
    </div>
  </section>
</div>

<style>
  .ports { flex: 1; overflow: auto; padding: 14px; display: flex; flex-direction: column; gap: 14px; }
  section { display: flex; flex-direction: column; gap: 8px; }
  h4 { margin: 0; font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--dim); }
  .head-row { display: flex; align-items: center; justify-content: space-between; }
  .auto-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--dim); cursor: pointer; user-select: none; }
  .auto-toggle input { cursor: pointer; margin: 0; }
  .row { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 10px; background: #ffffff06; border: 1px solid var(--line); }
  .info { flex: 1; display: flex; align-items: center; gap: 10px; min-width: 0; }
  .port { font-weight: 700; font-size: 15px; }
  .add { display: flex; gap: 8px; margin-top: 6px; }
  .add .field { flex: 1; }
  .hint { margin: 0; font-size: 13px; }
  .note { margin: 0; padding: 10px 12px; border-radius: 8px; background: #2a2619; color: #ffe2b0; }
  .stale { color: var(--warn); font-size: 12.5px; }
</style>
