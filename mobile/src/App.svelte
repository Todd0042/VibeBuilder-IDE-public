<script lang="ts">
  import { onMount } from "svelte";
  import Login from "./components/Login.svelte";
  import MobileWorkbench from "./components/MobileWorkbench.svelte";
  import Dialog from "./components/Dialog.svelte";
  import Toasts from "./components/Toasts.svelte";
  import { session } from "@state/session.svelte";
  import { editors } from "@state/editors.svelte";
  import { terminals } from "@state/terminals.svelte";
  import { ui } from "@state/ui.svelte";

  let everReady = $state(false);

  onMount(() => {
    void session.init();
    session.beforeLock(() => editors.saveAll());

    const onVis = () => {
      if (document.visibilityState === "hidden") {
        // Flush dirty files promptly when Android sends the app to background.
        if (session.phase === "ready" && editors.dirtyTabs.length) void editors.saveAll();
      } else {
        void session.resumeFromBackground();
      }
    };
    document.addEventListener("visibilitychange", onVis);

    // Keep app height, xterm.js, and toasts fitted cleanly above the Android soft keyboard.
    let baseH = window.innerHeight;
    const onOrient = () => { baseH = window.innerHeight; };
    const syncViewport = () => {
      const winH = window.innerHeight;
      const vvH = window.visualViewport?.height ?? winH;
      if (winH > baseH) baseH = winH;
      const kb = Math.max(0, Math.round(baseH - Math.min(winH, vvH)));
      // Only clamp --app-height if visualViewport shrank inside a non-resized window.
      document.documentElement.style.setProperty("--app-height", vvH < winH - 2 ? `${Math.round(vvH)}px` : "100%");
      ui.keyboardOpen = kb > 120 || Math.min(winH, vvH) < 500;
      if (ui.mobileView === "terminal" && terminals.activeId) {
        requestAnimationFrame(() => terminals.fit(terminals.activeId!));
      }
    };
    const vv = window.visualViewport;
    vv?.addEventListener("resize", syncViewport);
    window.addEventListener("resize", syncViewport);
    window.addEventListener("orientationchange", onOrient);
    syncViewport();

    return () => {
      document.removeEventListener("visibilitychange", onVis);
      vv?.removeEventListener("resize", syncViewport);
      window.removeEventListener("resize", syncViewport);
      window.removeEventListener("orientationchange", onOrient);
    };
  });

  $effect(() => {
    if (session.phase === "ready") everReady = true;
  });
</script>

{#if everReady}
  <MobileWorkbench />
{/if}
{#if session.phase !== "ready"}
  <Login overlay={everReady} />
{/if}
<Dialog />
<Toasts />
