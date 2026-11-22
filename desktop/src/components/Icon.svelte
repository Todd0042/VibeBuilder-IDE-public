<script lang="ts">
  // A small fixed icon set (stroke icons, 24-unit grid) so the app needs no icon library.
  let { name, size = 16, class: cls = "" }: { name: string; size?: number; class?: string } = $props();
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
    chevronRight: "M9 6l6 6-6 6",
    chevronDown: "M6 9l6 6 6-6",
    close: "M6 6l12 12M18 6L6 18",
    plus: "M12 5v14M5 12h14",
    refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
    terminal: "M4 5h16v14H4zM7 9l3 3-3 3M12 15h5",
    maximize: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
    minimize: "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5",
    collapse: "M7 13l5-5 5 5",
    expand: "M7 11l5 5 5-5",
    undo: "M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
    newFile: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M12 12v6M9 15h6",
    newFolder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM12 10v6M9 13h6",
    collapseAll: "M4 6h16M4 12h10M4 18h6",
    regex: "M17 3v8M13.5 5l7 4M13.5 9l7-4M5 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
    word: "M3 7l2 10 3-7 3 7 2-10M15 17V7h3a2.5 2.5 0 0 1 0 5h-3 3.5a2.5 2.5 0 0 1 0 5z",
    caseSensitive: "M3 17l4-10 4 10M4.5 13h5M14 12.5a2.5 2.5 0 1 1 5 0V17M19 14.5a2.5 2.5 0 1 1-2.5-2.5",
    clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
    dot: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
    trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
    rename: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
    open: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
    branch: "M6 3v12M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9c0 6-12 3-12 9",
    sidebar: "M4 5h16v14H4zM9 5v14",
    panel: "M4 5h16v14H4zM4 14h16",
    check: "M5 12l5 5L20 7",
    eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    eyeOff: "M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2",
    warning: "M12 4l9 16H3zM12 10v4M12 17v.5",
  };
</script>

<svg class={cls} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d={P[name] ?? P.dot} />
</svg>
