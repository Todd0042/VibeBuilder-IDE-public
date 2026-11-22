<script lang="ts">
  import { tick } from "svelte";
  import { ui } from "@state/ui.svelte";

  let value = $state("");
  let checks = $state<Record<string, boolean>>({});
  let input: HTMLInputElement | undefined = $state();

  $effect(() => {
    const d = ui.dialog;
    if (!d) return;
    value = d.input ?? "";
    checks = Object.fromEntries((d.checks ?? []).map((c) => [c.id, c.checked]));
    void tick().then(() => {
      if (input) {
        input.focus();
        const dot = value.lastIndexOf(".");
        input.setSelectionRange(0, dot > 0 && !value.endsWith("/") ? dot : value.length);
      }
    });
  });

  function done(button: string) {
    ui.dialog?.resolve({ button, input: value, checks: { ...checks } });
  }
</script>

{#if ui.dialog}
  <div class="backdrop" role="presentation" onclick={() => done("cancel")}>
    <div class="dialog" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === "Escape") done("cancel"); if (e.key === "Enter" && input) done(ui.dialog?.buttons.find((b) => b.primary)?.value ?? "ok"); }}>
      <h3>{ui.dialog.title}</h3>
      {#if ui.dialog.message}<p>{ui.dialog.message}</p>{/if}
      {#if ui.dialog.input !== undefined}
        <input class="field" bind:this={input} bind:value placeholder={ui.dialog.placeholder ?? ""} spellcheck="false" />
      {/if}
      {#if ui.dialog.checks?.length}
        <div class="checks">
          {#each ui.dialog.checks as c (c.id)}
            <label class="chk">
              <input type="checkbox" bind:checked={checks[c.id]} />
              <span>{c.label}</span>
            </label>
          {/each}
        </div>
      {/if}
      <div class="buttons">
        {#each ui.dialog.buttons as b}
          <button class="btn" class:primary={b.primary} class:danger={b.danger} onclick={() => done(b.value)}>{b.label}</button>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop { position: fixed; inset: 0; background: #000a; display: grid; place-items: start center; padding: 14vh 16px 16px; z-index: 150; }
  .dialog { width: min(420px, 100%); background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 14px; padding: 18px; box-shadow: 0 20px 60px #000a; display: flex; flex-direction: column; gap: 14px; }
  h3 { margin: 0; font-size: 16px; }
  p { margin: 0; color: var(--dim); line-height: 1.45; }
  .checks { display: flex; flex-direction: column; gap: 10px; }
  .chk { display: flex; align-items: center; gap: 10px; min-height: 36px; font-size: 14.5px; color: var(--text); }
  .chk input { width: 20px; height: 20px; accent-color: var(--accent-2); flex: none; }
  .buttons { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
</style>
