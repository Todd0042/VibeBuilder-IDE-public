<script lang="ts">
  import { onMount, tick } from "svelte";
  import Icon from "./Icon.svelte";
  import type { SearchResult } from "@core/index";
  import { session } from "@state/session.svelte";
  import { ui } from "@state/ui.svelte";
  import { editors } from "@state/editors.svelte";
  import { searchRoot } from "@state/searchRoot";
  import { fileColor } from "@state/fileIcons";

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

  onMount(() => searchRoot.listen((dir) => { root = dir; void tick().then(() => input?.focus()); }));
  $effect(() => { void ui.project; root = ""; result = null; });

  function changed() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(run, 350);
  }

  async function run() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (!query.trim() || (!scope && !ui.workspaceOpen)) { result = null; error = ""; return; }
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
    void run();
  }

  function rel(path: string) {
    return path.startsWith(ui.project + "/") ? path.slice(ui.project.length + 1) : path;
  }

  function pieces(text: string, ranges: [number, number][]) {
    const out: { s: string; hit: boolean }[] = [];
    let start = 0;
    const first = ranges[0]?.[0] ?? 0;
    if (first > 50) start = first - 30;
    let pos = start;
    for (const [a, b] of ranges) {
      if (b <= pos) continue;
      if (a > pos) out.push({ s: text.slice(pos, a), hit: false });
      out.push({ s: text.slice(Math.max(a, pos), b), hit: true });
      pos = b;
    }
    out.push({ s: text.slice(pos, pos + 240), hit: false });
    if (start > 0) out.unshift({ s: "…", hit: false });
    return out;
  }
</script>

<div class="search">
  <div class="form">
    <div class="qbox">
      <input bind:this={input} class="field" placeholder="Search in {scope || 'project'}" bind:value={query} oninput={changed} onkeydown={(e) => e.key === "Enter" && run()} spellcheck="false" />
      <div class="flags">
        <button class="btn small" class:primary={caseSensitive} onclick={() => toggle("case")}>Aa</button>
        <button class="btn small" class:primary={wholeWord} onclick={() => toggle("word")}>ab</button>
        <button class="btn small" class:primary={regex} onclick={() => toggle("regex")}>.*</button>
        <button class="btn small" onclick={() => (showFilters = !showFilters)}>Filters</button>
        {#if root}<button class="btn small" onclick={() => { root = ""; void run(); }}>All</button>{/if}
      </div>
    </div>
    {#if showFilters}
      <input class="field" placeholder="files to include (e.g. *.ts, src/**)" bind:value={include} oninput={changed} />
      <input class="field" placeholder="files to exclude (e.g. *.min.js)" bind:value={exclude} oninput={changed} />
    {/if}
  </div>

  <div class="results">
    {#if busy}<div class="faint pad">Searching…</div>{/if}
    {#if error}<div class="err pad">{error}</div>{/if}
    {#if result && !busy}
      <div class="summary pad faint">{result.match_count} matches in {result.files.length} files{result.truncated ? " (truncated)" : ""}</div>
      {#each result.files as f (f.path)}
        <button class="file" onclick={() => (collapsed[f.path] = !collapsed[f.path])}>
          <Icon name={collapsed[f.path] ? "chevronRight" : "chevronDown"} size={14} />
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
</div>

<style>
  .search { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .form { padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; border-bottom: 1px solid var(--line); }
  .qbox { display: flex; flex-direction: column; gap: 6px; }
  .flags { display: flex; gap: 6px; flex-wrap: wrap; }
  .results { flex: 1; overflow: auto; padding-bottom: 24px; }
  .pad { padding: 10px 14px; font-size: 13px; }
  .err { color: var(--bad); }
  .file { width: 100%; min-height: 38px; display: flex; align-items: center; gap: 6px; padding: 6px 12px; border: 0; background: #ffffff04; text-align: left; }
  .fname { font-weight: 600; white-space: nowrap; }
  .fdir { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; direction: rtl; text-align: left; }
  .n { font-size: 11px; padding: 1px 7px; border-radius: 10px; background: #2a303c; color: var(--dim); }
  .match { width: 100%; min-height: 34px; display: flex; gap: 8px; padding: 5px 12px 5px 28px; border: 0; background: none; text-align: left; font: 12.5px var(--mono); white-space: nowrap; overflow: hidden; }
  .match:active { background: #ffffff0c; }
  .ln { color: var(--faint); min-width: 28px; text-align: right; flex: none; }
  .txt { overflow: hidden; text-overflow: ellipsis; color: #b8bfcc; }
  mark { background: #e8b04a55; color: #fff; border-radius: 2px; }
</style>
