// A colour per file type for the tree and tabs.
const BY_EXT: Record<string, string> = {
  py: "#5a9fd4", js: "#e8d44d", mjs: "#e8d44d", cjs: "#e8d44d", ts: "#4f8fd8", tsx: "#4f8fd8", jsx: "#61dafb",
  svelte: "#ff5d35", vue: "#41b883", rs: "#e0905a", go: "#29beb0", c: "#7f9cd0", h: "#a08fd0", cpp: "#5f8fd8",
  cc: "#5f8fd8", hpp: "#a08fd0", cs: "#9b6fd8", java: "#e76f51", kt: "#a97bff", kts: "#a97bff", gradle: "#6fbf8f",
  json: "#e8c46a", toml: "#c9a95a", yaml: "#d08f8f", yml: "#d08f8f", md: "#8fb4d8", txt: "#9aa3b2", html: "#e8734a",
  css: "#4f9fd8", scss: "#d86fa0", sh: "#8fd18a", fish: "#8fd18a", bash: "#8fd18a", nix: "#7ebae4", lua: "#5f7fd8",
  zig: "#f0a63a", qml: "#41cd52", sql: "#e0b05a", xml: "#e8734a", svg: "#f0a63a", png: "#b48ead", jpg: "#b48ead",
  lock: "#6b7385", env: "#e8c46a", cmake: "#6fbf8f", dockerfile: "#3a9ad9",
};
const BY_NAME: Record<string, string> = {
  Dockerfile: "#3a9ad9", Containerfile: "#3a9ad9", Makefile: "#8fd18a", "CMakeLists.txt": "#6fbf8f",
  ".gitignore": "#e0705a", "package.json": "#8fd18a", "Cargo.toml": "#e0905a", "pyproject.toml": "#5a9fd4",
};

export function fileColor(name: string): string {
  if (BY_NAME[name]) return BY_NAME[name];
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".") + 1).toLowerCase() : "";
  return BY_EXT[ext] ?? "#8a93a3";
}
