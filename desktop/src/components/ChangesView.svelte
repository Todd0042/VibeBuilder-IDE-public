<script lang="ts">
  import Icon from "./Icon.svelte";
  import { relativeTime, clockTime, basename } from "@core/index";
  import { changes, SOURCE_LABEL } from "../lib/changes.svelte";
  import { editors } from "../lib/editors.svelte";
  import { ui } from "../lib/ui.svelte";
  import { session } from "../lib/session.svelte";

  const RANGES = [
    { label: "Last 15 minutes", sec: 15 * 60 }, { label: "Last hour", sec: 3600 },
    { label: "Last 4 hours", sec: 4 * 3600 }, { label: "Today", sec: -1 },
  ];
  let now = $state(Date.now() / 1000);
  $effect(() => { const t = setInterval(() => (now = Date.now() / 1000), 30000); return () => clearInterval(t); });

  function openRange(r: { label: string; sec: number }) {
    const start = new Date(); start.setHours(0, 0, 0, 0);
    const since = r.sec < 0 ? start.getTime() / 1000 : Date.now() / 1000 - r.sec;
    editors.openReview({ type: "range", since, label: r.label }, `Changes: ${r.label.toLowerCase()}`);
  }

  async function undo(id: number) {
    if (!(await ui.confirm(`Undo change set #${id}?`, "Every file it touched goes back to how it was before it. The undo is itself recorded, so you can redo it.", "Undo changes", true))) return;
    try {
      const r = await session.api.restoreChangeset(id);
      ui.toast(`Restored ${r.restored.length} file${r.restored.length === 1 ? "" : "s"}`, "ok");
      void changes.reload();
    } catch (e) {
      ui.error(e);
    }
  }

  $effect(() => { void changes.allProjects; void changes.reload(); });
</script>

<div class="head">
  <span class="label">CHANGES</span>
  <div class="tools">
    <button class="icon-btn" title="Refresh" onclick={() => changes.reload()}><Icon name="refresh" /></button>
  </div>
</div>

<div class="ranges">
  {#each RANGES as r}<button class="chip" onclick={() => openRange(r)}>{r.label}</button>{/each}
</div>
<label class="scope"><input type="checkbox" bind:checked={changes.allProjects} /> All projects</label>

<div class="list">
  {#if changes.open}
    <div class="cs live">
      <span class="pulse"></span>
      <div class="info"><b>Agent is editing…</b><div class="faint">Started {clockTime(changes.open.started)} · shows up here when it pauses</div></div>
    </div>
  {/if}
  {#each changes.items as cs (cs.id)}
    <div class="cs" role="button" tabindex="0" onclick={() => editors.openReview({ type: "changeset", id: cs.id }, `#${cs.id} ${SOURCE_LABEL[cs.source] ?? cs.source}`)}
      onkeydown={(e) => e.key === "Enter" && editors.openReview({ type: "changeset", id: cs.id }, `#${cs.id}`)}>
      <div class="top">
        <span class="badge src-{cs.source}">{SOURCE_LABEL[cs.source] ?? cs.source}</span>
        <span class="when" title={new Date(cs.ended * 1000).toLocaleString()}>{relativeTime(cs.ended, now)}</span>
        <span class="grow"></span>
        <span class="count">{cs.file_count} file{cs.file_count === 1 ? "" : "s"}</span>
        <button class="icon-btn undo" title="Undo this change set" onclick={(e) => { e.stopPropagation(); void undo(cs.id); }}><Icon name="undo" size={14} /></button>
      </div>
      {#if cs.label}<div class="lbl faint">{cs.label}</div>{/if}
      <div class="paths">{cs.paths.map((p) => basename(p)).join(", ")}{cs.file_count > cs.paths.length ? ` +${cs.file_count - cs.paths.length} more` : ""}</div>
      {#if changes.allProjects}<div class="faint proj">{cs.projects.join(", ")}</div>{/if}
    </div>
  {:else}
    {#if !changes.loading && !changes.open}<p class="faint pad">No agent changes yet{changes.allProjects ? "" : " in this project"}. When Claude or agy edits files, each burst of edits shows up here.</p>{/if}
  {/each}
  {#if changes.more && changes.items.length}
    <button class="btn small more" disabled={changes.loading} onclick={() => changes.loadMore()}>Older…</button>
  {/if}
</div>

<style>
  .head { height: 36px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 8px 0 14px; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .ranges { display: flex; flex-wrap: wrap; gap: 5px; padding: 0 10px 6px; flex: none; }
  .chip { height: 24px; padding: 0 9px; border-radius: 12px; background: #1f2430; border: 1px solid var(--line-2); font-size: 11.5px; color: var(--dim); }
  .chip:hover { color: var(--text); border-color: #3d4556; }
  .scope { display: flex; align-items: center; gap: 6px; padding: 0 12px 8px; font-size: 12px; color: var(--dim); flex: none; }
  .list { flex: 1; overflow: auto; padding: 0 6px 20px; display: flex; flex-direction: column; gap: 4px; }
  .cs { padding: 8px 9px; border-radius: 7px; border: 1px solid transparent; cursor: pointer; background: #ffffff04; display: flex; flex-direction: column; gap: 3px; }
  .cs:hover { background: #ffffff0a; border-color: var(--line-2); }
  .cs.live { flex-direction: row; align-items: center; gap: 10px; cursor: default; background: #2a221955; border-color: #4a3a22; }
  .top { display: flex; align-items: center; gap: 7px; }
  .when { font-size: 11.5px; color: var(--dim); }
  .grow { flex: 1; }
  .count { font-size: 11.5px; color: var(--dim); }
  .undo { width: 22px; height: 22px; opacity: 0; }
  .cs:hover .undo { opacity: 1; }
  .paths { font: 12px var(--mono); color: #b8bfcc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lbl, .proj { font-size: 11.5px; }
  .pad { padding: 10px 8px; font-size: 12px; }
  .more { align-self: center; margin-top: 6px; }
  .pulse { width: 9px; height: 9px; border-radius: 50%; background: var(--save); animation: pulse 1.2s infinite; flex: none; }
  @keyframes pulse { 50% { opacity: .3; } }
  .info { font-size: 12px; }
</style>
