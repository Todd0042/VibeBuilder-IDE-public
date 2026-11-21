<script lang="ts" module>
  export type MenuItem = { label: string; run: () => unknown; hint?: string; danger?: boolean } | { sep: true };
</script>

<script lang="ts">
  import { onMount } from "svelte";
  let { x, y, items, onclose }: { x: number; y: number; items: MenuItem[]; onclose: () => void } = $props();
  let el: HTMLDivElement | undefined = $state();
  let pos = $state({ x: 0, y: 0 });

  onMount(() => {
    const r = el!.getBoundingClientRect();
    pos = { x: Math.min(x, window.innerWidth - r.width - 6), y: Math.min(y, window.innerHeight - r.height - 6) };
    const away = (e: Event) => { if (!el?.contains(e.target as Node)) onclose(); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onclose(); };
    setTimeout(() => { window.addEventListener("pointerdown", away); window.addEventListener("keydown", esc); });
    return () => { window.removeEventListener("pointerdown", away); window.removeEventListener("keydown", esc); };
  });
</script>

<div class="menu" bind:this={el} style:left="{pos.x || x}px" style:top="{pos.y || y}px" role="menu">
  {#each items as it}
    {#if "sep" in it}
      <div class="sep"></div>
    {:else}
      <button class="item" class:danger={it.danger} role="menuitem" onclick={() => { onclose(); void it.run(); }}>
        <span>{it.label}</span>{#if it.hint}<span class="hint">{it.hint}</span>{/if}
      </button>
    {/if}
  {/each}
</div>

<style>
  .menu { position: fixed; z-index: 90; min-width: 200px; padding: 4px; border-radius: 8px; background: #1e222b; border: 1px solid var(--line-2); box-shadow: 0 10px 40px #000b; }
  .item { width: 100%; display: flex; justify-content: space-between; gap: 16px; padding: 6px 10px; border: 0; border-radius: 5px; background: none; text-align: left; }
  .item:hover { background: var(--accent-2); color: #fff; }
  .item.danger { color: #ffb3b9; }
  .item.danger:hover { background: #8a2c36; color: #fff; }
  .hint { color: var(--faint); font-size: 11.5px; }
  .item:hover .hint { color: #dde; }
  .sep { height: 1px; margin: 4px 6px; background: var(--line-2); }
</style>
