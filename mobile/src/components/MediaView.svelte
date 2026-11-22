<script lang="ts">
  import { editors, type FileTab } from "@state/editors.svelte";
  import { session } from "@state/session.svelte";
  import { formatBytes } from "@state/media";
  import { downloadFile } from "@state/fileOps";
  import Icon from "./Icon.svelte";

  let { tab, active }: { tab: FileTab; active: boolean } = $props();
  let player: HTMLMediaElement | undefined = $state();

  $effect(() => { if (!active) player?.pause(); });
  let src = $state("");
  let size = $state(0);
  let error = $state("");
  let fit = $state(true);
  let dims = $state("");
  let duration = $state("");

  $effect(() => {
    const path = tab.path;
    void tab.mediaRev;
    let stale = false;
    error = ""; dims = ""; duration = "";
    session.api.mediaUrl(path).then((r) => {
      if (stale) return;
      src = r.url;
      size = r.size;
    }, (e) => {
      if (!stale) error = `Couldn't open ${tab.title}: ${e instanceof Error ? e.message : String(e)}`;
    });
    return () => { stale = true; };
  });

  function failed(e: Event) {
    const el = e.currentTarget as HTMLMediaElement | HTMLImageElement;
    const code = "error" in el && el.error ? ` (media error ${el.error.code}${el.error.message ? `: ${el.error.message}` : ""})` : "";
    error = tab.media === "image"
      ? `This image couldn't be shown${code}. The file may be damaged or unsupported.`
      : `This file couldn't be played${code}. The format or codec may not be supported by Android WebView.`;
  }

  function clock(sec: number) {
    if (!isFinite(sec)) return "";
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
    return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) + `:${String(s).padStart(2, "0")}`;
  }

  async function asText() {
    const path = tab.path;
    if (await editors.close(tab.id)) await editors.open(path, undefined, true);
  }
</script>

<div class="bar">
  <span class="faint">{tab.media}</span>
  {#if size}<span>{formatBytes(size)}</span>{/if}
  {#if dims}<span>{dims}</span>{/if}
  {#if duration}<span>{duration}</span>{/if}
  <span class="grow"></span>
  {#if tab.media === "image"}
    <button class="btn small" onclick={() => (fit = !fit)}>{fit ? "1:1" : "Fit"}</button>
  {/if}
  {#if tab.path.toLowerCase().endsWith(".svg")}
    <button class="btn small" onclick={asText}>Source</button>
  {/if}
  <button class="icon-btn" title="Download" onclick={() => downloadFile(tab.path)}><Icon name="download" size={16} /></button>
  <button class="icon-btn" onclick={() => tab.mediaRev++}><Icon name="refresh" size={16} /></button>
</div>

<div class="stage" class:checker={tab.media === "image"} class:scroll={!fit}>
  {#if error}
    <div class="err"><Icon name="warning" size={16} /><span>{error}</span></div>
  {:else if !src}
    <div class="faint">Opening…</div>
  {:else if tab.media === "image"}
    <img {src} alt={tab.title} class:fit onerror={failed}
      onload={(e) => { const i = e.currentTarget as HTMLImageElement; dims = `${i.naturalWidth}×${i.naturalHeight}`; }} />
  {:else if tab.media === "video"}
    <!-- svelte-ignore a11y_media_has_caption -->
    <video bind:this={player} {src} controls preload="metadata" onerror={failed}
      onloadedmetadata={(e) => { const v = e.currentTarget as HTMLVideoElement; dims = v.videoWidth ? `${v.videoWidth}×${v.videoHeight}` : ""; duration = clock(v.duration); }}></video>
  {:else}
    <div class="audio">
      <Icon name="file" size={42} />
      <div class="name">{tab.title}</div>
      <audio bind:this={player} {src} controls preload="metadata" onerror={failed}
        onloadedmetadata={(e) => (duration = clock((e.currentTarget as HTMLAudioElement).duration))}></audio>
    </div>
  {/if}
</div>

<style>
  .bar { display: flex; align-items: center; gap: 10px; padding: 4px 10px; font-size: 12px; border-bottom: 1px solid var(--line); flex: none; color: var(--dim); }
  .grow { flex: 1; }
  .stage { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; overflow: hidden; padding: 12px; }
  .stage.scroll { overflow: auto; align-items: flex-start; justify-content: flex-start; }
  .checker { background: repeating-conic-gradient(#1c1f26 0 25%, #23272f 0 50%) 0 0 / 20px 20px; }
  img.fit { max-width: 100%; max-height: 100%; object-fit: contain; }
  img:not(.fit) { flex: none; }
  video { max-width: 100%; max-height: 100%; background: #000; border-radius: 6px; }
  .audio { display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--dim); width: 100%; }
  .audio .name { color: var(--text); font-weight: 600; }
  audio { width: min(380px, 90vw); }
  .err { display: flex; gap: 10px; align-items: flex-start; padding: 14px; border-radius: 10px; background: #3a1d22; color: #ffd1d5; }
</style>
