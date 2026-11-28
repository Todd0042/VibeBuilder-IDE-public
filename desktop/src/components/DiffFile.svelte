<script lang="ts">
  // One file in a review, agy-style: a header, then only the changed sections with a few lines of
  // context. "More context" re-asks the server with a wider window; "Whole file" shows everything.
  import Icon from "./Icon.svelte";
  import type { FileDiff, Hunk } from "@core/index";
  import { fileColor } from "../lib/fileIcons";

  let { file, onopen, onrestore, onmore, restoreLabel = "Restore file" }: {
    file: FileDiff;
    onopen?: (path: string, line: number) => void;
    onrestore?: () => void;
    onmore?: (context: number) => Promise<void>;
    restoreLabel?: string;
  } = $props();

  let collapsed = $state(false);
  let context = $state(3);
  let busy = $state(false);

  async function more(n: number) {
    if (!onmore || busy) return;
    busy = true;
    context = n;
    try { await onmore(n); } finally { busy = false; }
  }

  function gap(prev: Hunk | undefined, h: Hunk): number {
    if (!prev) return h.new_start - 1;
    return h.new_start - (prev.new_start + prev.new_count);
  }

  const name = $derived(file.path.slice(file.path.lastIndexOf("/") + 1));
  const dir = $derived(file.path.slice(0, Math.max(0, file.path.lastIndexOf("/"))));
  const firstLine = $derived(file.hunks[0]?.lines.find((l) => l.t !== " ")?.n ?? file.hunks[0]?.new_start ?? 1);
</script>

<section class="file">
  <header>
    <button class="icon-btn" onclick={() => (collapsed = !collapsed)} title={collapsed ? "Expand" : "Collapse"}>
      <Icon name={collapsed ? "chevronRight" : "chevronDown"} size={14} />
    </button>
    <span class="status {file.status}">{file.status === "added" ? "A" : file.status === "deleted" ? "D" : "M"}</span>
    <span class="name" style:color={fileColor(name)}>{name}</span>
    <span class="dir faint">{dir}</span>
    <span class="grow"></span>
    {#if file.added}<span class="plus">+{file.added}</span>{/if}
    {#if file.removed}<span class="minus">−{file.removed}</span>{/if}
    {#if onmore && file.hunks.length}
      <button class="btn small ghost" disabled={busy} onclick={() => more(context + 20)} title="Show more lines around each change">More context</button>
      <button class="btn small ghost" disabled={busy} onclick={() => more(100000)}>Whole file</button>
    {/if}
    {#if onopen && file.status !== "deleted"}
      <button class="btn small ghost" onclick={() => onopen(file.path, firstLine)} title="Open in the editor"><Icon name="open" size={13} /> Open</button>
    {/if}
    {#if onrestore}<button class="btn small" onclick={onrestore} title="Put this file back as it was before this change">{restoreLabel}</button>{/if}
  </header>

  {#if !collapsed}
    {#if file.deferred && onmore}
      <div class="note faint">
        Large changeset — diff deferred to keep loading fast.
        <button class="btn small ghost" disabled={busy} onclick={() => more(3)}>Load diff</button>
      </div>
    {:else if file.note}
      <div class="note faint">{file.note}</div>
    {:else if !file.hunks.length}
      <div class="note faint">{file.status === "added" ? "Empty file" : "No text changes"}</div>
    {:else}
      <div class="code">
        {#each file.hunks as h, i}
          {#if gap(file.hunks[i - 1], h) > 0}
            <button class="gap" onclick={() => more(context + 20)} disabled={!onmore || busy} title="Show the lines in between">
              <Icon name="expand" size={12} /> {gap(file.hunks[i - 1], h)} unchanged line{gap(file.hunks[i - 1], h) === 1 ? "" : "s"}
            </button>
          {/if}
          {#each h.lines as l}
            <div class="ln {l.t === '+' ? 'add' : l.t === '-' ? 'del' : ''}"
              ondblclick={() => onopen && l.n && onopen(file.path, l.n)} role="presentation">
              <span class="no">{l.o ?? ""}</span><span class="no">{l.n ?? ""}</span>
              <span class="sign">{l.t === " " ? "" : l.t === "-" ? "−" : "+"}</span>
              <span class="txt">{l.s || " "}</span>
            </div>
          {/each}
        {/each}
      </div>
    {/if}
  {/if}
</section>

<style>
  .file { flex: 0 0 auto; border: 1px solid var(--line-2); border-radius: 8px; overflow: clip; background: #12141a; }
  header { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 7px; padding: 5px 8px; background: #1a1e26; border-bottom: 1px solid var(--line); }
  .status { font: 700 11px var(--mono); width: 18px; height: 18px; border-radius: 4px; display: grid; place-items: center; }
  .status.modified { background: #3a3218; color: var(--warn); }
  .status.added { background: #1d3324; color: var(--ok); }
  .status.deleted { background: #3a1d22; color: var(--bad); }
  .name { font-weight: 600; }
  .dir { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .grow { flex: 1; }
  .plus { color: var(--ok); font: 600 12px var(--mono); }
  .minus { color: var(--bad); font: 600 12px var(--mono); }
  .note { padding: 10px 14px; font-size: 12.5px; }
  .code { font: 12.8px/1.5 var(--mono); overflow-x: auto; }
  .ln { display: grid; grid-template-columns: 46px 46px 18px 1fr; min-width: max-content; }
  .ln:hover { filter: brightness(1.15); }
  .no { color: #4d5566; text-align: right; padding-right: 8px; user-select: none; font-size: 11.5px; }
  .sign { color: var(--faint); user-select: none; text-align: center; }
  .txt { white-space: pre; padding-right: 20px; color: #c3c8d2; }
  .add { background: var(--add-bg); }
  .add .txt, .add .sign { color: var(--add-fg); }
  .add .no { color: #5f8a63; background: #1a2d20; }
  .del { background: var(--del-bg); }
  .del .txt, .del .sign { color: var(--del-fg); }
  .del .no { color: #9a5f66; background: #33191e; }
  .gap { width: 100%; display: flex; align-items: center; gap: 6px; padding: 3px 12px 3px 100px; border: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); background: #171b22; color: var(--dim); font-size: 11.5px; text-align: left; }
  .gap:not(:disabled):hover { background: #1f2430; color: var(--text); }
</style>
