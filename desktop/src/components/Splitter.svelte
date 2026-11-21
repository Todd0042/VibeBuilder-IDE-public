<script lang="ts">
  // Drag to resize the side bar (dir x) or the terminal panel (dir y, inverted: dragging up grows it).
  let { dir, value, min, max, invert = false, onchange }:
    { dir: "x" | "y"; value: number; min: number; max: number; invert?: boolean; onchange: (v: number) => void } = $props();

  function down(e: PointerEvent) {
    const start = dir === "x" ? e.clientX : e.clientY, from = value;
    const el = e.currentTarget as HTMLElement;
    el.setPointerCapture(e.pointerId);
    document.body.style.cursor = dir === "x" ? "col-resize" : "row-resize";
    const move = (ev: PointerEvent) => {
      const d = (dir === "x" ? ev.clientX : ev.clientY) - start;
      onchange(Math.round(Math.min(max, Math.max(min, from + (invert ? -d : d)))));
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      document.body.style.cursor = "";
      window.dispatchEvent(new Event("resize"));
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }
</script>

<div class="split {dir}" role="separator" aria-orientation={dir === "x" ? "vertical" : "horizontal"} onpointerdown={down}></div>

<style>
  .split { flex: none; position: relative; z-index: 5; }
  .split.x { width: 5px; margin: 0 -2px; cursor: col-resize; }
  .split.y { height: 5px; margin: -2px 0; cursor: row-resize; }
  .split:hover, .split:active { background: var(--accent-2); opacity: .7; }
</style>
