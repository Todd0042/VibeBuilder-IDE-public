<script lang="ts">
  import { onMount, tick } from "svelte";
  import Icon from "./Icon.svelte";
  import type { SearchResult } from "@core/index";
  import { session } from "../lib/session.svelte";
  import { ui } from "../lib/ui.svelte";
  import { editors } from "../lib/editors.svelte";
  import { searchRoot } from "../lib/searchRoot";
  import { fileColor } from "../lib/fileIcons";

  let query = $state("");
  let regex = $state(false);
  let caseSensitive = $state(false);
  let wholeWord = $state(false);
  let include = $state("");
  let exclude = $state("");
  let showFilters = $state(false);
  let root = $state("");
  let result = $state<SearchResult | null>(null);
  let busy = $state(false);
  let error = $state("");
  let collapsed = $state<Record<string, boolean>>({});
  let input: HTMLInputElement | undefined = $state();
  let timer: ReturnType<typeof setTimeout> | null = null;
  let seq = 0;

  const scope = $derived(root || ui.project);

  onMount(() => searchRoot.listen((dir) => { root = dir; ui.side = "search"; ui.sideOpen = true; void tick().then(() => input?.focus()); }));

  // Ctrl+Shift+F: focus (with the selected text, if any)
  $effect(() => {
    const s = ui.searchSeed;
    if (!s.n) return;
    if (s.text) query = s.text;
    void tick().then(() => { input?.focus(); input?.select(); if (query) run(); });
  });

  $effect(() => {
    void ui.project;
    root = "";
    result = null;
  });

  function changed() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(run, 350);
  }

  async function run() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (!query.trim() || !scope) { result = null; error = ""; return; }
    const my = ++seq;
    busy = true;
    error = "";
    try {
      const r = await session.api.search({ query, root: scope, regex, case_sensitive: caseSensitive, whole_word: wholeWord, include, exclude });
      if (my === seq) { result = r; collapsed = {}; }
    } catch (e) {
      if (my === seq) { error = e instanceof Error ? e.message : String(e); result = null; }
    } finally {
      if (my === seq) busy = false;
    }
  }

  function toggle(flag: "regex" | "case" | "word") {
    if (flag === "regex") regex = !regex;
    if (flag === "case") caseSensitive = !caseSensitive;
    if (flag === "word") wholeWord = !wholeWord;
    run();
  }

  function rel(path: string) {
    return path.startsWith(ui.project + "/") ? path.slice(ui.project.length + 1) : path;
  }

  function pieces(text: string, ranges: [number, number][]) {
    const out: { s: string; hit: boolean }[] = [];
    // trim long leading whitespace and very long lines around the first hit
    let start = 0;
    const first = ranges[0]?.[0] ?? 0;
    if (first > 60) start = first - 40;
    let pos = start;
    for (const [a, b] of ranges) {
      if (b <= pos) continue;
      if (a > pos) out.push({ s: text.slice(pos, a), hit: false });
      out.push({ s: text.slice(Math.max(a, pos), b), hit: true });
      pos = b;
    }
    out.push({ s: text.slice(pos, pos + 300), hit: false });
    if (start > 0) out.unshift({ s: "…", hit: false });
    return out;
  }
</script>

<div class="head"><span class="label">SEARCH</span>
  <button class="icon-btn" class:on={showFilters} title="Files to include / exclude" onclick={() => (showFilters = !showFilters)}>⋯</button>
