<script lang="ts">
  import { onMount, tick } from "svelte";
  import { fuzzyFilter, type FuzzyHit } from "@core/index";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";
  import { editors } from "../lib/editors.svelte";
  import { fileColor } from "../lib/fileIcons";

  // The file list is cached per project for a minute: Ctrl+P should feel instant.
  const cache = (globalThis as any).__vbFiles ?? ((globalThis as any).__vbFiles = new Map<string, { at: number; files: string[] }>());

  let query = $state("");
  let files = $state<string[]>([]);
  let sel = $state(0);
  let loading = $state(true);
  let input: HTMLInputElement | undefined = $state();
  let listEl: HTMLDivElement | undefined = $state();
  let pendingEnter = false; // Enter pressed before the file list arrived: open the best match when it does

  const recent = $derived(editors.tabs.filter((t) => t.kind === "file").map((t) => (t as { path: string }).path.slice(ui.project.length + 1)));
  const hits: FuzzyHit[] = $derived(query.trim() ? fuzzyFilter(query, files, 60) : recent.concat(files.filter((f) => !recent.includes(f))).slice(0, 60).map((item) => ({ item, score: 0, marks: [] })));

  onMount(async () => {
    await tick();
    input?.focus();
    const c = cache.get(ui.project);
    if (c && Date.now() - c.at < 60_000) { files = c.files; loading = false; }
    try {
      const r = await session.api.files(ui.project);
      files = r.files;
      cache.set(ui.project, { at: Date.now(), files: r.files });
      if (pendingEnter) { await tick(); choose(hits[0]); }
    } catch (e) {
      ui.error(e);
    } finally {
      loading = false;
    }
  });

  $effect(() => { void query; sel = 0; });

  function choose(h: FuzzyHit | undefined) {
    if (!h) return;
    ui.quickOpen = false;
    const m = query.match(/:(\d+)$/);
    void editors.open(`${ui.project}/${h.item}`, m ? { line: Number(m[1]) } : undefined);
  }

  function key(e: KeyboardEvent) {
    if (e.key === "Escape") { e.preventDefault(); ui.quickOpen = false; }
    else if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, hits.length - 1); scroll(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); scroll(); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (loading && query.trim() && !files.length) pendingEnter = true;
      else choose(hits[sel]);
    }
  }

  function scroll() {
    void tick().then(() => listEl?.querySelector(".sel")?.scrollIntoView({ block: "nearest" }));
  }

  function parts(h: FuzzyHit) {
    const set = new Set(h.marks), out: { s: string; m: boolean }[] = [];
    for (let i = 0; i < h.item.length; i++) {
      const m = set.has(i);
      if (out.length && out[out.length - 1].m === m) out[out.length - 1].s += h.item[i];
      else out.push({ s: h.item[i], m });
    }
    return out;
  }
</script>

<div class="back" role="presentation" onclick={() => (ui.quickOpen = false)}>
  <div class="box" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={() => {}}>
    <input bind:this={input} class="field" placeholder="Go to file in {ui.project} (add :line to jump)" bind:value={query} onkeydown={key} spellcheck="false" />
    <div class="list" bind:this={listEl}>
      {#each hits as h, i (h.item)}
        <button class="row" class:sel={i === sel} onmouseenter={() => (sel = i)} onclick={() => choose(h)}>
          <span class="sq" style:background={fileColor(h.item.slice(h.item.lastIndexOf("/") + 1))}></span>
          <span class="name">{h.item.slice(h.item.lastIndexOf("/") + 1)}</span>
          <span class="path">{#each parts(h) as p}{#if p.m}<b>{p.s}</b>{:else}{p.s}{/if}{/each}</span>
        </button>
      {/each}
      {#if !hits.length}<div class="faint pad">{loading ? "Loading files…" : "No matching files"}</div>{/if}
    </div>
  </div>
</div>

<style>
  .back { position: fixed; inset: 0; z-index: 80; background: #0005; display: flex; justify-content: center; padding-top: 70px; }
  .box { width: 620px; max-height: 60vh; display: flex; flex-direction: column; background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 10px; box-shadow: 0 20px 60px #000b; overflow: hidden; align-self: flex-start; }
  .box .field { border-radius: 0; border: 0; border-bottom: 1px solid var(--line-2); height: 40px; font-size: 14px; padding: 0 14px; box-shadow: none; }
  .list { overflow: auto; padding: 4px; }
  .row { width: 100%; display: flex; align-items: center; gap: 9px; padding: 5px 10px; border: 0; border-radius: 6px; background: none; text-align: left; }
  .row.sel { background: #2f4168; }
  .sq { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  .name { font-weight: 600; white-space: nowrap; }
  .path { color: var(--dim); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .path b { color: var(--accent); font-weight: 700; }
  .pad { padding: 10px; }
</style>
