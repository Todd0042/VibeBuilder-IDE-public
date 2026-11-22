// Files the media viewer shows instead of the code editor.
export type MediaKind = "image" | "video" | "audio";

const KINDS: Record<string, MediaKind> = {
  png: "image", jpg: "image", jpeg: "image", gif: "image", webp: "image", avif: "image", bmp: "image", ico: "image", svg: "image",
  mp4: "video", m4v: "video", webm: "video", mov: "video", mkv: "video", ogv: "video",
  mp3: "audio", wav: "audio", ogg: "audio", oga: "audio", opus: "audio", flac: "audio", m4a: "audio", aac: "audio",
};

export function mediaKind(path: string): MediaKind | null {
  const dot = path.lastIndexOf(".");
  return dot < 0 ? null : KINDS[path.slice(dot + 1).toLowerCase()] ?? null;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const u = ["KB", "MB", "GB", "TB"];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}
