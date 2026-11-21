<script lang="ts">
  import { onMount } from "svelte";
  import { terminals } from "../lib/terminals.svelte";
  import { session } from "../lib/session.svelte";

  let { id, active }: { id: string; active: boolean } = $props();
  let el: HTMLDivElement | undefined = $state();

  onMount(() => {
    const ro = new ResizeObserver(() => { if (active) terminals.fit(id); });
    ro.observe(el!);
    return () => ro.disconnect();
  });

  // (Re)attach whenever signed in: after a lock the old connection is gone; the builder kept the
  // terminal running and replays its scrollback.
  $effect(() => {
    if (session.phase !== "ready" || !el) return;
    terminals.attach(id, el);
    requestAnimationFrame(() => terminals.fit(id));
  });

  $effect(() => {
    if (active) requestAnimationFrame(() => { terminals.fit(id); terminals.focus(id); });
  });
</script>

<div class="term" class:hidden={!active} bind:this={el}></div>

<style>
  .term { position: absolute; inset: 4px 0 0 10px; }
  .hidden { visibility: hidden; pointer-events: none; }
</style>
