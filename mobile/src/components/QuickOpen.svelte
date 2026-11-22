<script lang="ts">
  import { onMount, tick } from "svelte";
  import { fuzzyFilter, type FuzzyHit } from "@core/index";
  import { session } from "@state/session.svelte";
  import { ui } from "@state/ui.svelte";
  import { editors } from "@state/editors.svelte";
  import { fileColor } from "@state/fileIcons";

  const cache = (globalThis as any).__vbFiles ?? ((globalThis as any).__vbFiles = new Map<string, { at: number; files: string[] }>());

  let query = $state("");
  let files = $state<string[]>([]);
  let loading = $state(true);
  let input: HTMLInputElement | undefined = $state();

  const recent = $derived(editors.tabs.filter((t) => t.kind === "file").map((t) => {
    const p = (t as { path: string }).path;
    return ui.project ? p.slice(ui.project.length + 1) : p;
  }));
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
    } catch (e) { ui.error(e); }
    finally { loading = false; }
  });

  function choose(h: FuzzyHit) {
    ui.quickOpen = false;
    const m = query.match(/:(\d+)$/);
    const full = ui.project ? `${ui.project}/${h.item}` : h.item;
    void editors.open(full, m ? { line: Number(m[1]) } : undefined);
  }
</script>

<div class="back" role="presentation" onclick={() => (ui.quickOpen = false)}>
  <div class="box" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.key === "Escape" && (ui.quickOpen = false)}>
    <div class="head">
      <input bind:this={input} class="field" placeholder="Go to file in {ui.project || 'Workspace'} (:line)" bind:value={query} spellcheck="false" />
      <button class="btn small" onclick={() => (ui.quickOpen = false)}>Close</button>
    </div>
    <div class="list">
      {#each hits as h (h.item)}
        <button class="row" onclick={() => choose(h)}>
          <span class="sq" style:background={fileColor(h.item.slice(h.item.lastIndexOf("/") + 1))}></span>
          <div class="txt">
            <div class="name">{h.item.slice(h.item.lastIndexOf("/") + 1)}</div>
            <div class="path faint">{h.item}</div>
          </div>
        </button>
      {/each}
      {#if !hits.length}<div class="faint pad">{loading ? "Loading files…" : "No matching files"}</div>{/if}
    </div>
  </div>
</div>

<style>
  .back { position: fixed; inset: 0; z-index: 120; background: #0008; display: flex; justify-content: center; padding: 14px; }
  .box {
    width: min(520px, 100%); max-height: 75dvh; display: flex; flex-direction: column;
    background: var(--panel-2); border: 1px solid var(--line-2); border-radius: 14px; overflow: hidden; align-self: flex-start;
  }
  .head { display: flex; gap: 8px; padding: 10px; border-bottom: 1px solid var(--line); }
  .head .field { flex: 1; }
  .list { overflow: auto; padding: 6px; }
  .row { width: 100%; display: flex; align-items: center; gap: 10px; padding: 10px; border: 0; border-radius: 8px; background: none; text-align: left; }
  .row:active { background: #2f4168; }
  .sq { width: 9px; height: 9px; border-radius: 2px; flex: none; }
  .txt { min-width: 0; flex: 1; }
  .name { font-weight: 600; font-size: 14px; }
  .path { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pad { padding: 14px; }
</style>
