<script lang="ts">
  import { onMount } from "svelte";
  import { terminals } from "@state/terminals.svelte";
  import { session } from "@state/session.svelte";

  let { id, active }: { id: string; active: boolean } = $props();
  let el: HTMLDivElement | undefined = $state();

  onMount(() => {
    const ro = new ResizeObserver(() => { if (active) terminals.fit(id); });
    ro.observe(el!);
    return () => ro.disconnect();
  });

  $effect(() => {
    if (session.phase !== "ready" || !el) return;
    terminals.attach(id, el);
    requestAnimationFrame(() => terminals.fit(id));
  });

  $effect(() => {
    if (active) requestAnimationFrame(() => { terminals.fit(id); });
  });
</script>

<div class="term" class:hidden={!active} bind:this={el}></div>

<style>
  .term { position: absolute; inset: 4px 4px 0 6px; }
  .hidden { visibility: hidden; pointer-events: none; }
</style>
