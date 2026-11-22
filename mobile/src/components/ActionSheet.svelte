<script lang="ts" module>
  export type SheetItem = { label: string; danger?: boolean; run: () => unknown } | { sep: true };
</script>

<script lang="ts">
  let { title = "", items, onclose }: { title?: string; items: SheetItem[]; onclose: () => void } = $props();
</script>

<div class="back" role="presentation" onclick={onclose}>
  <div class="sheet" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === "Escape" && onclose()}>
    {#if title}<div class="title">{title}</div>{/if}
    {#each items as it}
      {#if "sep" in it}
        <div class="sep"></div>
      {:else}
        <button class="item" class:danger={it.danger} onclick={() => { onclose(); void it.run(); }}>
          {it.label}
        </button>
      {/if}
    {/each}
    <button class="cancel" onclick={onclose}>Cancel</button>
  </div>
</div>

<style>
  .back { position: fixed; inset: 0; z-index: 130; background: #0008; display: flex; align-items: flex-end; justify-content: center; }
  .sheet {
    width: min(520px, 100%); background: var(--panel-2); border-top: 1px solid var(--line-2);
    border-radius: 16px 16px 0 0; padding: 10px 12px calc(14px + env(safe-area-inset-bottom, 0px));
    display: flex; flex-direction: column; gap: 4px; max-height: 75vh; overflow: auto;
  }
  .title { padding: 6px 12px 8px; font-size: 12px; color: var(--dim); font-weight: 600; word-break: break-all; }
  .item, .cancel {
    width: 100%; min-height: 44px; padding: 0 14px; border: 0; border-radius: 10px;
    background: none; text-align: left; font-size: 15px; color: var(--text);
  }
  .item:active { background: #ffffff12; }
  .item.danger { color: var(--bad); }
  .sep { height: 1px; background: var(--line); margin: 4px 8px; }
  .cancel { margin-top: 6px; background: #232833; text-align: center; font-weight: 600; color: var(--dim); }
</style>
