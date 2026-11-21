<script lang="ts">
  import { tick } from "svelte";
  import { ui } from "../lib/ui.svelte";

  let value = $state("");
  let input: HTMLInputElement | undefined = $state();
  let box: HTMLDivElement | undefined = $state();

  $effect(() => {
    const d = ui.dialog;
    if (!d) return;
    value = d.input ?? "";
    void tick().then(() => {
      if (input) {
        input.focus();
        const dot = value.lastIndexOf(".");
        input.setSelectionRange(0, dot > 0 && !value.endsWith("/") ? dot : value.length);
      } else box?.querySelector<HTMLButtonElement>("button.primary, button.danger")?.focus();
    });
  });

  function done(button: string) {
    ui.dialog?.resolve({ button, input: value });
  }

  function key(e: KeyboardEvent) {
    if (!ui.dialog) return;
    if (e.key === "Escape") { e.preventDefault(); done("cancel"); }
    if (e.key === "Enter" && input) {
      e.preventDefault();
      done(ui.dialog.buttons.find((b) => b.primary)?.value ?? "ok");
    }
  }
</script>

<svelte:window onkeydown={key} />

{#if ui.dialog}
  <div class="backdrop" role="presentation" onclick={() => done("cancel")}>
    <div class="dialog" role="dialog" aria-modal="true" tabindex="-1" bind:this={box} onclick={(e) => e.stopPropagation()} onkeydown={() => {}}>
      <h3>{ui.dialog.title}</h3>
      {#if ui.dialog.message}<p>{ui.dialog.message}</p>{/if}
      {#if ui.dialog.input !== undefined}
        <input class="field" bind:this={input} bind:value placeholder={ui.dialog.placeholder ?? ""} spellcheck="false" />
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
  .backdrop { position: fixed; inset: 0; background: #0009; display: grid; place-items: start center; padding-top: 16vh; z-index: 100; }
  .dialog { width: 440px; background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 10px; padding: 18px; box-shadow: 0 20px 60px #000a; display: flex; flex-direction: column; gap: 12px; }
  h3 { margin: 0; font-size: 14px; }
  p { margin: 0; color: var(--dim); }
  .buttons { display: flex; justify-content: flex-end; gap: 8px; }
</style>
