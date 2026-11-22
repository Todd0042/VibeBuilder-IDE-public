<script lang="ts">
  import DiffFile from "./DiffFile.svelte";
  import Icon from "./Icon.svelte";
  import { clockTime, diffLines, relativeTime, type FileDiff, type FileVersion } from "@core/index";
  import { session } from "@state/session.svelte";
  import { editors, type ReviewTab } from "@state/editors.svelte";
  import { changes, SOURCE_LABEL } from "@state/changes.svelte";
  import { ui } from "@state/ui.svelte";

  let { tab }: { tab: ReviewTab } = $props();
  let files = $state<FileDiff[]>([]);
  let header = $state<{ source?: string; started?: number; ended?: number; label?: string }>({});
  let versions = $state<(FileVersion & { diff?: FileDiff })[]>([]);
  let loading = $state(true);
  let error = $state("");

  async function load() {
    loading = true;
    error = "";
    const src = tab.source;
    try {
      if (src.type === "changeset") {
        const d = await session.api.changeset(src.id);
        files = d.files;
        header = { source: d.source, started: d.started, ended: d.ended, label: d.label };
      } else if (src.type === "range") {
        const d = await session.api.range(src.since, null, 3, changes.allProjects ? "" : ui.project);
        files = d.files;
        header = { label: src.label, started: src.since };
      } else if (src.type === "file") {
        const t = await session.api.fileTimeline(src.path);
        versions = t.versions;
        files = [];
        header = { label: src.path };
        await Promise.all(versions.slice(0, 6).map((v) => loadVersion(v)));
      } else {
        const { hunks, added, removed } = diffLines(src.theirs, src.mine);
        files = [{ path: src.path, status: "modified", before: null, after: null, added, removed, hunks, note: "" }];
        header = { label: "On disk (−) vs. your unsaved version (+)" };
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function loadVersion(v: FileVersion & { diff?: FileDiff }) {
    if (tab.source.type !== "file") return;
    v.diff = await session.api.fileDiff(tab.source.path, v.before, v.after, 3);
    versions = [...versions];
  }

  $effect(() => { void tab.source; void load(); });

  async function more(f: FileDiff, context: number) {
    const fresh = await session.api.fileDiff(f.path, f.before, f.after, context);
    files = files.map((x) => (x.path === f.path ? fresh : x));
  }

  async function restoreFile(f: FileDiff) {
    if (!(await ui.confirm(`Restore ${f.path}?`, f.before === null ? "The file didn't exist before this change, so restoring deletes it." : "The file goes back to how it was before this change.", "Restore", true))) return;
    try {
      await session.api.restoreFile(f.path, f.before);
      ui.toast(`Restored ${f.path}`, "ok");
    } catch (e) { ui.error(e); }
  }

  async function restoreAll() {
    if (tab.source.type !== "changeset") return;
    const id = tab.source.id;
    if (!(await ui.confirm(`Undo all of #${id}?`, `${files.length} file${files.length === 1 ? "" : "s"} go back to how they were before it.`, "Undo changes", true))) return;
    try {
      const r = await session.api.restoreChangeset(id);
      ui.toast(`Restored ${r.restored.length} file${r.restored.length === 1 ? "" : "s"}`, "ok");
    } catch (e) { ui.error(e); }
  }

  async function restoreVersion(v: FileVersion, which: "before" | "after") {
    if (tab.source.type !== "file") return;
    const state = which === "before" ? v.before : v.after;
    if (!(await ui.confirm("Restore this version?", state === null ? "At that point the file didn't exist: restoring deletes it." : `The file goes back to how it was ${which === "before" ? "before" : "after"} this change (${clockTime(v.ts)}).`, "Restore", true))) return;
    try {
      await session.api.restoreFile(tab.source.path, state);
      ui.toast("Restored", "ok");
      void load();
    } catch (e) { ui.error(e); }
  }

  const open = (path: string, line: number) => editors.open(path, { line });
  const totals = $derived(files.reduce((a, f) => ({ add: a.add + f.added, del: a.del + f.removed }), { add: 0, del: 0 }));
</script>

<div class="review">
  <div class="bar">
    <div class="info">
      {#if header.source}<span class="badge src-{header.source}">{SOURCE_LABEL[header.source] ?? header.source}</span>{/if}
      <span class="title">{tab.title}</span>
      {#if files.length}
        <span class="plus">+{totals.add}</span><span class="minus">−{totals.del}</span>
      {/if}
    </div>
    <div class="actions">
      <button class="icon-btn" onclick={load}><Icon name="refresh" size={16} /></button>
      {#if tab.source.type === "changeset" && files.length}
        <button class="btn small danger" onclick={restoreAll}><Icon name="undo" size={13} /> Undo all</button>
      {/if}
    </div>
  </div>
  {#if header.started && tab.source.type === "changeset"}
    <div class="sub faint">{clockTime(header.started)}–{clockTime(header.ended ?? header.started)} · {relativeTime(header.ended ?? header.started)}</div>
  {:else if header.label && tab.source.type !== "changeset"}
    <div class="sub faint">{header.label}</div>
  {/if}

  <div class="list">
    {#if loading}<p class="faint pad">Loading…</p>{/if}
    {#if error}<p class="err pad">{error}</p>{/if}
    {#if !loading && !error && tab.source.type !== "file" && !files.length}
      <p class="faint pad">Nothing changed here.</p>
    {/if}

    {#each files as f (f.path)}
      <DiffFile file={f} onopen={tab.source.type === "compare" ? undefined : open}
        onmore={tab.source.type === "compare" ? undefined : (c) => more(f, c)}
        onrestore={tab.source.type === "compare" ? undefined : () => restoreFile(f)} />
    {/each}

    {#if tab.source.type === "file"}
      {#if !loading && !versions.length}<p class="faint pad">No recorded changes for this file yet.</p>{/if}
      {#each versions as v (v.id)}
        <div class="ver">
          <div class="vhead">
            <span class="badge src-{v.source}">{SOURCE_LABEL[v.source] ?? v.source}</span>
            <span>{relativeTime(v.ts)}</span>
            <span class="grow"></span>
            <button class="btn small" onclick={() => restoreVersion(v, "before")}>Before</button>
            <button class="btn small" onclick={() => restoreVersion(v, "after")}>After</button>
          </div>
          {#if v.diff}
            <DiffFile file={v.diff} onopen={open} />
          {:else}
            <button class="btn small" onclick={() => loadVersion(v)}>Show changes</button>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .review { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .bar { flex: none; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .info { display: flex; align-items: center; gap: 7px; min-width: 0; flex-wrap: wrap; }
  .actions { display: flex; align-items: center; gap: 6px; flex: none; }
  .title { font-weight: 700; font-size: 13.5px; }
  .sub { padding: 4px 12px; font-size: 12px; background: #101218; border-bottom: 1px solid var(--line); }
  .grow { flex: 1; }
  .plus { color: var(--ok); font: 600 12px var(--mono); }
  .minus { color: var(--bad); font: 600 12px var(--mono); }
  .list { flex: 1; overflow: auto; padding: 10px 10px 40px; display: flex; flex-direction: column; gap: 12px; }
  .pad { padding: 8px 4px; }
  .err { color: var(--bad); }
  .ver { display: flex; flex-direction: column; gap: 6px; }
  .vhead { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
</style>
