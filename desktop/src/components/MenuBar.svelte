<script lang="ts">
  // File / Edit / View / Go / Terminal / Help. Click a menu to open it; while one is open, hovering
  // another switches to it (like a desktop app). Alt+F, Alt+E, … open them from the keyboard (not
  // while a terminal has focus: there Alt+letter belongs to the shell).
  import { tick } from "svelte";
  import { commands, focusIn, MENUS, type Command, type MenuEntry } from "../lib/commands";
  import { ui } from "../lib/ui.svelte";

  let open = $state<number | null>(null);
  let sel = $state(-1);
  let bar: HTMLElement | undefined = $state();

  type Row = { kind: "cmd"; id: string; c: Command } | { kind: "sep" } | { kind: "project"; name: string } | { kind: "label"; text: string };

  function rows(items: MenuEntry[]): Row[] {
    const out: Row[] = [];
    for (const it of items) {
      if (it === "-") out.push({ kind: "sep" });
      else if (typeof it === "object") {
        out.push({ kind: "label", text: "Folders" });
        for (const p of ui.folderChoices) out.push({ kind: "project", name: p });
      } else out.push({ kind: "cmd", id: it, c: commands[it] as Command });
    }
    return out;
  }

  const current = $derived(open === null ? [] : rows(MENUS[open].items));
  const actionable = (r: Row) => (r.kind === "cmd" && (!r.c.enabled || r.c.enabled())) || r.kind === "project";

  function show(i: number | null, focusFirst = false) {
    open = i;
    sel = -1;
    if (i !== null && focusFirst) void tick().then(() => move(1));
  }

  function run(r: Row) {
    if (!actionable(r)) return;
    show(null);
    if (r.kind === "cmd") void r.c.run();
    else if (r.kind === "project") ui.openFolder(r.name);
  }

  function move(d: 1 | -1) {
    const list = current;
    if (!list.length) return;
    let i = sel;
    for (let n = 0; n < list.length; n++) {
      i = (i + d + list.length) % list.length;
      if (actionable(list[i])) { sel = i; return; }
    }
  }

  function key(e: KeyboardEvent) {
    if (ui.dialog) return;
    if (open === null) {
      if (e.altKey && !e.ctrlKey && !e.shiftKey && focusIn() !== "terminal") {
        const i = MENUS.findIndex((m) => m.key === e.key.toLowerCase());
        if (i >= 0) { e.preventDefault(); e.stopPropagation(); show(i, true); }
      }
      return;
    }
    const stop = () => { e.preventDefault(); e.stopPropagation(); };
    if (e.key === "Escape") { stop(); show(null); }
    else if (e.key === "ArrowDown") { stop(); move(1); }
    else if (e.key === "ArrowUp") { stop(); move(-1); }
    else if (e.key === "ArrowRight") { stop(); show((open + 1) % MENUS.length, true); }
    else if (e.key === "ArrowLeft") { stop(); show((open - 1 + MENUS.length) % MENUS.length, true); }
    else if (e.key === "Enter") { stop(); if (sel >= 0) run(current[sel]); }
  }

  function away(e: PointerEvent) {
    if (open !== null && !bar?.contains(e.target as Node)) show(null);
  }
</script>

<svelte:window onkeydowncapture={key} onpointerdowncapture={away} />

<nav class="menubar" bind:this={bar}>
  {#each MENUS as m, i}
    <div class="menu">
      <button class="top" class:open={open === i} onclick={() => show(open === i ? null : i)} onmouseenter={() => open !== null && show(i)}>
        {m.label}
      </button>
      {#if open === i}
        <div class="drop" role="menu">
          {#each current as r, j}
            {#if r.kind === "sep"}
              <div class="sep"></div>
            {:else if r.kind === "label"}
              <div class="label">{r.text}</div>
            {:else if r.kind === "project"}
              <button class="item" class:sel={sel === j} role="menuitemradio" aria-checked={ui.project === r.name}
                onmouseenter={() => (sel = j)} onclick={() => run(r)}>
                <span class="check">{ui.project === r.name ? "●" : ""}</span><span class="name">{r.name}</span><span class="keys"></span>
              </button>
            {:else}
              {@const disabled = !!r.c.enabled && !r.c.enabled()}
              <button class="item" class:sel={sel === j} class:disabled role="menuitem" aria-disabled={disabled}
                onmouseenter={() => (sel = disabled ? -1 : j)} onclick={() => run(r)}>
                <span class="check">{r.c.checked?.() ? "✓" : ""}</span>
                <span class="name">{r.c.label}</span>
                <span class="keys">{r.c.keys ?? ""}</span>
              </button>
            {/if}
          {/each}
        </div>
      {/if}
    </div>
  {/each}
</nav>

<style>
  .menubar { display: flex; align-items: center; gap: 1px; }
  .menu { position: relative; }
  .top { height: 26px; padding: 0 9px; border: 0; border-radius: 5px; background: none; color: var(--dim); font-size: 12.5px; }
  .top:hover, .top.open { background: #ffffff12; color: var(--text); }
  .drop { position: absolute; top: 30px; left: 0; z-index: 95; min-width: 260px; padding: 4px; border-radius: 8px; background: #1e222b; border: 1px solid var(--line-2); box-shadow: 0 12px 40px #000c; }
  .item { width: 100%; display: grid; grid-template-columns: 18px 1fr auto; align-items: center; gap: 4px; height: 27px; padding: 0 10px 0 4px; border: 0; border-radius: 5px; background: none; text-align: left; font-size: 12.5px; }
  .item.sel { background: var(--accent-2); color: #fff; }
  .item.disabled { color: #5f6878; cursor: default; }
  .check { text-align: center; color: var(--accent); font-size: 11px; }
  .item.sel .check { color: #fff; }
  .keys { color: var(--faint); font-size: 11.5px; padding-left: 20px; }
  .item.sel .keys { color: #dde4f5; }
  .sep { height: 1px; margin: 4px 8px; background: var(--line-2); }
  .label { padding: 4px 10px 2px 26px; font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase; color: var(--faint); }
</style>
