<script lang="ts">
  import { ui } from "../lib/ui.svelte";
</script>

<div class="toasts">
  {#each ui.toasts as t (t.id)}
    <div class="toast {t.kind}">
      <span>{t.text}</span>
      {#if t.action}<button class="btn small" onclick={t.action.run}>{t.action.label}</button>{/if}
    </div>
  {/each}
</div>

<style>
  .toasts { position: fixed; right: 16px; bottom: 34px; display: flex; flex-direction: column; gap: 8px; z-index: 120; pointer-events: none; }
  .toast { pointer-events: auto; max-width: 440px; display: flex; gap: 10px; align-items: center; padding: 9px 12px; border-radius: 8px; background: #222733; border: 1px solid var(--line-2); box-shadow: 0 8px 30px #0008; font-size: 12.5px; }
  .toast.error { border-color: #6a2c34; background: #2c1a1e; }
  .toast.ok { border-color: #2f5a33; background: #18261a; }
</style>
