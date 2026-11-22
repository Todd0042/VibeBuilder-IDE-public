<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import Icon from "./Icon.svelte";
  import { session } from "@state/session.svelte";
  import { terminals } from "@state/terminals.svelte";
  import { PreviewSocket, type TerminalInfo } from "@core/index";

  interface Props {
    terminal: TerminalInfo;
  }

  const { terminal }: Props = $props();

  let socket: PreviewSocket | null = null;
  let frameUrl = $state<string | null>(null);
  let status = $state<"connecting" | "live" | "closed">("connecting");
  let exitCode = $state<number | null>(null);
  let inputText = $state("");
  let imgEl = $state<HTMLImageElement | null>(null);
  let ripple = $state<{ x: number; y: number } | null>(null);
  let rippleTimer: any = null;

  function updateFrame(blob: Blob) {
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    frameUrl = URL.createObjectURL(blob);
    status = "live";
  }

  function handlePointer(e: MouseEvent | TouchEvent) {
    if (!imgEl || !socket) return;
    const rect = imgEl.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    let clientX = 0;
    let clientY = 0;
    if ("touches" in e) {
      if (!e.touches.length) return;
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }

    const relX = clientX - rect.left;
    const relY = clientY - rect.top;
    if (relX < 0 || relX > rect.width || relY < 0 || relY > rect.height) return;

    const normX = relX / rect.width;
    const normY = relY / rect.height;

    socket.click(normX, normY, 1);

    ripple = { x: relX, y: relY };
    clearTimeout(rippleTimer);
    rippleTimer = setTimeout(() => { ripple = null; }, 350);
  }

  function sendText() {
    if (!inputText || !socket) return;
    socket.type(inputText);
    inputText = "";
  }

  function sendKey(key: string) {
    if (!socket) return;
    socket.key(key);
  }

  function refresh() {
    socket?.refresh();
  }

  onMount(() => {
    socket = new PreviewSocket(session.api, terminal.id, {
      onFrame: (blob) => updateFrame(blob),
      onReady: () => { status = "live"; },
      onExit: (code) => { status = "closed"; exitCode = code; },
      onState: (st) => {
        if (st === "closed") status = "closed";
        else if (st === "connecting" && status !== "live") status = "connecting";
      },
    });
    socket.start();
  });

  onDestroy(() => {
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    clearTimeout(rippleTimer);
    socket?.stop();
  });
</script>

