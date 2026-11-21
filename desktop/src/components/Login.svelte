<script lang="ts">
  import logo from "../assets/logo.png";
  import { onMount, tick } from "svelte";
  import { session } from "../lib/session.svelte";
  import { deviceName } from "../lib/native";

  let { overlay = false }: { overlay?: boolean } = $props();

  let code = $state("");
  let pairCode = $state("");
  let name = $state("");
  let busy = $state(false);
  let error = $state("");
  let editingServer = $state(!session.server);
  let serverDraft = $state(session.server);
  let codeInput: HTMLInputElement | undefined = $state();
  let pairInput: HTMLInputElement | undefined = $state();

  onMount(async () => {
    name = await deviceName();
  });

  $effect(() => {
    if (session.phase === "code") void tick().then(() => codeInput?.focus());
    if (session.phase === "pair") void tick().then(() => pairInput?.focus());
  });

  function onCode(e: Event) {
    code = (e.target as HTMLInputElement).value.replace(/\D/g, "").slice(0, 6);
    error = "";
    if (code.length === 6) void signIn();
  }

  function onPairCode(e: Event) {
    const raw = (e.target as HTMLInputElement).value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
    pairCode = raw.length > 3 ? `${raw.slice(0, 3)}-${raw.slice(3)}` : raw;
    error = "";
  }

  async function signIn() {
    if (busy || code.length !== 6) return;
    busy = true;
    try {
      await session.login(code);
      code = "";
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      code = "";
      await tick();
      codeInput?.focus();
    } finally {
      busy = false;
    }
  }

  async function pair() {
    if (busy || pairCode.replace("-", "").length !== 6) return;
    busy = true;
    try {
      await session.pair(pairCode, name || "Laptop");
      pairCode = "";
      error = "";
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  async function saveServer() {
    if (!serverDraft.trim()) return;
    await session.setServer(serverDraft);
    serverDraft = session.server;
    editingServer = false;
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
            <button class="btn small" disabled={!serverDraft.trim()} onclick={saveServer}>Use</button>
          {:else}
            <span class="muted">{host}</span>
            {#if session.phase === "pair"}<button class="link" onclick={() => (editingServer = true)}>change</button>{/if}
          {/if}
        </div>
      </div>
    </div>

    {#if session.phase === "starting"}
      <p class="muted">Starting…</p>
    {:else if session.phase === "pair"}
      <h2>Pair this device</h2>
      {#if !session.server}<p class="muted">First, enter your IDE server's address above (the <code>VB_PUBLIC_URL</code> from its <code>vibebuilder.env</code>).</p>{/if}
      <p class="muted">On your desktop run <code>vibebuilder pair</code> and type the code it shows. Codes change every 30 seconds and work once.</p>
      <label>Pairing code
        <input bind:this={pairInput} class="field code pair" value={pairCode} oninput={onPairCode} placeholder="ABC-123"
          autocomplete="off" spellcheck="false" onkeydown={(e) => e.key === "Enter" && pair()} />
      </label>
      <label>Device name
        <input class="field" bind:value={name} maxlength="60" />
      </label>
      <button class="btn primary wide" disabled={busy || !session.server || pairCode.replace("-", "").length !== 6} onclick={pair}>
        {busy ? "Pairing…" : "Pair"}
      </button>
    {:else}
      <h2>{overlay ? "Locked" : "Sign in"}</h2>
      {#if session.lockReason}<p class="reason">{session.lockReason}</p>{/if}
      <p class="muted">Enter the 6-digit code from your authenticator app.</p>
      <input bind:this={codeInput} class="field code" value={code} oninput={onCode} inputmode="numeric" placeholder="••••••"
        autocomplete="one-time-code" disabled={busy} />
      <div class="foot">
        <button class="link" onclick={() => session.forgetDevice()}>Pair again</button>
        {#if overlay}<span class="faint">Your open files are kept while locked.</span>{/if}
      </div>
    {/if}

    {#if error}<p class="error">{error}</p>{/if}
  </div>
</div>

<style>
  .login { position: fixed; inset: 0; display: grid; place-items: center; background: radial-gradient(1200px 600px at 30% 20%, #1b2130, var(--bg)); z-index: 50; }
  .login.overlay { background: #0b0d11d9; backdrop-filter: blur(6px); }
  .card { width: 380px; padding: 28px; border-radius: 14px; background: var(--panel); border: 1px solid var(--line); box-shadow: 0 20px 60px #0008; display: flex; flex-direction: column; gap: 12px; }
  .brand { display: flex; gap: 12px; align-items: center; margin-bottom: 6px; }
  .logo { width: 42px; height: 42px; border-radius: 10px; flex: none; }
  h1 { font-size: 17px; margin: 0; }
  h2 { font-size: 15px; margin: 6px 0 0; }
  p { margin: 0; }
  .server { display: flex; gap: 6px; align-items: center; font-size: 12px; }
  .server :global(.field.small) { height: 24px; font-size: 12px; }
  label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--dim); }
  .code { height: 48px; font: 600 26px var(--mono); letter-spacing: .45em; text-align: center; padding-left: .45em; }
  .code.pair { letter-spacing: .25em; }
  .wide { width: 100%; justify-content: center; height: 34px; }
  .link { background: none; border: 0; padding: 0; color: var(--accent); font-size: 12px; }
  .link:hover { text-decoration: underline; }
  .foot { display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
  .reason { color: var(--warn); font-size: 12.5px; }
  .error { color: var(--bad); font-size: 12.5px; }
  code { font-family: var(--mono); font-size: 12px; background: #0e1015; padding: 1px 5px; border-radius: 4px; color: var(--text); }
</style>
