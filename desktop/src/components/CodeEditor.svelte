<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { gotoLine, openSearchPanel } from "@codemirror/search";
  import { redo, selectAll, toggleComment, undo } from "@codemirror/commands";
  import { keymap } from "@codemirror/view";
  import type { Text } from "@codemirror/state";
  import { EditorState, EditorView, baseExtensions, languageFor, languageSlot, readOnlySlot } from "../lib/codemirror";
  import { editors, type FileTab } from "../lib/editors.svelte";
  import { cursor } from "../lib/cursor.svelte";
  import { ui } from "../lib/ui.svelte";
  import { formatBytes } from "../lib/media";
  import { downloadFile } from "../lib/fileOps";
  import Icon from "./Icon.svelte";

  let { tab, active }: { tab: FileTab; active: boolean } = $props();
  let host: HTMLDivElement | undefined = $state();
  let view: EditorView | null = null;
  let savedDoc: Text | null = null;
  let created = false;

  function make() {
    if (!host || created || tab.loading || tab.binary) return;
    created = true;
    const state = EditorState.create({
      doc: tab.initial,
      extensions: [
        ...baseExtensions(() => void editors.save(tab)),
        keymap.of([{ key: "Mod-g", run: gotoLine }, { key: "Alt-g", run: gotoLine }, { key: "Mod-/", run: toggleComment }]),
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
    editors.register(tab, {
      exec: (cmd) => {
        const v = view;
        if (!v) return;
        v.focus();
        if (cmd === "undo") undo(v);
        else if (cmd === "redo") redo(v);
        else if (cmd === "selectAll") selectAll(v);
        else if (cmd === "toggleComment") toggleComment(v);
        else if (cmd === "gotoLine") gotoLine(v);
        else if (cmd === "find" || cmd === "replace") {
          openSearchPanel(v);
          if (cmd === "replace") requestAnimationFrame(() => v.dom.querySelector<HTMLInputElement>(".cm-search input[name=replace]")?.focus());
        } else if (cmd === "copy" || cmd === "cut") {
          const sel = v.state.sliceDoc(v.state.selection.main.from, v.state.selection.main.to);
          if (sel) {
            void navigator.clipboard.writeText(sel);
            if (cmd === "cut") v.dispatch(v.state.replaceSelection(""));
          }
        } else if (cmd === "paste") {
          navigator.clipboard.readText()
            .then((t) => v.dispatch(v.state.replaceSelection(t)))
            .catch(() => ui.toast("Paste with Ctrl+V here", "error"));
        }
      },
      getText: () => view!.state.doc.toString(),
      setText: (text, keepCursor) => {
        if (!view) return;
        const sel = view.state.selection.main.head;
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
          selection: keepCursor ? { anchor: Math.min(sel, text.length) } : undefined,
        });
      },
      markSaved: () => { if (view) savedDoc = view.state.doc; },
      goTo: (line, col = 0, length = 0) => {
        if (!view) return;
        const l = view.state.doc.line(Math.max(1, Math.min(line, view.state.doc.lines)));
        const from = Math.min(l.from + col, l.to);
        view.dispatch({ selection: { anchor: from, head: Math.min(from + length, l.to) }, scrollIntoView: true,
          effects: EditorView.scrollIntoView(from, { y: "center" }) });
        focusUnlessDialog();
      },
      focus: () => view?.focus(),
    });
    if (active) {
      cursor.set(tab.path, 1, 1, 1, 0);
      requestAnimationFrame(focusUnlessDialog);
    }
  }

  // Files open asynchronously: by the time one has loaded (or jumped to a search hit), a dialog such as
  // Go to File may have opened. Taking focus then would send its typing and Enter into the editor.
  function focusUnlessDialog() {
    if (document.activeElement?.closest('[role="dialog"], [role="alertdialog"]')) return;
    view?.focus();
  }

  onMount(make);
  $effect(() => {
    // waits for the file to load
    void tab.loading;
    make();
  });
  $effect(() => {
    if (active && view) {
      requestAnimationFrame(() => { view?.requestMeasure(); });
      const head = view.state.selection.main.head, line = view.state.doc.lineAt(head);
      cursor.set(tab.path, line.number, head - line.from + 1, 1, 0);
    }
  });
  $effect(() => {
    // read-only while the file has a conflict, so you decide first
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
    <Icon name="warning" size={15} />
    <span><b>{tab.title}</b> was changed on disk (probably by an agent) while you had unsaved edits.</span>
    <div class="grow"></div>
    <button class="btn small" onclick={() => editors.compare(tab)}>Compare</button>
    <button class="btn small" onclick={() => editors.takeTheirs(tab)}>Take theirs</button>
    <button class="btn small primary" onclick={() => editors.keepMine(tab)}>Keep mine</button>
  </div>
{:else if tab.deletedOnDisk}
  <div class="banner gone">
    <Icon name="warning" size={15} />
    <span>This file was deleted on disk. Saving puts it back.</span>
    <div class="grow"></div>
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
{/if}

<style>
  .cm { flex: 1; min-height: 0; overflow: hidden; }
  .cm :global(.cm-editor) { height: 100%; }
  .cm :global(.cm-editor.cm-focused) { outline: none; }
  .msg { padding: 30px; }
  .banner { display: flex; align-items: center; gap: 9px; padding: 7px 12px; font-size: 12.5px; flex: none; border-bottom: 1px solid var(--line); }
  .banner.conflict { background: #3a2f18; color: #ffe2b0; }
  .banner.gone { background: #3a1d22; color: #ffd1d5; }
  .banner.note { background: #18261a; color: #c8ecc4; padding: 4px 12px; font-size: 12px; }
  .grow { flex: 1; }
  .bin-view { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; padding: 24px; }
  .bin-card { display: flex; flex-direction: column; align-items: center; text-align: center; max-width: 440px; padding: 32px 24px; background: var(--panel-bg); border: 1px solid var(--line); border-radius: 8px; gap: 10px; }
  .bin-icon { color: var(--dim); margin-bottom: 4px; }
  .bin-name { font-size: 16px; font-weight: 600; word-break: break-all; }
  .bin-meta { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; font-size: 12px; }
  .bin-desc { font-size: 13px; }
  .bin-acts { display: flex; gap: 10px; margin-top: 8px; }
</style>
