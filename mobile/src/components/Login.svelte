<script lang="ts">
  import logo from "../assets/logo.png";
  import Icon from "./Icon.svelte";
  import { onMount, tick } from "svelte";
  import { session } from "@state/session.svelte";
  import { canQrScan, deviceName, scanPairingQr } from "@platform";

  let { overlay = false }: { overlay?: boolean } = $props();

  let code = $state("");
  let pairCode = $state("");
  let name = $state("");
  let busy = $state(false);
  let error = $state("");
  let editingServer = $state(!session.server);
  let serverDraft = $state(session.server);
  let codeInput: HTMLInputElement | undefined = $state();

  onMount(async () => {
    name = await deviceName();
  });

  $effect(() => {
    if (session.phase === "code") void tick().then(() => codeInput?.focus());
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
      await session.pair(pairCode, name || "Android Phone");
      pairCode = "";
      error = "";
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  async function scanQr() {
    if (busy) return;
    error = "";
    try {
      const scanned = await scanPairingQr();
      if (!scanned) return;
      serverDraft = scanned.server;
      await session.setServer(scanned.server);
      editingServer = false;
      pairCode = scanned.code;
      await pair();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
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
      <div class="grow">
        <h1>VibeBuilder IDE</h1>
        <div class="server">
          {#if editingServer}
            <input class="field small" bind:value={serverDraft} placeholder="https://ide.example.com"
              autocapitalize="off" autocomplete="url" onkeydown={(e) => e.key === "Enter" && saveServer()} />
            <button class="btn small" disabled={!serverDraft.trim()} onclick={saveServer}>Use</button>
          {:else}
            <span class="muted">{host || "No server set"}</span>
            {#if session.phase === "pair"}<button class="link" onclick={() => (editingServer = true)}>change</button>{/if}
          {/if}
        </div>
      </div>
    </div>

    {#if session.phase === "starting"}
      <p class="muted">Starting…</p>
    {:else if session.phase === "pair"}
      <h2>Pair this phone</h2>
      <p class="muted">On your desktop run <code>vibebuilder pair</code> and scan the QR code or type the 6-character code.</p>

      {#if canQrScan}
        <button class="btn primary wide qr-btn" disabled={busy} onclick={scanQr}>
          <Icon name="qr" size={20} /> Scan Pairing QR
        </button>
      {/if}

      <label>Pairing code
        <input class="field code pair" value={pairCode} oninput={onPairCode} placeholder="ABC-123"
          autocomplete="off" autocapitalize="characters" spellcheck="false" onkeydown={(e) => e.key === "Enter" && pair()} />
      </label>
      <label>Device name
        <input class="field" bind:value={name} maxlength="60" />
      </label>
      <button class="btn wide" class:primary={!canQrScan} disabled={busy || !session.server || pairCode.replace("-", "").length !== 6} onclick={pair}>
        {busy ? "Pairing…" : "Pair with code"}
      </button>
    {:else}
      <h2>{overlay ? "Locked" : "Sign in"}</h2>
      {#if session.lockReason}<p class="reason">{session.lockReason}</p>{/if}
      <p class="muted">Enter the 6-digit code from your authenticator app.</p>
      <input bind:this={codeInput} class="field code" value={code} oninput={onCode} inputmode="numeric" placeholder="••••••"
        autocomplete="one-time-code" disabled={busy} />
      <div class="foot">
        <button class="link" onclick={() => session.forgetDevice()}>Pair again</button>
        {#if overlay}<span class="faint">Open tabs are kept while locked.</span>{/if}
      </div>
    {/if}

    {#if error}<p class="error">{error}</p>{/if}
  </div>
</div>

<style>
  .login {
    position: fixed; inset: 0; display: grid; place-items: center; padding: 16px;
    background: radial-gradient(900px 500px at 30% 15%, #1b2130, var(--bg)); z-index: 100; overflow: auto;
  }
  .login.overlay { background: #0b0d11e6; backdrop-filter: blur(6px); }
  .card {
    width: min(400px, 100%); padding: 22px; border-radius: 16px;
    background: var(--panel); border: 1px solid var(--line); box-shadow: 0 20px 60px #0008;
    display: flex; flex-direction: column; gap: 12px;
  }
  .brand { display: flex; gap: 12px; align-items: center; margin-bottom: 2px; }
  .grow { flex: 1; min-width: 0; }
  .logo { width: 44px; height: 44px; border-radius: 11px; flex: none; }
  h1 { font-size: 18px; margin: 0; }
  h2 { font-size: 16px; margin: 4px 0 0; }
  p { margin: 0; }
  .server { display: flex; gap: 6px; align-items: center; font-size: 12.5px; margin-top: 2px; flex-wrap: wrap; }
  .server .field.small { min-height: 32px; font-size: 13px; flex: 1; min-width: 140px; }
  label { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; color: var(--dim); }
  .code { height: 52px; font: 600 26px var(--mono); letter-spacing: .4em; text-align: center; padding-left: .4em; }
  .code.pair { letter-spacing: .22em; }
  .wide { width: 100%; min-height: 44px; }
  .qr-btn { font-size: 15px; }
  .link { background: none; border: 0; padding: 4px 0; color: var(--accent); font-size: 13px; }
  .foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12.5px; }
  .reason { color: var(--warn); font-size: 13px; }
  .error { color: var(--bad); font-size: 13px; }
  code { font-family: var(--mono); font-size: 12px; background: #0e1015; padding: 1px 5px; border-radius: 4px; color: var(--text); }
</style>
