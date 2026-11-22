<script lang="ts">
  let { name, size = 18, class: cls = "" }: { name: string; size?: number; class?: string } = $props();
  const P: Record<string, string> = {
    files: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5",
    search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
    changes: "M6 3v12M18 9v12M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM18 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM6 15c0-5 12-1 12-6",
    devices: "M4 5h16v10H4zM2 19h20M10 15v4M14 15v4",
    lock: "M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3",
    save: "M5 3h11l3 3v15H5zM8 3v5h7V3M8 21v-7h8v7",
    saveall: "M7 7h10l3 3v11H7zM10 7v4h6V7M10 21v-6h7v6M4 17V4h10",
    folder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    folderOpen: "M3 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v1M3 7v10a2 2 0 0 0 2 2h12.5a2 2 0 0 0 1.9-1.4L22 11H7.5a2 2 0 0 0-1.9 1.4L3 19",
    file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5",
    code: "M8 9l-4 3 4 3M16 9l4 3-4 3M13 5l-2 14",
    chevronRight: "M9 6l6 6-6 6",
    chevronDown: "M6 9l6 6 6-6",
    close: "M6 6l12 12M18 6L6 18",
    plus: "M12 5v14M5 12h14",
    refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
    terminal: "M4 5h16v14H4zM7 9l3 3-3 3M12 15h5",
    undo: "M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
    redo: "M15 14l5-5-5-5M20 9H10a6 6 0 0 0 0 12h3",
    newFile: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M12 12v6M9 15h6",
    newFolder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM12 10v6M9 13h6",
    collapseAll: "M4 6h16M4 12h10M4 18h6",
    expand: "M7 11l5 5 5-5",
    clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
    dot: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
    open: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
    branch: "M6 3v12M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9c0 6-12 3-12 9",
    check: "M5 12l5 5L20 7",
    warning: "M12 4l9 16H3zM12 10v4M12 17v.5",
    more: "M12 6a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4zM12 13.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4zM12 20.4a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4z",
    menu: "M4 7h16M4 12h16M4 17h16",
    qr: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 14h2v2h-2zM16 16h2v2h-2zM14 18h2v2h-2zM18 18h2v2h-2z",
    back: "M15 6l-6 6 6 6",
    ports: "M8 12h8M4 8v8M20 8v8M12 4v4M12 16v4",
  };
</script>

<svg class={cls} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d={P[name] ?? P.dot} />
</svg>
