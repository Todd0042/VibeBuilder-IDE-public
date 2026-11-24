<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { gotoLine } from "@codemirror/search";
  import { toggleComment } from "@codemirror/commands";
  import { keymap } from "@codemirror/view";
  import type { Text } from "@codemirror/state";
  import { createEditorBridge, EditorState, EditorView, baseExtensions, languageFor, languageSlot, readOnlySlot } from "@state/codemirror";
  import { editors, type FileTab } from "@state/editors.svelte";
  import { cursor } from "@state/cursor.svelte";
  import { ui } from "@state/ui.svelte";
  import { formatBytes } from "@state/media";
  import { downloadFile } from "@state/fileOps";
  import Icon from "./Icon.svelte";

  let { tab, active }: { tab: FileTab; active: boolean } = $props();
  let host: HTMLDivElement | undefined = $state();
  let view: EditorView | null = null;
  let savedDoc: Text | null = null;
  let created = false;
  let focused = $state(false);

  function make() {
    if (!host || created || tab.loading || tab.binary) return;
    created = true;
    const state = EditorState.create({
      doc: tab.initial,
      extensions: [
        ...baseExtensions(() => void editors.save(tab), true),
        keymap.of([{ key: "Mod-g", run: gotoLine }, { key: "Mod-/", run: toggleComment }]),
        EditorView.domEventHandlers({
          focus: () => { focused = true; },
          blur: () => { focused = false; },
        }),
        EditorView.updateListener.of((u) => {
          if (u.docChanged && savedDoc) editors.changed(tab, !u.state.doc.eq(savedDoc));
          if (u.selectionSet || u.docChanged) {
            const head = u.state.selection.main.head, line = u.state.doc.lineAt(head);
            cursor.set(tab.path, line.number, head - line.from + 1, u.state.selection.ranges.length, u.state.selection.main.to - u.state.selection.main.from);
          }
        }),
      ],
    });
    view = new EditorView({ state, parent: host });
    savedDoc = state.doc;
    void languageFor(tab.path).then((lang) => { if (lang && view) view.dispatch({ effects: languageSlot.reconfigure(lang) }); });
    editors.register(tab, createEditorBridge({
      getView: () => view,
      setSavedDoc: (d) => { savedDoc = d; },
      onPasteError: () => ui.toast("Use keyboard paste", "error"),
    }));
    if (active) cursor.set(tab.path, 1, 1, 1, 0);
  }

  function insertText(s: string) {
    if (!view) return;
    const { from, to } = view.state.selection.main;
    view.dispatch({
      changes: { from, to, insert: s },
      selection: { anchor: from + s.length },
    });
    view.focus();
  }

  onMount(make);
  $effect(() => { void tab.loading; make(); });
  $effect(() => {
    if (active && view) {
      requestAnimationFrame(() => view?.requestMeasure());
      const head = view.state.selection.main.head, line = view.state.doc.lineAt(head);
      cursor.set(tab.path, line.number, head - line.from + 1, 1, 0);
    }
  });
  $effect(() => {
    const ro = !!tab.conflict;
    view?.dispatch({ effects: readOnlySlot.reconfigure(ro ? EditorState.readOnly.of(true) : []) });
  });
  onDestroy(() => {
    editors.register(tab, null);
    view?.destroy();
    view = null;
  });
</script>

