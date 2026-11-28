// Shapes of the server's API (server/src/vbide). Shared by the laptop app and, later, the phone app.

export interface PairResult { device_id: string; device_name: string; device_token: string }
export interface LoginResult { session: string; idle_timeout_sec: number; device_id: string; device_name: string }

export type EntryKind = "dir" | "file" | "symlink" | "other";
export interface DirEntry { name: string; kind: EntryKind; size: number; mtime: number }
export interface DirListing { path: string; entries: DirEntry[]; truncated: boolean }
export interface FileContent { path: string; etag: string; size: number; mtime: number; binary: boolean; content: string }
export interface SaveResult { path: string; etag: string; size: number; mtime: number }

export interface SearchOptions {
  query: string; root: string; regex?: boolean; case_sensitive?: boolean; whole_word?: boolean;
  include?: string; exclude?: string; use_ignore_files?: boolean;
}
export interface SearchMatch { line: number; text: string; ranges: [number, number][] }
export interface SearchFile { path: string; matches: SearchMatch[] }
export interface SearchResult {
  files: SearchFile[]; match_count: number; truncated: boolean;
  /** Files ripgrep couldn't search (first 20) and how many there were; matches in non-UTF-8 files (not shown). */
  skipped?: { path: string; reason: string }[]; skipped_count?: number; not_text_matches?: number;
}

export type Source = "claude" | "agy" | "shell" | "unknown" | "offline" | "restore" | "you" | "agent";
export interface ChangesetSummary {
  id: number; started: number; ended: number; source: Source; label: string; closed: boolean;
  file_count: number; projects: string[]; paths: string[];
}
export interface DiffLine { t: " " | "-" | "+"; o: number | null; n: number | null; s: string }
export interface Hunk { old_start: number; old_count: number; new_start: number; new_count: number; lines: DiffLine[] }
export interface FileDiff {
  path: string; status: "added" | "deleted" | "modified"; before: string | null; after: string | null;
  added: number; removed: number; hunks: Hunk[]; note: string; deferred?: boolean;
}
export interface ChangesetDetail { id: number; started: number; ended: number; source: Source; label: string; closed: boolean; files: FileDiff[] }
export interface RangeDetail { since: number; until: number; files: FileDiff[] }
export interface FileVersion { id: number; ts: number; before: string | null; after: string | null; changeset: number | null; source: Source }

export type TerminalKind = "claude" | "agy" | "shell" | "run";
export interface TerminalInfo { id: string; kind: TerminalKind; title: string; cwd: string; alive: boolean; exit_code: number | null; created: number; preview?: boolean; display?: number | null }

export interface GitFile { path: string; xy: string }
export interface GitStatus { repo: boolean; error?: string; root?: string; branch?: string; ahead?: number; behind?: number; files?: GitFile[] }

/** One repo's result in a checkpoint (an automatic commit on the side branch checkpoints/<branch>). */
export interface CheckpointResult {
  repo: string; status: "committed" | "unchanged" | "skipped" | "failed"; branch?: string; ref?: string; commit?: string;
  title?: string; reason?: string; files?: number; rolled: boolean; left_out: { path: string; reason: string }[];
}
export interface CheckpointRun { at: number; results: CheckpointResult[] }
export interface CheckpointInfo { enabled: boolean; delay_sec: number; pending_since: number | null; last: CheckpointRun | null }

/** Something the server ran into in the background (problems.py); secrets are masked. */
export interface Problem { key: string; message: string; detail: string; fix: string; first: number; last: number; count: number }

export interface DeviceInfo { id: string; name: string; created: number; last_seen: number; last_ip: string; current: boolean }

export type LiveEvent =
  | { event: "hello" } | { event: "keepalive" }
  | { event: "fs"; paths: string[] }
  | ({ event: "changeset" } & Partial<ChangesetSummary>)
  | { event: "changeset.open"; id: number; started: number }
  | { event: "terminals" }
  | ({ event: "checkpoint"; project: string } & CheckpointRun)
  | ({ event: "problem" } & Problem);
