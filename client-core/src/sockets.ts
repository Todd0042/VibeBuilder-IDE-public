// WebSockets: the live event stream and terminal connections. Both authenticate with their first
// message (never the URL), and both reconnect on their own unless the server ended the session.
import type { Api } from "./api";
import type { LiveEvent } from "./types";

const SIGNED_OUT = 4401;

function parseJson(raw: string): any | null {
  try {
    return JSON.parse(raw);
  } catch (err) {
    console.debug("Ignoring malformed WebSocket JSON frame:", err);
    return null;
  }
}

export class LiveSocket {
  private ws: WebSocket | null = null;
  private stopped = false;
  private retry = 500;
  connected = false;
  onStatus: (connected: boolean) => void = () => {};

  constructor(private api: Api, private onEvent: (e: LiveEvent) => void) {}

  start() {
    this.stopped = false;
    this.open();
  }

  stop() {
    this.stopped = true;
    this.ws?.close();
    this.ws = null;
  }

  private open() {
    if (this.stopped || !this.api.session) return;
    const ws = new WebSocket(this.api.wsUrl("/api/v1/live"));
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", session: this.api.session }));
    ws.onmessage = (m) => {
      const e = parseJson(m.data) as LiveEvent | null;
      if (!e) return;
      if (e.event === "hello") {
        this.retry = 500;
        this.setConnected(true);
      }
      this.onEvent(e);
    };
    ws.onclose = (ev) => {
      this.setConnected(false);
      if (ev.code === SIGNED_OUT) {
        if (this.api.session) {
          this.api.session = null;
          this.api.onSignedOut();
        }
        return;
      }
      if (!this.stopped) {
        setTimeout(() => this.open(), this.retry);
        this.retry = Math.min(this.retry * 2, 10_000);
      }
    };
  }

  private setConnected(v: boolean) {
    if (this.connected !== v) {
      this.connected = v;
      this.onStatus(v);
    }
  }
}

export interface PtyHandlers {
  onData: (data: Uint8Array) => void;
  onExit: (code: number | null) => void;
  onState: (state: "connecting" | "open" | "closed") => void;
}

export class PtySocket {
  private ws: WebSocket | null = null;
  private stopped = false;
  private retry = 500;
  private ready = false;
  private queue: string[] = [];
  private size: { cols: number; rows: number } | null = null;

  constructor(private api: Api, public id: string, private h: PtyHandlers) {}

  start() {
    this.stopped = false;
    this.open();
  }

  stop() {
    this.stopped = true;
    this.ws?.close();
    this.ws = null;
  }

  /** On reconnect the server replays the scrollback, so the terminal is cleared first. */
  onReconnect: () => void = () => {};

  private open(reconnect = false) {
    if (this.stopped || !this.api.session) return;
    this.h.onState("connecting");
    this.ready = false;
    const ws = new WebSocket(this.api.wsUrl(`/api/v1/pty/${this.id}`));
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", session: this.api.session }));
    ws.onmessage = (m) => {
      if (m.data instanceof ArrayBuffer) {
        this.h.onData(new Uint8Array(m.data));
        return;
      }
      const ev = parseJson(m.data);
      if (!ev) return;
      if (ev.type === "ready") {
        if (reconnect) this.onReconnect();
        this.ready = true;
        this.retry = 500;
        this.h.onState("open");
        if (this.size) this.send({ type: "resize", ...this.size });
        for (const q of this.queue.splice(0)) ws.send(q);
      } else if (ev.type === "exit") {
        this.h.onExit(typeof ev.code === "number" ? ev.code : null);
      }
    };
    ws.onclose = (ev) => {
      this.ready = false;
      this.h.onState("closed");
      if (ev.code === SIGNED_OUT || this.stopped) return;
      setTimeout(() => this.open(true), this.retry);
      this.retry = Math.min(this.retry * 2, 10_000);
    };
  }

  private send(msg: object) {
    const s = JSON.stringify(msg);
    if (this.ready && this.ws?.readyState === WebSocket.OPEN) this.ws.send(s);
    else if (this.queue.length < 200) this.queue.push(s);
  }

  input(data: string) {
    this.send({ type: "input", data });
  }

  resize(cols: number, rows: number) {
    this.size = { cols, rows };
    if (this.ready) this.send({ type: "resize", cols, rows });
  }
}

export interface PreviewHandlers {
  onFrame: (blob: Blob) => void;
  onReady?: (info: { width: number; height: number; display: number }) => void;
  onExit?: (code: number | null) => void;
  onState?: (state: "connecting" | "open" | "closed") => void;
}

export class PreviewSocket {
  private ws: WebSocket | null = null;
  private stopped = false;
  private retry = 1000;
  private ready = false;

  constructor(private api: Api, public id: string, private h: PreviewHandlers) {}

  start() {
    this.stopped = false;
    this.open();
  }

  stop() {
    this.stopped = true;
    this.ws?.close();
    this.ws = null;
  }

  private open() {
    if (this.stopped || !this.api.session) return;
    this.h.onState?.("connecting");
    this.ready = false;
    const ws = new WebSocket(this.api.wsUrl(`/api/v1/preview/${encodeURIComponent(this.id)}`));
    ws.binaryType = "blob";
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", session: this.api.session }));
    ws.onmessage = (m) => {
      if (m.data instanceof Blob) {
        this.h.onFrame(m.data);
        return;
      }
      if (m.data instanceof ArrayBuffer) {
        this.h.onFrame(new Blob([m.data], { type: "image/jpeg" }));
        return;
      }
      const ev = parseJson(m.data);
      if (!ev) return;
      if (ev.type === "ready") {
        this.ready = true;
        this.retry = 1000;
        this.h.onState?.("open");
        this.h.onReady?.(ev);
      } else if (ev.type === "exit") {
        this.h.onExit?.(typeof ev.code === "number" ? ev.code : null);
      }
    };
    ws.onclose = (ev) => {
      this.ready = false;
      this.h.onState?.("closed");
      if (ev.code === SIGNED_OUT || this.stopped) return;
      setTimeout(() => this.open(), this.retry);
      this.retry = Math.min(this.retry * 2, 10_000);
    };
  }

  private send(msg: object) {
    if (this.ready && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  click(x: number, y: number, button = 1) {
    this.send({ type: "click", x, y, button });
  }

  type(text: string) {
    this.send({ type: "type", text });
  }

  key(key: string) {
    this.send({ type: "key", key });
  }

  refresh() {
    this.send({ type: "refresh" });
  }
}