{#if tab.conflict}
  <div class="banner conflict">
    <div class="bmsg"><Icon name="warning" size={16} /> <b>{tab.title}</b> changed on disk while you had unsaved edits.</div>
    <div class="bacts">
      <button class="btn small" onclick={() => editors.compare(tab)}>Compare</button>
      <button class="btn small" onclick={() => editors.takeTheirs(tab)}>Take theirs</button>
      <button class="btn small primary" onclick={() => editors.keepMine(tab)}>Keep mine</button>
    </div>
  </div>
{:else if tab.deletedOnDisk}
  <div class="banner gone">
    <div class="bmsg"><Icon name="warning" size={16} /> Deleted on disk. Saving restores it.</div>
    <button class="btn small" onclick={() => editors.close(tab.id, false)}>Close</button>
  </div>
{:else if tab.notice}
  <div class="banner note"><Icon name="check" size={14} /><span>{tab.notice}</span></div>
{/if}

{#if tab.loading}
  <div class="msg faint">Opening…</div>
{:else if tab.binary}
  <div class="bin-view">
    <div class="bin-card">
      <div class="bin-icon"><Icon name="file" size={44} /></div>
      <div class="bin-name">{tab.title}</div>
      <div class="bin-meta faint">
        <span>{tab.path}</span>
        {#if tab.size !== undefined}<span>•</span><span>{formatBytes(tab.size)}</span>{/if}
        {#if tab.mtime}<span>•</span><span>{new Date(tab.mtime * 1000).toLocaleString()}</span>{/if}
      </div>
      <div class="bin-desc faint">Binary file (not displayed as text)</div>
      <div class="bin-acts">
        <button class="btn primary" onclick={() => downloadFile(tab.path)}>
          <Icon name="download" size={14} /> Download
        </button>
        <button class="btn" onclick={() => editors.openAsText(tab.path)}>
          Open as text anyway
        </button>
      </div>
    </div>
  </div>
{:else}
  <div class="cm" bind:this={host}></div>
  {#if active}
    <div class="kbar" class:focused>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => tab.handle?.exec("undo")} title="Undo"><Icon name="undo" size={15} /></button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => tab.handle?.exec("redo")} title="Redo"><Icon name="redo" size={15} /></button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("    ")}>Tab</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("{")}>{"{"}</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("}")}>{"}"}</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("(")}>(</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText(")")}>)</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("[")}>[</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("]")}>]</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => insertText("/")}>/</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => tab.handle?.exec("toggleComment")}>//</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => tab.handle?.exec("find")}><Icon name="search" size={14} /></button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => tab.handle?.exec("gotoLine")}>:Ln</button>
      <button class="k save" class:dirty={tab.dirty} onpointerdown={(e) => e.preventDefault()} onclick={() => editors.save(tab)}>Save</button>
    </div>
  {/if}
{/if}

<style>
  .cm { flex: 1; min-height: 0; overflow: hidden; }
  .cm :global(.cm-editor) { height: 100%; }
  .cm :global(.cm-editor.cm-focused) { outline: none; }
  .msg { padding: 30px 18px; }
  .banner { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; font-size: 13px; flex: none; border-bottom: 1px solid var(--line); }
  .banner.conflict { background: #3a2f18; color: #ffe2b0; }
  .banner.gone { background: #3a1d22; color: #ffd1d5; flex-direction: row; align-items: center; justify-content: space-between; }
  .banner.note { background: #18261a; color: #c8ecc4; flex-direction: row; align-items: center; padding: 6px 12px; font-size: 12px; }
  .bmsg { display: flex; align-items: center; gap: 8px; }
  .bacts { display: flex; gap: 8px; flex-wrap: wrap; }
  .kbar {
    flex: none; display: flex; align-items: center; gap: 4px; padding: 4px 6px;
    background: #0f1116; border-top: 1px solid var(--line); overflow-x: auto; scrollbar-width: none;
  }
  .k {
    flex: none; min-width: 36px; height: 34px; padding: 0 9px; border-radius: 6px;
    border: 1px solid var(--line-2); background: #1d2129; color: var(--text);
    font: 600 13px var(--mono); display: inline-flex; align-items: center; justify-content: center;
  }
  .k:active { background: #2f4168; }
  .k.save.dirty { background: var(--save); border-color: var(--save); color: #1d1405; }
  .bin-view { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; padding: 20px 14px; }
  .bin-card { display: flex; flex-direction: column; align-items: center; text-align: center; width: 100%; max-width: 360px; padding: 24px 16px; background: var(--panel-bg); border: 1px solid var(--line); border-radius: 8px; gap: 10px; }
  .bin-icon { color: var(--dim); margin-bottom: 2px; }
  .bin-name { font-size: 15px; font-weight: 600; word-break: break-all; }
  .bin-meta { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; font-size: 11px; }
  .bin-desc { font-size: 12px; }
  .bin-acts { display: flex; flex-direction: column; width: 100%; gap: 8px; margin-top: 8px; }
</style>
