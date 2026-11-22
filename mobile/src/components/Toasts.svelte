<script lang="ts">
  import { ui } from "@state/ui.svelte";
</script>

<div class="toasts" class:kb={ui.keyboardOpen}>
  {#each ui.toasts as t (t.id)}
    <div class="toast {t.kind}">
      <span>{t.text}</span>
      {#if t.action}<button class="btn small" onclick={t.action.run}>{t.action.label}</button>{/if}
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed; left: 12px; right: 12px;
    bottom: 68px;
    display: flex; flex-direction: column; align-items: center; gap: 8px; z-index: 140; pointer-events: none;
  }
  .toasts.kb { bottom: 48px; }
  .toast {
    pointer-events: auto; width: min(460px, 100%); display: flex; gap: 10px; align-items: center; justify-content: space-between;
    padding: 10px 14px; border-radius: 10px; background: #222733; border: 1px solid var(--line-2);
    box-shadow: 0 8px 30px #0009; font-size: 13px;
  }
  .toast.error { border-color: #6a2c34; background: #2c1a1e; }
  .toast.ok { border-color: #2f5a33; background: #18261a; }
</style>
