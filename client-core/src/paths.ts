// Workspace-relative path helpers ("project/src/app.py").

export const basename = (p: string) => p.slice(p.lastIndexOf("/") + 1);
export const dirname = (p: string) => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");
export const join = (...parts: string[]) => parts.filter(Boolean).join("/").replace(/\/+/g, "/");
export const projectOf = (p: string) => p.split("/")[0] ?? "";
export const withinProject = (p: string) => p.split("/").slice(1).join("/");

export function relativeTime(epochSec: number, now = Date.now() / 1000): string {
  const d = Math.max(0, now - epochSec);
  if (d < 45) return "just now";
  if (d < 90) return "1 min ago";
  if (d < 3600) return `${Math.round(d / 60)} min ago`;
  if (d < 5400) return "1 hour ago";
  if (d < 86400) return `${Math.round(d / 3600)} hours ago`;
  const date = new Date(epochSec * 1000);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " " +
    date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function clockTime(epochSec: number): string {
  return new Date(epochSec * 1000).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
