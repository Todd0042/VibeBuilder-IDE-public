// The typed API client. No UI here: the laptop and phone apps both build on it.
import type {
  ChangesetDetail, ChangesetSummary, CheckpointInfo, CheckpointRun, DeviceInfo, Problem, DirListing, FileContent, FileDiff, FileVersion, GitStatus,
  LoginResult, PairResult, RangeDetail, SaveResult, SearchOptions, SearchResult, TerminalInfo, TerminalKind,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail: unknown = null) {
    super(message);
  }
}

export function normalizeServer(url: string): string {
  let u = url.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(u)) u = "https://" + u;
  return u;
}

export class Api {
  session: string | null = null;
  /** Called when the server says the session is gone (idle timeout, device removed, server restart). */
  onSignedOut: () => void = () => {};

  constructor(public server: string) {
    this.server = normalizeServer(server);
  }

  wsUrl(path: string): string {
    return this.server.replace(/^http/i, "ws") + path;
  }

  private async req<T>(method: string, path: string, body?: unknown, opts: { background?: boolean; auth?: boolean } = {}): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.auth !== false && this.session) headers["Authorization"] = `Bearer ${this.session}`;
    if (opts.background) headers["X-VB-Background"] = "1";
    let r: Response;
    try {
      r = await fetch(this.server + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw new ApiError(0, "Can't reach the IDE server. Check your connection.");
    }
    const text = await r.text();
    let data: any = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = null; }
    if (!r.ok) {
      const d = data?.detail;
      const msg = typeof d === "string" ? d : typeof d?.message === "string" ? d.message : `Request failed (${r.status})`;
      if (r.status === 401 && opts.auth !== false && this.session) {
        this.session = null;
        this.onSignedOut();
      }
      throw new ApiError(r.status, msg, d);
    }
    return data as T;
  }

  private q(params: Record<string, string | number | boolean | undefined | null>): string {
    const s = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
    const out = s.toString();
    return out ? "?" + out : "";
  }

  // ---- auth --------------------------------------------------------------------------------------
  pair(code: string, deviceName: string) {
    return this.req<PairResult>("POST", "/api/v1/auth/pair", { code, device_name: deviceName }, { auth: false });
  }
  async login(deviceToken: string, code: string) {
    const r = await this.req<LoginResult>("POST", "/api/v1/auth/login", { device_token: deviceToken, code }, { auth: false });
    this.session = r.session;
    return r;
  }
  async logout() {
    if (!this.session) return;
    try { await this.req("POST", "/api/v1/auth/logout"); } catch { /* signing out anyway */ }
    this.session = null;
  }
  ping() { return this.req<{ idle_remaining_sec: number }>("POST", "/api/v1/auth/ping"); }
  devices() { return this.req<{ max: number; devices: DeviceInfo[] }>("GET", "/api/v1/auth/devices"); }
  revokeDevice(id: string) { return this.req("DELETE", `/api/v1/auth/devices/${encodeURIComponent(id)}`); }

  // ---- files -------------------------------------------------------------------------------------
  projects() { return this.req<{ projects: string[]; hidden: string[] }>("GET", "/api/v1/projects"); }
  /** Hide a folder from the folder list, or show it again. Nothing on disk changes. */
  setHidden(path: string, hidden: boolean) { return this.req<{ hidden: string[] }>("PUT", "/api/v1/folders/hidden", { path, hidden }); }
  /** A URL an <img>/<video>/<audio> can load one file from, or to download a workspace file. */
  async mediaUrl(path: string, download = false) {
    const r = await this.req<{ url: string; mime: string; size: number }>("POST", "/api/v1/media/ticket", { path, download });
    return { ...r, url: this.server + r.url };
  }
  list(path: string, background = false) {
    // path "" is the workspace itself, so it's always sent (q() drops empty values)
    return this.req<DirListing>("GET", "/api/v1/fs/list?path=" + encodeURIComponent(path), undefined, { background });
  }
  read(path: string, background = false, asText = false) {
    return this.req<FileContent>("GET", "/api/v1/fs/file" + this.q({ path, as_text: asText ? 1 : undefined }), undefined, { background });
  }
  save(path: string, content: string, baseEtag: string | null, force = false, background = false) {
    return this.req<SaveResult>("PUT", "/api/v1/fs/file", { path, content, base_etag: baseEtag, force }, { background });
  }
  create(path: string, kind: "file" | "dir") { return this.req("POST", "/api/v1/fs/create", { path, kind }); }
  rename(src: string, dst: string) { return this.req("POST", "/api/v1/fs/rename", { src, dst }); }
  remove(path: string) { return this.req("POST", "/api/v1/fs/delete", { path }); }
  files(root: string) { return this.req<{ root: string; files: string[]; truncated: boolean }>("GET", "/api/v1/fs/files" + this.q({ root })); }
  search(o: SearchOptions) { return this.req<SearchResult>("POST", "/api/v1/search", o); }

  // ---- history -----------------------------------------------------------------------------------
  changesets(o: { before?: number; limit?: number; project?: string } = {}, background = false) {
    return this.req<{ changesets: ChangesetSummary[]; open: { id: number; started: number; files: number } | null }>(
      "GET", "/api/v1/history/changesets" + this.q(o), undefined, { background });
  }
  changeset(id: number, context = 3, project = "") {
    return this.req<ChangesetDetail>("GET", `/api/v1/history/changesets/${id}` + this.q({ context, project }));
  }
  range(since: number, until: number | null, context = 3, project = "") {
    return this.req<RangeDetail>("GET", "/api/v1/history/range" + this.q({ since, until, context, project }));
  }
  fileDiff(path: string, before: string | null, after: string | null, context: number) {
    return this.req<FileDiff>("GET", "/api/v1/history/filediff" + this.q({ path, before: before ?? "", after: after ?? "", context }));
  }
  historyUsage() {
    return this.req<{ stored_bytes: number; raw_bytes: number; blobs: number; versions: number; cap_bytes: number }>(
      "GET", "/api/v1/history/usage", undefined, { background: true });
  }
  pruneHistory(capGb?: number) {
    return this.req<{ freed_bytes: number; usage: { stored_bytes: number; raw_bytes: number; blobs: number; versions: number; cap_bytes: number } }>(
      "POST", "/api/v1/history/prune", capGb !== undefined ? { cap_gb: capGb } : {});
  }
  fileTimeline(path: string) { return this.req<{ path: string; versions: FileVersion[] }>("GET", "/api/v1/history/file" + this.q({ path })); }
  restoreChangeset(changeset: number) { return this.req<{ changeset: number; restored: string[] }>("POST", "/api/v1/history/restore", { changeset }); }
  restoreFile(path: string, state: string | null) {
    return this.req<{ changeset: number; restored: string[] }>("POST", "/api/v1/history/restore", { path, state: state ?? "" });
  }

  // ---- terminals and git -------------------------------------------------------------------------
  terminals() { return this.req<{ terminals: TerminalInfo[] }>("GET", "/api/v1/terminals", undefined, { background: true }); }
  newTerminal(kind: TerminalKind, cwd: string, cols: number, rows: number, run?: { cmd: string; waypipeSocket?: string; preview?: boolean }) {
    return this.req<TerminalInfo>("POST", "/api/v1/terminals",
      { kind, cwd, cols, rows, cmd: run?.cmd ?? "", waypipe_socket: run?.waypipeSocket ?? "", preview: run?.preview ?? false });
  }
  ports() { return this.req<{ ports: { port: number; process: string }[] }>("GET", "/api/v1/ports", undefined, { background: true }); }
  closeTerminal(id: string) { return this.req("DELETE", `/api/v1/terminals/${encodeURIComponent(id)}`); }
  gitStatus(project: string) { return this.req<GitStatus>("GET", "/api/v1/git/status" + this.q({ project }), undefined, { background: true }); }

  // ---- checkpoints and starter agent rules -------------------------------------------------------
  checkpoints(project: string) {
    return this.req<CheckpointInfo>("GET", "/api/v1/checkpoints" + this.q({ project }), undefined, { background: true });
  }
  setCheckpoints(project: string, enabled: boolean) { return this.req<CheckpointInfo>("PUT", "/api/v1/checkpoints", { project, enabled }); }
  checkpointNow(project: string) { return this.req<CheckpointRun>("POST", "/api/v1/checkpoints/now", { project }); }
  /** Adds AGENTS.md (+ CLAUDE.md) to a project without agent rules, once ever. */
  ensureAgentRules(project: string) {
    return this.req<{ created: string[]; failed: { path: string; reason: string }[] }>(
      "POST", "/api/v1/agent-rules", { project }, { background: true });
  }

  // ---- problems the server ran into ----------------------------------------------------------------
  problems() { return this.req<{ problems: Problem[] }>("GET", "/api/v1/problems", undefined, { background: true }); }
  dismissProblem(key: string) { return this.req("DELETE", `/api/v1/problems/${encodeURIComponent(key)}`); }
}
