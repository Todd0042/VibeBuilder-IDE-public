<script lang="ts">
  // The review: every file a change set (or a time range, or one file's history) touched, top to
  // bottom, only the changed parts. Restore puts files back; the restore is itself recorded.
  import DiffFile from "./DiffFile.svelte";
  import Icon from "./Icon.svelte";
  import { clockTime, diffLines, relativeTime, type FileDiff, type FileVersion } from "@core/index";
  import { session } from "../lib/session.svelte";
  import { editors, type ReviewTab } from "../lib/editors.svelte";
  import { changes, SOURCE_LABEL } from "../lib/changes.svelte";
  import { ui } from "../lib/ui.svelte";

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
        // diffs for the newest few right away; older ones load when expanded
        await Promise.all(versions.slice(0, 6).map((v) => loadVersion(v)));
      } else {
        const { hunks, added, removed } = diffLines(src.theirs, src.mine);
        files = [{ path: src.path, status: "modified", before: null, after: null, added, removed, hunks, note: "" }];
        header = { label: "On disk (left/−) vs. your unsaved version (right/+)" };
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

  $effect(() => {
    void tab.source;
    void load();
  });

  async function more(f: FileDiff, context: number) {
    const fresh = await session.api.fileDiff(f.path, f.before, f.after, context);
    files = files.map((x) => (x.path === f.path ? fresh : x));
  }

  async function restoreFile(f: FileDiff) {
    if (!(await ui.confirm(`Restore ${f.path}?`, f.before === null ? "The file didn't exist before this change, so restoring deletes it." : "The file goes back to how it was before this change.", "Restore", true))) return;
    try {
      await session.api.restoreFile(f.path, f.before);
      ui.toast(`Restored ${f.path}`, "ok");
    } catch (e) {
      ui.error(e);
    }
  }

  async function restoreAll() {
    if (tab.source.type !== "changeset") return;
    const id = tab.source.id;
    if (!(await ui.confirm(`Undo all of #${id}?`, `${files.length} file${files.length === 1 ? "" : "s"} go back to how they were before it.`, "Undo changes", true))) return;
    try {
      const r = await session.api.restoreChangeset(id);
      ui.toast(`Restored ${r.restored.length} file${r.restored.length === 1 ? "" : "s"}`, "ok");
    } catch (e) {
      ui.error(e);
    }
  }

  async function restoreVersion(v: FileVersion, which: "before" | "after") {
    if (tab.source.type !== "file") return;
    const state = which === "before" ? v.before : v.after;
    if (!(await ui.confirm("Restore this version?", state === null ? "At that point the file didn't exist: restoring deletes it." : `The file goes back to how it was ${which === "before" ? "before" : "after"} this change (${clockTime(v.ts)}).`, "Restore", true))) return;
    try {
      await session.api.restoreFile(tab.source.path, state);
      ui.toast("Restored", "ok");
      void load();
    } catch (e) {
      ui.error(e);
    }
  }

  const open = (path: string, line: number) => editors.open(path, { line });
  const totals = $derived(files.reduce((a, f) => ({ add: a.add + f.added, del: a.del + f.removed }), { add: 0, del: 0 }));
</script>

<div class="review">
  <div class="bar">
    {#if header.source}<span class="badge src-{header.source}">{SOURCE_LABEL[header.source] ?? header.source}</span>{/if}
    <span class="title">{tab.title}</span>
    {#if header.started && tab.source.type === "changeset"}
      <span class="faint">{clockTime(header.started)}–{clockTime(header.ended ?? header.started)} · {relativeTime(header.ended ?? header.started)}</span>
    {/if}
    {#if header.label && tab.source.type !== "changeset"}<span class="faint">{header.label}</span>{/if}
    <span class="grow"></span>
    {#if files.length}
      <span class="faint">{files.length} file{files.length === 1 ? "" : "s"}</span>
      <span class="plus">+{totals.add}</span><span class="minus">−{totals.del}</span>
    {/if}
    <button class="icon-btn" title="Reload" onclick={load}><Icon name="refresh" /></button>
    {#if tab.source.type === "changeset" && files.length}
      <button class="btn small danger" onclick={restoreAll}><Icon name="undo" size={13} /> Undo all</button>
    {/if}
  </div>

  <div class="list">
    {#if loading}<p class="faint pad">Loading…</p>{/if}
    {#if error}<p class="err pad">{error}</p>{/if}
    {#if !loading && !error && tab.source.type !== "file" && !files.length}
      <p class="faint pad">Nothing changed in this {tab.source.type === "range" ? "time range" : "change set"}{tab.source.type === "range" && !changes.allProjects ? ` in ${ui.project}` : ""}.</p>
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
            <span>{new Date(v.ts * 1000).toLocaleString()}</span>
            <span class="faint">{relativeTime(v.ts)}</span>
            <span class="grow"></span>
            <button class="btn small" onclick={() => restoreVersion(v, "before")}>Restore before this</button>
            <button class="btn small" onclick={() => restoreVersion(v, "after")}>Restore this version</button>
          </div>
          {#if v.diff}
            <DiffFile file={v.diff} onopen={open} />
          {:else}
            <button class="btn small ghost" onclick={() => loadVersion(v)}>Show changes</button>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .review { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .bar { flex: none; display: flex; align-items: center; gap: 10px; padding: 7px 14px; border-bottom: 1px solid var(--line); background: var(--panel); font-size: 12.5px; }
  .title { font-weight: 700; }
  .grow { flex: 1; }
  .plus { color: var(--ok); font: 600 12px var(--mono); }
  .minus { color: var(--bad); font: 600 12px var(--mono); }
  .list { flex: 1; overflow: auto; padding: 14px 18px 60px; display: flex; flex-direction: column; gap: 14px; }
  .pad { padding: 8px 2px; }
  .err { color: var(--bad); }
  .ver { display: flex; flex-direction: column; gap: 6px; }
  .vhead { display: flex; align-items: center; gap: 9px; font-size: 12.5px; }
</style>
