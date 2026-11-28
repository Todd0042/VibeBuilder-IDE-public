<script lang="ts">
  import logo from "../assets/logo.png";
  import { session } from "../lib/session.svelte";

  let { overlay = false }: { overlay?: boolean } = $props();

  let busy = $state(false);
  let editingServer = $state(!session.server);
  let serverDraft = $state(session.server);

  async function saveServer() {
    if (!serverDraft.trim() || busy) return;
    busy = true;
    try {
      await session.setServer(serverDraft);
      serverDraft = session.server;
      editingServer = false;
    } finally {
      busy = false;
    }
  }

  async function retryCloudflare() {
    if (busy) return;
    busy = true;
    try {
      if (session.server && typeof window !== "undefined" && window.location.origin !== session.server) {
        window.location.href = session.server;
        return;
      }
      await session.reconnect();
    } finally {
      busy = false;
    }
  }

  const host = $derived(session.server.replace(/^https?:\/\//, ""));
</script>

<div class="login" class:overlay>
  <div class="card">
    <div class="brand">
      <img class="logo" src={logo} alt="VibeBuilder" />
      <div>
        <h1>VibeBuilder IDE</h1>
        <div class="server">
          {#if editingServer}
            <input class="field small" bind:value={serverDraft} placeholder="https://ide.example.com" onkeydown={(e) => e.key === "Enter" && saveServer()} />
            <button class="btn small" disabled={!serverDraft.trim() || busy} onclick={saveServer}>Use</button>
          {:else}
            <span class="muted">{host}</span>
            <button class="link" onclick={() => (editingServer = true)}>change</button>
          {/if}
        </div>
      </div>
    </div>

    {#if session.phase === "starting"}
      <p class="muted">Connecting via Cloudflare Access…</p>
    {:else}
      <h2>{overlay ? "Disconnected" : "Sign in"}</h2>
      {#if session.lockReason}<p class="reason">{session.lockReason}</p>{/if}
      <p class="muted">Protected by Cloudflare Zero Trust Access. Sign in once and your session is remembered.</p>
      <button class="btn primary wide" disabled={busy || !session.server} onclick={retryCloudflare}>
        {busy ? "Connecting…" : "Sign in with Cloudflare"}
      </button>
      {#if overlay}
        <div class="foot">
          <span class="faint">Your open files are kept while disconnected.</span>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .login { position: fixed; inset: 0; display: grid; place-items: center; background: var(--bg); z-index: 60; padding: 16px; }
  .login.overlay { background: rgba(13, 17, 23, .82); backdrop-filter: blur(8px); }
  .card { width: min(390px, 100%); background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
          padding: 24px; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 24px 64px rgba(0,0,0,.5); }
  .brand { display: flex; align-items: center; gap: 12px; }
  .logo { width: 42px; height: 42px; border-radius: 9px; object-fit: cover; }
  h1 { margin: 0; font-size: 16px; font-weight: 600; }
  h2 { margin: 4px 0 0; font-size: 15px; font-weight: 600; }
  .server { display: flex; align-items: center; gap: 8px; margin-top: 2px; font-size: 12px; }
  .muted { margin: 0; color: var(--muted); font-size: 12.5px; line-height: 1.5; }
  .reason { margin: 0; padding: 8px 10px; border-radius: 6px; background: var(--warn-bg); color: var(--warn); font-size: 12px; }
  .foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  .faint { color: var(--faint); font-size: 11.5px; }
  .link { background: none; border: 0; padding: 0; color: var(--accent); cursor: pointer; font-size: 12px; }
  .link:hover { text-decoration: underline; }
</style>
