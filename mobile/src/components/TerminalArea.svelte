<script lang="ts">
  import Icon from "./Icon.svelte";
  import TerminalView from "./TerminalView.svelte";
  import { testing } from "@state/testing.svelte";
  import { terminals } from "@state/terminals.svelte";
  import { ui } from "@state/ui.svelte";
  import type { TerminalKind } from "@core/index";

  const NEW: { kind: TerminalKind; label: string }[] = [
    { kind: "claude", label: "claude" }, { kind: "agy", label: "agy" }, { kind: "shell", label: "shell" },
  ];

  let ctrl = $state(false);
  let alt = $state(false);

  function pick(id: string) {
    terminals.activeId = id;
    setTimeout(() => { terminals.fit(id); terminals.focus(id); }, 20);
  }

  function sendKey(seq: string) {
    if (ctrl && seq.length === 1) {
      const code = seq.toUpperCase().charCodeAt(0);
      if (code >= 64 && code <= 95) seq = String.fromCharCode(code - 64);
      ctrl = false;
    } else if (alt && seq.length === 1) {
      seq = "\x1b" + seq;
      alt = false;
    }
    terminals.sendInput(seq);
    terminals.focus(terminals.activeId!);
  }

  function sendText(s: string) {
    terminals.sendInput(s);
    terminals.focus(terminals.activeId!);
  }
</script>

<div class="panel">
  <div class="bar">
    <div class="tabs">
      {#each terminals.list as t (t.id)}
        <div class="tab k-{t.kind}" class:active={t.id === terminals.activeId} role="tab" tabindex="0"
          onclick={() => pick(t.id)} onkeydown={(e) => e.key === "Enter" && pick(t.id)}>
          <span class="kdot"></span>
          <span class="name">{t.title}</span>
          {#if !t.alive || terminals.exited[t.id] !== undefined}<span class="faint small">exit</span>{/if}
          <button class="x" aria-label="Close terminal" onclick={(e) => { e.stopPropagation(); void terminals.close(t.id); }}>
            <Icon name="close" size={13} />
          </button>
        </div>
      {/each}
    </div>
    <button class="runbtn" onclick={() => testing.runApp()}>▶</button>
    {#each NEW as n}
      <button class="newbtn k-{n.kind}" onclick={() => terminals.create(n.kind)}>+{n.label}</button>
    {/each}
  </div>

  <div class="body">
    {#each terminals.list as t (t.id)}
      <TerminalView id={t.id} active={t.id === terminals.activeId} />
    {/each}
    {#if !terminals.list.length}
      <div class="empty">
        <p class="muted">Terminals run in the builder and keep going when the app is closed.</p>
        <div class="starts">
          {#each NEW as n}
            <button class="btn" onclick={() => terminals.create(n.kind)}><Icon name="terminal" size={16} /> {n.label}</button>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  {#if terminals.activeId}
    <div class="kbar">
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendKey("\x1b")}>Esc</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendKey("\t")}>Tab</button>
      <button class="k mod" class:on={ctrl} onpointerdown={(e) => e.preventDefault()} onclick={() => (ctrl = !ctrl)}>Ctrl</button>
      <button class="k mod" class:on={alt} onpointerdown={(e) => e.preventDefault()} onclick={() => (alt = !alt)}>Alt</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendKey("\x1b[A")}>↑</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendKey("\x1b[B")}>↓</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendKey("\x1b[D")}>←</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendKey("\x1b[C")}>→</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendText("/")}>/</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendText("-")}>-</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendText("|")}>|</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => sendText("\x03")}>^C</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => terminals.paste()}>Paste</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => terminals.setFontSize(terminals.fontSize - 1)}>A-</button>
      <button class="k" onpointerdown={(e) => e.preventDefault()} onclick={() => terminals.setFontSize(terminals.fontSize + 1)}>A+</button>
    </div>
  {/if}
</div>

<style>
  .panel { flex: 1; min-height: 0; display: flex; flex-direction: column; background: var(--editor-bg); }
  .bar { height: 42px; flex: none; display: flex; align-items: center; gap: 5px; padding: 0 6px; background: var(--panel); border-bottom: 1px solid var(--line); }
  .tabs { flex: 1; min-width: 0; display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; }
  .tab { flex: none; display: flex; align-items: center; gap: 5px; height: 32px; padding: 0 4px 0 10px; border-radius: 7px; color: var(--dim); background: #ffffff06; }
  .tab.active { background: #ffffff18; color: var(--text); }
  .kdot { width: 7px; height: 7px; border-radius: 50%; background: var(--dim); }
  .k-claude .kdot { background: var(--claude); }
  .k-agy .kdot { background: var(--agy); }
  .k-shell .kdot { background: var(--ok); }
  .k-run .kdot { background: var(--save); }
  .name { font-size: 13px; white-space: nowrap; }
  .small { font-size: 11px; }
  .x { width: 24px; height: 24px; display: grid; place-items: center; border: 0; border-radius: 5px; background: none; color: var(--dim); }
  .runbtn { height: 30px; padding: 0 10px; border-radius: 6px; border: 1px solid #4a3a22; background: #2a2219; color: #ffcf8a; font-weight: 700; flex: none; }
  .newbtn { height: 30px; padding: 0 8px; border-radius: 6px; border: 1px solid var(--line-2); background: #1d2129; color: var(--dim); font-size: 12px; flex: none; }
  .newbtn.k-claude { border-color: #6b432a; color: #ffc49a; }
  .newbtn.k-agy { border-color: #294c70; color: #a9d4ff; }
  .newbtn.k-shell { border-color: #2d4c2e; color: #b8e6b3; }
  .body { flex: 1; min-height: 0; position: relative; }
  .empty { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 24px; text-align: center; }
  .starts { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .kbar { flex: none; display: flex; align-items: center; gap: 4px; padding: 4px 6px; background: #0f1116; border-top: 1px solid var(--line); overflow-x: auto; scrollbar-width: none; }
  .k { flex: none; min-width: 38px; height: 34px; padding: 0 9px; border-radius: 6px; border: 1px solid var(--line-2); background: #1d2129; color: var(--text); font: 600 13px var(--mono); }
  .k:active { background: #2f4168; }
  .k.mod.on { background: var(--accent-2); border-color: var(--accent); color: #fff; }
</style>
