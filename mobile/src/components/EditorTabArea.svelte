<script lang="ts">
  import logo from "../assets/logo.png";
  import Icon from "./Icon.svelte";
  import CodeEditorView from "./CodeEditorView.svelte";
  import MediaView from "./MediaView.svelte";
  import ReviewView from "./ReviewView.svelte";
  import ActionSheet, { type SheetItem } from "./ActionSheet.svelte";
  import { editors } from "@state/editors.svelte";
  import { ui } from "@state/ui.svelte";
  import { tree, gitClass } from "@state/tree.svelte";
  import { fileColor } from "@state/fileIcons";
  import { cursor } from "@state/cursor.svelte";
  import { languageName } from "@state/codemirror";

  let tabMenu = $state<SheetItem[] | null>(null);
  const active = $derived(editors.active);

  function openActions() {
    const t = active;
    if (!t) return;
    tabMenu = [
      ...(t.kind === "file" ? [
        { label: "Save", run: () => editors.save(t) },
        { label: "Revert File", run: () => editors.revert(t) },
        { label: "File History", run: () => editors.openReview({ type: "file", path: t.path }, `History: ${t.title}`) },
        { label: "Reveal in Explorer", run: () => { ui.mobileView = "files"; void tree.reveal(t.path); } },
        { label: "Copy Path", run: () => navigator.clipboard?.writeText(`/workspace/${t.path}`) },
        { sep: true as const },
      ] : []),
      { label: "Close Tab", run: () => editors.close(t.id) },
      { label: "Close Other Tabs", run: () => editors.closeOthers(t.id) },
      { label: "Close All Tabs", danger: true, run: () => editors.closeAll() },
    ];
  }
</script>

<div class="area">
  {#if editors.tabs.length}
    <div class="tabbar">
      <div class="tabs" role="tablist">
        {#each editors.tabs as t (t.id)}
          <div class="tab" class:active={t.id === editors.activeId} role="tab" tabindex="0" aria-selected={t.id === editors.activeId}
            onclick={() => (editors.activeId = t.id)} onkeydown={(e) => e.key === "Enter" && (editors.activeId = t.id)}>
            {#if t.kind === "file"}
              <span class="dot" style:background={fileColor(t.title)}></span>
              <span class="tname {gitClass(tree.git[t.path])}">{t.title}</span>
              {#if t.dirty}<span class="dirty-dot"></span>{/if}
              {#if t.conflict}<Icon name="warning" size={13} />{/if}
            {:else}
              <span class="rev"><Icon name="changes" size={14} /></span>
              <span class="tname">{t.title}</span>
            {/if}
            <button class="x" aria-label="Close tab" onclick={(e) => { e.stopPropagation(); void editors.close(t.id); }}>
              <Icon name="close" size={14} />
            </button>
          </div>
        {/each}
      </div>
      {#if active}
        <button class="icon-btn" aria-label="Tab actions" onclick={openActions}><Icon name="more" size={18} /></button>
      {/if}
    </div>

    {#if active?.kind === "file"}
      <div class="meta">
        <span class="path faint">{active.path}</span>
        {#if !active.media}
          <span class="faint">Ln {cursor.line}:{cursor.col} · {languageName(active.path)}</span>
        {/if}
      </div>
    {/if}

    <div class="content">
      {#each editors.tabs as t (t.id)}
        <div class="pane" class:hidden={t.id !== editors.activeId}>
          {#if t.kind === "file" && t.media}
            <MediaView tab={t} active={t.id === editors.activeId} />
          {:else if t.kind === "file"}
            <CodeEditorView tab={t} active={t.id === editors.activeId} />
          {:else}
            <ReviewView tab={t} />
          {/if}
        </div>
      {/each}
    </div>
  {:else}
    <div class="welcome">
      <img class="logo" src={logo} alt="VibeBuilder" />
      <h2>No files open</h2>
      <p class="muted">Pick a file from Explorer, use Quick Open, or inspect recent agent Changes.</p>
      <div class="wbtns">
        <button class="btn primary" onclick={() => (ui.quickOpen = true)}><Icon name="search" size={16} /> Go to File</button>
        <button class="btn" onclick={() => (ui.mobileView = "files")}><Icon name="files" size={16} /> Explorer</button>
      </div>
    </div>
  {/if}
</div>

{#if tabMenu}<ActionSheet title={active?.title ?? "Tab"} items={tabMenu} onclose={() => (tabMenu = null)} />{/if}

<style>
  .area { flex: 1; min-height: 0; display: flex; flex-direction: column; background: var(--editor-bg); }
  .tabbar { height: 42px; flex: none; display: flex; align-items: center; background: var(--panel); border-bottom: 1px solid var(--line); }
  .tabs { flex: 1; min-width: 0; display: flex; overflow-x: auto; scrollbar-width: none; height: 100%; }
  .tab {
    flex: none; display: flex; align-items: center; gap: 7px; padding: 0 6px 0 12px; max-width: 210px;
    border-right: 1px solid var(--line); color: var(--dim); border-top: 2px solid transparent;
  }
  .tab.active { background: var(--editor-bg); color: var(--text); border-top-color: var(--accent); }
  .dot { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  .dirty-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--save); flex: none; }
  .rev { color: var(--save); display: grid; flex: none; }
  .tname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13.5px; }
  .x { width: 28px; height: 28px; display: grid; place-items: center; border: 0; background: none; color: var(--dim); border-radius: 6px; flex: none; }
  .x:active { background: #ffffff18; color: var(--text); }
  .meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 3px 12px; background: #101218; border-bottom: 1px solid var(--line); font-size: 11.5px; }
  .path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left; }
  .content { flex: 1; min-height: 0; position: relative; }
  .pane { position: absolute; inset: 0; display: flex; flex-direction: column; }
  .hidden { display: none; }
  .welcome { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 24px; text-align: center; }
  .welcome .logo { width: 64px; height: 64px; border-radius: 16px; }
  .welcome h2 { margin: 0; font-size: 18px; }
  .welcome p { margin: 0; max-width: 280px; }
  .wbtns { display: flex; gap: 10px; margin-top: 6px; }
</style>
