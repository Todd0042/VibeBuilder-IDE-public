<script lang="ts">
  import { onMount } from "svelte";
  import Login from "./components/Login.svelte";
  import Workbench from "./components/Workbench.svelte";
  import Dialog from "./components/Dialog.svelte";
  import Toasts from "./components/Toasts.svelte";
  import { session } from "./lib/session.svelte";
  import { editors } from "./lib/editors.svelte";
  import { onWindowClose } from "./lib/native";

  let everReady = $state(false);

  onMount(() => {
    void session.init();
    // The lock button and closing the app save unsaved files first, then sign out.
    session.beforeLock(() => editors.saveAll());
    void onWindowClose(() => session.lock());
  });

  $effect(() => {
    if (session.phase === "ready") everReady = true;
  });
</script>

<!-- The workbench stays mounted under the lock screen, so open tabs and unsaved edits survive a lock. -->
{#if everReady}
  <Workbench />
{/if}
{#if session.phase !== "ready"}
  <Login overlay={everReady} />
{/if}
<Dialog />
<Toasts />
