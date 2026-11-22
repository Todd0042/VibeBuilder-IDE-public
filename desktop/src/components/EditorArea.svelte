<script lang="ts">
  import logo from "../assets/logo.png";
  import Icon from "./Icon.svelte";
  import CodeEditor from "./CodeEditor.svelte";
  import MediaView from "./MediaView.svelte";
  import ReviewView from "./ReviewView.svelte";
  import ContextMenu, { type MenuItem } from "./ContextMenu.svelte";
  import { editors, type Tab } from "../lib/editors.svelte";
  import { tree } from "../lib/tree.svelte";
  import { ui } from "../lib/ui.svelte";
  import { fileColor } from "../lib/fileIcons";
  import { gitClass } from "../lib/tree.svelte";

  let menu = $state<{ x: number; y: number; items: MenuItem[] } | null>(null);
  let dragId: string | null = null;

  function tabMenu(e: MouseEvent, t: Tab) {
    e.preventDefault();
    menu = {
      x: e.clientX, y: e.clientY, items: [
        { label: "Close", hint: "Ctrl W", run: () => editors.close(t.id) },
        { label: "Close Others", run: () => editors.closeOthers(t.id) },
        { label: "Close All", run: async () => { for (const x of [...editors.tabs]) if (!(await editors.close(x.id))) break; } },
        ...(t.kind === "file" ? [{ sep: true } as MenuItem,
          { label: "Reveal in Explorer", run: () => { ui.side = "explorer"; ui.sideOpen = true; void tree.reveal(t.path); } },
          { label: "History of this file", run: () => openFileHistory(t.path) },
          { label: "Copy Path", run: () => navigator.clipboard.writeText(`/workspace/${t.path}`) }] : []),
      ],
    };
  }

  function openFileHistory(path: string) {
    editors.openReview({ type: "file", path }, `History: ${path.slice(path.lastIndexOf("/") + 1)}`);
  }

  function drop(target: Tab) {
    if (!dragId || dragId === target.id) return;
    const from = editors.tabs.findIndex((x) => x.id === dragId), to = editors.tabs.findIndex((x) => x.id === target.id);
    const list = [...editors.tabs];
    const [moved] = list.splice(from, 1);
    list.splice(to, 0, moved);
    editors.tabs = list;
    dragId = null;
  }
</script>

<div class="area">
  {#if editors.tabs.length}
    <div class="tabs" role="tablist">
      {#each editors.tabs as t (t.id)}
        <div class="tab" class:active={t.id === editors.activeId} role="tab" tabindex="0" aria-selected={t.id === editors.activeId}
          draggable="true" ondragstart={() => (dragId = t.id)} ondragover={(e) => e.preventDefault()} ondrop={() => drop(t)}
          onclick={() => (editors.activeId = t.id)} onauxclick={(e) => e.button === 1 && editors.close(t.id)}
          oncontextmenu={(e) => tabMenu(e, t)} onkeydown={(e) => e.key === "Enter" && (editors.activeId = t.id)} title={t.kind === "file" ? t.path : t.title}>
          {#if t.kind === "file"}
            <span class="dot" style:background={fileColor(t.title)}></span>
            <span class="tname {gitClass(tree.git[t.path])}">{t.title}</span>
            {#if t.conflict}<span class="warn" title="Changed on disk"><Icon name="warning" size={13} /></span>{/if}
          {:else}
            <span class="rev"><Icon name="changes" size={13} /></span>
            <span class="tname">{t.title}</span>
          {/if}
          <button class="x" class:dirty={t.kind === "file" && t.dirty} title={t.kind === "file" && t.dirty ? "Unsaved (click to close)" : "Close"}
            onclick={(e) => { e.stopPropagation(); void editors.close(t.id); }}>
            <span class="circle"></span><Icon name="close" size={13} />
          </button>
        </div>
      {/each}
    </div>
    <div class="content">
      {#each editors.tabs as t (t.id)}
        <div class="pane" class:hidden={t.id !== editors.activeId}>
          {#if t.kind === "file" && t.media}
            <MediaView tab={t} active={t.id === editors.activeId} />
          {:else if t.kind === "file"}
            <CodeEditor tab={t} active={t.id === editors.activeId} />
          {:else}
            <ReviewView tab={t} />
          {/if}
        </div>
      {/each}
    </div>
  {:else}
    <div class="welcome">
      <img class="logo" src={logo} alt="VibeBuilder" />
      <h2>VibeBuilder IDE</h2>
      <div class="hints">
        <span><kbd>Ctrl P</kbd> Go to file</span>
        <span><kbd>Ctrl Shift F</kbd> Search in folder</span>
        <span><kbd>Ctrl Shift G</kbd> Review agent changes</span>
        <span><kbd>Ctrl `</kbd> Terminal</span>
      </div>
    </div>
  {/if}
</div>

{#if menu}<ContextMenu {...menu} onclose={() => (menu = null)} />{/if}

<style>
  .area { flex: 1; min-height: 0; display: flex; flex-direction: column; background: var(--editor-bg); }
  .tabs { height: 36px; flex: none; display: flex; overflow-x: auto; overflow-y: hidden; background: var(--panel); border-bottom: 1px solid var(--line); scrollbar-width: thin; }
  .tabs::-webkit-scrollbar { height: 4px; }
  .tab { flex: none; display: flex; align-items: center; gap: 7px; padding: 0 6px 0 12px; max-width: 240px; border-right: 1px solid var(--line); color: var(--dim); cursor: pointer; user-select: none; border-top: 2px solid transparent; }
  .tab:hover { color: var(--text); }
  .tab.active { background: var(--editor-bg); color: var(--text); border-top-color: var(--accent); }
  .dot { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  .rev { color: var(--save); display: grid; }
  .warn { color: var(--warn); display: grid; }
  .tname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .x { position: relative; width: 22px; height: 22px; display: grid; place-items: center; border: 0; border-radius: 4px; background: none; color: var(--faint); flex: none; }
  .x:hover { background: #ffffff14; color: var(--text); }
  .x :global(svg) { opacity: 0; }
  .tab:hover .x :global(svg), .tab.active .x:not(.dirty) :global(svg) { opacity: 1; }
  .circle { position: absolute; width: 9px; height: 9px; border-radius: 50%; background: var(--text); display: none; }
  .x.dirty .circle { display: block; }
  .x.dirty:hover .circle { display: none; }
  .x.dirty:hover :global(svg) { opacity: 1; }
  .content { flex: 1; min-height: 0; position: relative; }
  .pane { position: absolute; inset: 0; display: flex; flex-direction: column; }
  .hidden { display: none; }
  .welcome { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--dim); }
  .welcome .logo { width: 64px; height: 64px; border-radius: 16px; opacity: .9; }
  .welcome h2 { margin: 0; font-size: 18px; color: var(--text); }
  .hints { display: grid; grid-template-columns: auto auto; gap: 8px 24px; font-size: 12.5px; }
</style>