</div>
<div class="form">
  <div class="qbox">
    <input bind:this={input} class="field" placeholder="Search" bind:value={query} oninput={changed} onkeydown={(e) => e.key === "Enter" && run()} spellcheck="false" />
    <div class="flags">
      <button class="icon-btn small" class:on={caseSensitive} title="Match case" onclick={() => toggle("case")}>Aa</button>
      <button class="icon-btn small" class:on={wholeWord} title="Whole word" onclick={() => toggle("word")}><u>ab</u></button>
      <button class="icon-btn small" class:on={regex} title="Regular expression" onclick={() => toggle("regex")}>.*</button>
    </div>
  </div>
  {#if showFilters}
    <input class="field" placeholder="files to include (e.g. *.py, src/**)" bind:value={include} oninput={changed} />
    <input class="field" placeholder="files to exclude (e.g. *.min.js)" bind:value={exclude} oninput={changed} />
  {/if}
  <div class="scope">
    in <b>{scope || "—"}</b>
    {#if root}<button class="link" onclick={() => { root = ""; run(); }}>whole project</button>{/if}
  </div>
</div>

<div class="results">
  {#if busy}<div class="faint pad">Searching…</div>{/if}
  {#if error}<div class="err pad">{error}</div>{/if}
  {#if result && !busy}
    <div class="summary pad faint">
      {result.match_count} result{result.match_count === 1 ? "" : "s"} in {result.files.length} file{result.files.length === 1 ? "" : "s"}{result.truncated ? " (stopped early: narrow the search)" : ""}
      {#if result.skipped_count}
        <div class="skipped" title={(result.skipped ?? []).map((s) => `${s.path}: ${s.reason}`).join("\n") + (result.skipped_count > (result.skipped?.length ?? 0) ? "\n…" : "")}>
          ⚠ {result.skipped_count} file{result.skipped_count === 1 ? "" : "s"} couldn't be searched{result.skipped?.length ? ` (e.g. ${result.skipped[0].path}: ${result.skipped[0].reason})` : ""}
        </div>
      {/if}
      {#if result.not_text_matches}
        <div class="skipped">{result.not_text_matches} more match{result.not_text_matches === 1 ? "" : "es"} in files that aren't plain UTF-8 text (not shown)</div>
      {/if}
    </div>
    {#each result.files as f (f.path)}
      <button class="file" onclick={() => (collapsed[f.path] = !collapsed[f.path])}>
        <Icon name={collapsed[f.path] ? "chevronRight" : "chevronDown"} size={13} />
        <span class="fname" style:color={fileColor(f.path)}>{f.path.slice(f.path.lastIndexOf("/") + 1)}</span>
        <span class="fdir faint">{rel(f.path).slice(0, Math.max(0, rel(f.path).lastIndexOf("/")))}</span>
        <span class="n">{f.matches.length}</span>
      </button>
      {#if !collapsed[f.path]}
        {#each f.matches as m}
          <button class="match" onclick={() => editors.open(f.path, { line: m.line, col: m.ranges[0]?.[0] ?? 0, length: (m.ranges[0]?.[1] ?? 0) - (m.ranges[0]?.[0] ?? 0) })}>
            <span class="ln">{m.line}</span>
            <span class="txt">{#each pieces(m.text, m.ranges) as p}{#if p.hit}<mark>{p.s}</mark>{:else}{p.s}{/if}{/each}</span>
          </button>
        {/each}
      {/if}
    {/each}
  {/if}
</div>

<style>
  .head { height: 36px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 8px 0 14px; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--dim); }
  .form { padding: 0 10px 8px; display: flex; flex-direction: column; gap: 6px; flex: none; }
  .qbox { position: relative; }
  .qbox .field { padding-right: 86px; }
  .flags { position: absolute; right: 3px; top: 2px; display: flex; }
  .icon-btn.small { width: 26px; height: 26px; font: 600 11.5px var(--mono); }
  .scope { font-size: 11.5px; color: var(--dim); display: flex; gap: 8px; }
  .link { background: none; border: 0; padding: 0; color: var(--accent); font-size: 11.5px; }
  .results { flex: 1; overflow: auto; padding-bottom: 20px; }
  .pad { padding: 4px 14px; font-size: 12px; }
  .err { color: var(--bad); }
  .file { width: 100%; display: flex; align-items: center; gap: 5px; padding: 3px 10px; border: 0; background: none; text-align: left; }
  .file:hover { background: #ffffff09; }
  .fname { font-weight: 600; white-space: nowrap; }
  .fdir { font-size: 11.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; direction: rtl; text-align: left; }
  .n { font-size: 10.5px; padding: 0 6px; border-radius: 8px; background: #2a303c; color: var(--dim); }
  .match { width: 100%; display: flex; gap: 8px; padding: 2px 10px 2px 30px; border: 0; background: none; text-align: left; font: 12.5px var(--mono); white-space: nowrap; overflow: hidden; }
  .match:hover { background: #ffffff0b; }
  .ln { color: var(--faint); min-width: 28px; text-align: right; flex: none; }
  .txt { overflow: hidden; text-overflow: ellipsis; color: #b8bfcc; }
  mark { background: #e8b04a55; color: #fff; border-radius: 2px; outline: 1px solid #e8b04a88; }
  .skipped { color: var(--warn); margin-top: 3px; }
</style>
