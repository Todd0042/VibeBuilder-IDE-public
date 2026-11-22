<script lang="ts">
  import Icon from "./Icon.svelte";
  import { relativeTime, clockTime, basename } from "@core/index";
  import { changes, SOURCE_LABEL } from "@state/changes.svelte";
  import { editors } from "@state/editors.svelte";
  import { ui } from "@state/ui.svelte";
  import { session } from "@state/session.svelte";

  const RANGES = [
    { label: "15m", sec: 15 * 60 }, { label: "1h", sec: 3600 },
    { label: "4h", sec: 4 * 3600 }, { label: "Today", sec: -1 },
  ];
  let now = $state(Date.now() / 1000);
  $effect(() => { const t = setInterval(() => (now = Date.now() / 1000), 30000); return () => clearInterval(t); });

  function openRange(r: { label: string; sec: number }) {
    const start = new Date(); start.setHours(0, 0, 0, 0);
    const since = r.sec < 0 ? start.getTime() / 1000 : Date.now() / 1000 - r.sec;
    editors.openReview({ type: "range", since, label: r.label }, `Changes: ${r.label}`);
  }

  async function undo(id: number) {
    if (!(await ui.confirm(`Undo change set #${id}?`, "Every file it touched goes back to how it was before it. The undo is itself recorded.", "Undo changes", true))) return;
    try {
      const r = await session.api.restoreChangeset(id);
      ui.toast(`Restored ${r.restored.length} file${r.restored.length === 1 ? "" : "s"}`, "ok");
      void changes.reload();
    } catch (e) { ui.error(e); }
  }

  $effect(() => { void changes.allProjects; void changes.reload(); });
</script>

<div class="changes">
  <div class="bar">
    <span class="title">AGENT CHANGES</span>
    <div class="ranges">
      {#each RANGES as r}<button class="chip" onclick={() => openRange(r)}>{r.label}</button>{/each}
    </div>
    <button class="icon-btn" onclick={() => changes.reload()}><Icon name="refresh" size={18} /></button>
  </div>

  <label class="scope"><input type="checkbox" bind:checked={changes.allProjects} /> Show all projects</label>

  <div class="list">
    {#if changes.open}
      <div class="cs live">
        <span class="pulse"></span>
        <div class="info"><b>Agent is editing…</b><div class="faint">Started {clockTime(changes.open.started)} · updates when it pauses</div></div>
      </div>
    {/if}
    {#each changes.items as cs (cs.id)}
      <div class="cs" role="button" tabindex="0" onclick={() => editors.openReview({ type: "changeset", id: cs.id }, `#${cs.id} ${SOURCE_LABEL[cs.source] ?? cs.source}`)}
        onkeydown={(e) => e.key === "Enter" && editors.openReview({ type: "changeset", id: cs.id }, `#${cs.id}`)}>
        <div class="top">
          <span class="badge src-{cs.source}">{SOURCE_LABEL[cs.source] ?? cs.source}</span>
          <span class="when">{relativeTime(cs.ended, now)}</span>
          <span class="grow"></span>
          <span class="count">{cs.file_count} file{cs.file_count === 1 ? "" : "s"}</span>
          <button class="icon-btn" title="Undo" onclick={(e) => { e.stopPropagation(); void undo(cs.id); }}><Icon name="undo" size={16} /></button>
        </div>
        {#if cs.label}<div class="lbl faint">{cs.label}</div>{/if}
        <div class="paths">{cs.paths.map((p) => basename(p)).join(", ")}{cs.file_count > cs.paths.length ? ` +${cs.file_count - cs.paths.length} more` : ""}</div>
        {#if changes.allProjects}<div class="faint proj">{cs.projects.join(", ")}</div>{/if}
      </div>
    {:else}
      {#if !changes.loading && !changes.open}<p class="faint pad">No agent changes yet{changes.allProjects ? "" : " in this project"}.</p>{/if}
    {/each}
    {#if changes.more && changes.items.length}
      <button class="btn small more" disabled={changes.loading} onclick={() => changes.loadMore()}>Load older…</button>
    {/if}
  </div>
</div>

<style>
  .changes { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .bar { height: 42px; flex: none; display: flex; align-items: center; gap: 6px; padding: 0 6px 0 14px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .title { font-size: 11.5px; font-weight: 700; letter-spacing: .08em; color: var(--dim); margin-right: auto; }
  .ranges { display: flex; gap: 4px; }
  .chip { height: 28px; padding: 0 9px; border-radius: 14px; background: #1f2430; border: 1px solid var(--line-2); font-size: 12px; color: var(--dim); }
  .scope { display: flex; align-items: center; gap: 8px; padding: 8px 14px; font-size: 13px; color: var(--dim); flex: none; border-bottom: 1px solid var(--line); }
  .list { flex: 1; overflow: auto; padding: 8px 10px 28px; display: flex; flex-direction: column; gap: 8px; }
  .cs { padding: 10px 12px; border-radius: 10px; border: 1px solid var(--line); background: #ffffff05; display: flex; flex-direction: column; gap: 4px; }
  .cs:active { background: #ffffff0c; }
  .cs.live { flex-direction: row; align-items: center; gap: 10px; background: #2a221955; border-color: #4a3a22; }
  .top { display: flex; align-items: center; gap: 8px; }
  .when, .count { font-size: 12px; color: var(--dim); }
  .grow { flex: 1; }
  .paths { font: 12.5px var(--mono); color: #b8bfcc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lbl, .proj { font-size: 12px; }
  .pad { padding: 14px 4px; }
  .more { align-self: center; margin-top: 6px; }
  .pulse { width: 10px; height: 10px; border-radius: 50%; background: var(--save); animation: pulse 1.2s infinite; flex: none; }
  @keyframes pulse { 50% { opacity: .3; } }
</style>