<div class="preview-wrap">
  <div class="preview-toolbar">
    <div class="status-indicator">
      <span class="status-dot" class:live={status === "live"} class:closed={status === "closed"}></span>
      <span class="status-text">
        {#if status === "live"}Live Screen{:else if status === "closed"}Exited ({exitCode ?? 0}){:else}Connecting…{/if}
      </span>
    </div>
    <div class="grow"></div>
    <button class="tool-btn" title="Refresh frame" onclick={refresh}>
      <Icon name="refresh" size={14} />
      <span>Refresh</span>
    </button>
    <button class="tool-btn stop" title="Stop App" onclick={() => terminals.close(terminal.id)}>
      <Icon name="close" size={13} />
      <span>Stop App</span>
    </button>
  </div>

  <div class="viewport">
    {#if frameUrl}
      <div class="screen-box" onclick={handlePointer} role="presentation">
        <img bind:this={imgEl} src={frameUrl} alt="App Window Screen" class="screen-img" />
        {#if ripple}
          <span class="ripple" style="left: {ripple.x}px; top: {ripple.y}px;"></span>
        {/if}
      </div>
    {:else}
      <div class="placeholder">
        <div class="spinner"></div>
        <p class="muted">Starting display server and waiting for app window…</p>
        <p class="hint">App: {terminal.title}</p>
      </div>
    {/if}
  </div>

  <div class="key-bar">
    <button class="k" onclick={() => sendKey("Return")}>Enter</button>
    <button class="k" onclick={() => sendKey("Escape")}>Esc</button>
    <button class="k" onclick={() => sendKey("Tab")}>Tab</button>
    <button class="k" onclick={() => sendKey("space")}>Space</button>
    <button class="k" onclick={() => sendKey("BackSpace")}>⌫</button>
    <button class="k" onclick={() => sendKey("Up")}>↑</button>
    <button class="k" onclick={() => sendKey("Down")}>↓</button>
    <button class="k" onclick={() => sendKey("Left")}>←</button>
    <button class="k" onclick={() => sendKey("Right")}>→</button>
  </div>

  <form class="input-form" onsubmit={(e) => { e.preventDefault(); sendText(); }}>
    <input
      type="text"
      bind:value={inputText}
      placeholder="Type text into app…"
      class="text-input"
    />
    <button type="submit" class="send-btn" disabled={!inputText.trim()}>Send</button>
  </form>
</div>

<style>
  .preview-wrap {
    flex: 1; min-height: 0; display: flex; flex-direction: column;
    background: #090a0d; color: var(--text); position: relative;
  }
  .preview-toolbar {
    height: 38px; flex: none; display: flex; align-items: center; gap: 8px; padding: 0 10px;
    background: #14171f; border-bottom: 1px solid var(--line);
  }
  .status-indicator {
    display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
  }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #d29922; }
  .status-dot.live { background: #3fb950; box-shadow: 0 0 6px rgba(63, 185, 80, 0.4); }
  .status-dot.closed { background: #f85149; }
  .status-text { color: var(--dim); }
  .grow { flex: 1; }
  .tool-btn {
    display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 8px; border-radius: 6px;
    border: 1px solid var(--line-2); background: #1c212c; color: var(--text); font-size: 12px; font-weight: 500;
  }
  .tool-btn.stop {
    border-color: #6e2a2a; background: #321616; color: #ff9e9e;
  }
  .viewport {
    flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center;
    position: relative; overflow: auto; padding: 6px; background: #050608;
  }
  .screen-box {
    position: relative; display: inline-block; cursor: crosshair; user-select: none;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6); border-radius: 4px; overflow: hidden;
  }
  .screen-img {
    display: block; max-width: 100%; max-height: calc(100vh - 210px);
    object-fit: contain; background: #000;
  }
  .ripple {
    position: absolute; width: 22px; height: 22px; margin-left: -11px; margin-top: -11px;
    border-radius: 50%; background: rgba(88, 166, 255, 0.4); border: 2px solid #58a6ff;
    pointer-events: none; animation: pop 0.35s ease-out forwards;
  }
  @keyframes pop {
    0% { transform: scale(0.3); opacity: 1; }
    100% { transform: scale(1.6); opacity: 0; }
  }
  .placeholder {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 10px; text-align: center; padding: 20px;
  }
  .spinner {
    width: 28px; height: 28px; border: 3px solid rgba(255,255,255,0.1);
    border-top-color: var(--accent); border-radius: 50%; animation: spin 1s infinite linear;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .muted { color: var(--dim); font-size: 13px; }
  .hint { color: var(--dim-2); font-size: 11.5px; font-family: var(--mono); }
  .key-bar {
    flex: none; display: flex; align-items: center; gap: 4px; padding: 4px 6px;
    background: #0f1116; border-top: 1px solid var(--line); overflow-x: auto; scrollbar-width: none;
  }
  .k {
    flex: none; min-width: 44px; height: 32px; padding: 0 8px; border-radius: 6px;
    border: 1px solid var(--line-2); background: #1a1e28; color: var(--text); font: 600 12px var(--mono);
  }
  .k:active { background: #2f4168; }
  .input-form {
    flex: none; display: flex; align-items: center; gap: 6px; padding: 6px 8px;
    background: #14171f; border-top: 1px solid var(--line);
  }
  .text-input {
    flex: 1; height: 34px; padding: 0 10px; border-radius: 6px; border: 1px solid var(--line-2);
    background: #090a0d; color: var(--text); font-size: 13px; outline: none;
  }
  .text-input:focus { border-color: var(--accent); }
  .send-btn {
    height: 34px; padding: 0 14px; border-radius: 6px; border: 0;
    background: var(--accent); color: #fff; font-size: 13px; font-weight: 600;
  }
  .send-btn:disabled { opacity: 0.4; }
</style>