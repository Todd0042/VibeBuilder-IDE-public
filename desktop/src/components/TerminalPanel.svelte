<script lang="ts">
  import Icon from "./Icon.svelte";
  import TerminalView from "./TerminalView.svelte";
  import PortsView from "./PortsView.svelte";
  import { testing } from "../lib/testing.svelte";
  import { terminals } from "../lib/terminals.svelte";
  import { ui } from "../lib/ui.svelte";
  import type { TerminalKind } from "@core/index";

  const NEW: { kind: TerminalKind; label: string }[] = [
    { kind: "claude", label: "claude" }, { kind: "agy", label: "agy" }, { kind: "shell", label: "shell" },
  ];

  function pick(id: string) {
    terminals.activeId = id;
    setTimeout(() => { terminals.fit(id); terminals.focus(id); }, 20);
  }
</script>

<div class="bar">
  <div class="seg">
    <button class:on={ui.panelTab === "terminals"} onclick={() => (ui.panelTab = "terminals")}>Terminals</button>
    <button class:on={ui.panelTab === "ports"} onclick={() => (ui.panelTab = "ports")}>
      Ports{#if Object.keys(testing.forwards).length || testing.adb}<span class="cnt">{Object.keys(testing.forwards).length + (testing.adb ? 1 : 0)}</span>{/if}
    </button>
  </div>
  <div class="tabs" class:hidden={ui.panelTab !== "terminals"}>
    {#each terminals.list as t (t.id)}
      <div class="tab k-{t.kind}" class:active={t.id === terminals.activeId} role="tab" tabindex="0" aria-selected={t.id === terminals.activeId}
        onclick={() => pick(t.id)} onkeydown={(e) => e.key === "Enter" && pick(t.id)} onauxclick={(e) => e.button === 1 && terminals.close(t.id)}
        title={`${t.title}${t.cwd ? ` · /workspace/${t.cwd}` : ""}`}>
        <span class="kdot"></span>
        <span class="name">{t.title}</span>
        {#if terminals.states[t.id] === "connecting"}<span class="faint small">…</span>{/if}
        {#if !t.alive || terminals.exited[t.id] !== undefined}<span class="faint small">exited</span>{/if}
        <button class="x" title="Close terminal" onclick={(e) => { e.stopPropagation(); void terminals.close(t.id); }}><Icon name="close" size={12} /></button>
      </div>
    {/each}
  </div>
  <button class="runbtn" title="Run App… (F5): run something in the builder, windows open on this laptop" onclick={() => testing.runApp()}>▶ Run</button>
  <div class="new">
    {#each NEW as n}
      <button class="newbtn k-{n.kind}" title={`New ${n.label} terminal in ${ui.project || "the workspace"}`} onclick={() => terminals.create(n.kind)}>
        <Icon name="plus" size={12} /> {n.label}
      </button>
    {/each}
  </div>
  <div class="tools">
    <button class="icon-btn" title={ui.panelMax ? "Restore panel" : "Maximize panel"} onclick={() => { ui.panelMax = !ui.panelMax; setTimeout(() => terminals.activeId && terminals.fit(terminals.activeId), 30); }}>
      <Icon name={ui.panelMax ? "minimize" : "maximize"} size={14} />
    </button>
    <button class="icon-btn" title="Hide panel (Ctrl+`)" onclick={() => { ui.panelOpen = false; ui.panelMax = false; ui.persist(); }}><Icon name="close" size={14} /></button>
  </div>
</div>

<div class="body">
  {#each terminals.list as t (t.id)}
    <TerminalView id={t.id} active={ui.panelTab === "terminals" && t.id === terminals.activeId} />
  {/each}
  {#if ui.panelTab === "ports"}<PortsView visible={ui.panelTab === "ports"} />{/if}
  {#if !terminals.list.length && ui.panelTab === "terminals"}
    <div class="empty">
      <p class="faint">Terminals run in the builder and keep going when you close the app.</p>
      <div class="starts">
        {#each NEW as n}<button class="btn k-{n.kind}" onclick={() => terminals.create(n.kind)}><Icon name="terminal" size={14} /> {n.label}</button>{/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .bar { height: 34px; flex: none; display: flex; align-items: center; gap: 6px; padding: 0 6px; border-bottom: 1px solid var(--line); background: var(--panel); }
  .tabs { display: flex; gap: 2px; overflow-x: auto; min-width: 0; flex: 1; scrollbar-width: none; }
  .tab { flex: none; display: flex; align-items: center; gap: 6px; height: 26px; padding: 0 4px 0 9px; border-radius: 6px; color: var(--dim); cursor: pointer; user-select: none; }
  .tab:hover { background: #ffffff08; color: var(--text); }
  .tab.active { background: #ffffff12; color: var(--text); }
  .kdot { width: 7px; height: 7px; border-radius: 50%; background: var(--dim); }
  .k-claude .kdot { background: var(--claude); }
  .k-agy .kdot { background: var(--agy); }
  .k-shell .kdot { background: var(--ok); }
  .k-run .kdot { background: var(--save); }
  .seg { display: flex; flex: none; background: #0f1116; border: 1px solid var(--line-2); border-radius: 6px; padding: 2px; gap: 2px; }
  .seg button { height: 22px; padding: 0 9px; border: 0; border-radius: 4px; background: none; color: var(--dim); font-size: 12px; display: inline-flex; align-items: center; gap: 5px; }
  .seg button.on { background: #ffffff14; color: var(--text); }
  .cnt { min-width: 15px; height: 15px; padding: 0 4px; border-radius: 8px; background: var(--ok); color: #0b1a0b; font-size: 10px; font-weight: 800; display: grid; place-items: center; }
  .hidden { visibility: hidden; }
  .runbtn { height: 24px; padding: 0 10px; border-radius: 5px; border: 1px solid #4a3a22; background: #2a2219; color: #ffcf8a; font-size: 12px; font-weight: 600; flex: none; }
  .runbtn:hover { border-color: var(--save); }
  .name { white-space: nowrap; font-size: 12.5px; }
  .small { font-size: 11px; }
  .x { width: 20px; height: 20px; display: grid; place-items: center; border: 0; border-radius: 4px; background: none; color: var(--faint); opacity: 0; }
  .tab:hover .x, .tab.active .x { opacity: 1; }
  .x:hover { background: #ffffff14; color: var(--text); }
  .new { display: flex; gap: 4px; flex: none; }
  .newbtn { height: 24px; display: inline-flex; align-items: center; gap: 4px; padding: 0 8px; border-radius: 5px; border: 1px solid var(--line-2); background: #1d2129; font-size: 12px; color: var(--dim); }
  .newbtn:hover { color: var(--text); }
  .newbtn.k-claude:hover { border-color: var(--claude); }
  .newbtn.k-agy:hover { border-color: var(--agy); }
  .newbtn.k-shell:hover { border-color: var(--ok); }
  .tools { display: flex; flex: none; }
  .body { flex: 1; min-height: 0; position: relative; }
  .empty { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; }
  .starts { display: flex; gap: 8px; }
</style>
