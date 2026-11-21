"""Tunnels between the builder and the laptop (through the IDE server, which does the auth).

forward   laptop -> builder: the laptop accepts a connection on one of its ports and asks for
          127.0.0.1:<port> here (a dev server, say). One WebSocket per connection.
reverse   builder -> laptop: the laptop asks us to listen here (adb's port 5037; a unix socket that
          waypipe's server side connects to). When something connects, we tell the laptop over its
          control socket, and it opens a WebSocket for that connection, which we pair with it.

The laptop only ever connects to the targets *it* registered, so nothing in here can make it reach
anywhere else.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

REVERSE_DIR = Path("/tmp/vb-rev")
LISTENER_ID = re.compile(r"^[a-z0-9-]{1,40}$")
RESERVED_PORTS = {7070}  # the agent itself
PENDING_TIMEOUT = 20


async def pipe(ws: WebSocket, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Bytes both ways until either side closes."""

    async def up() -> None:  # socket -> websocket
        while data := await reader.read(65536):
            await ws.send_bytes(data)

    async def down() -> None:  # websocket -> socket
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return
            data = msg.get("bytes")
            if data:
                writer.write(data)
                await writer.drain()

    tasks = [asyncio.ensure_future(up()), asyncio.ensure_future(down())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (WebSocketDisconnect, ConnectionError, RuntimeError):
        pass
    finally:
        for t in tasks:
            t.cancel()
        writer.close()
        try:
            await ws.close()
        except RuntimeError:
            pass


@dataclass
class Listener:
    id: str
    server: asyncio.base_events.Server
    path: str = ""
    port: int = 0


@dataclass(eq=False)  # kept in a set: identity, not value
class ReverseSession:
    """One laptop's control socket and the listeners it asked for."""
    send: Callable[[dict], Awaitable[None]]
    listeners: dict[str, Listener] = field(default_factory=dict)


class Tunnels:
    def __init__(self) -> None:
        self.pending: dict[str, tuple[asyncio.StreamReader, asyncio.StreamWriter, float]] = {}
        self.sessions: set[ReverseSession] = set()

    # ---- forward -----------------------------------------------------------------------------
    async def forward(self, ws: WebSocket, port: int) -> None:
        if not 1 <= port <= 65535 or port in RESERVED_PORTS or self.reverse_port(port):
            await ws.close(code=4400)
            return
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 5)
        except (OSError, TimeoutError):
            await ws.close(code=4502)  # nothing listening there
            return
        await ws.accept()
        await pipe(ws, reader, writer)

    # ---- reverse -----------------------------------------------------------------------------
    def reverse_port(self, port: int) -> bool:
        return any(lst.port == port for s in self.sessions for lst in s.listeners.values())

    async def listen(self, sess: ReverseSession, lid: str, tcp: int | None, unix: bool) -> dict:
        if not LISTENER_ID.match(lid) or lid in sess.listeners:
            return {"type": "error", "id": lid, "detail": "bad or duplicate listener id"}

        async def accepted(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            conn = secrets.token_hex(12)
            self.pending[conn] = (reader, writer, time.time())
            try:
                await sess.send({"type": "conn", "id": lid, "conn": conn})
            except Exception:
                self.pending.pop(conn, None)
                writer.close()

        try:
            if unix:
                REVERSE_DIR.mkdir(mode=0o700, exist_ok=True)
                path = str(REVERSE_DIR / f"{lid}.sock")
                if os.path.exists(path):
                    os.unlink(path)
                server = await asyncio.start_unix_server(accepted, path)
                os.chmod(path, 0o600)
                sess.listeners[lid] = Listener(lid, server, path=path)
                return {"type": "listening", "id": lid, "path": path}
            if tcp is None or not 1024 <= tcp <= 65535 or tcp in RESERVED_PORTS:
                return {"type": "error", "id": lid, "detail": "pick a port from 1024 to 65535"}
            server = await asyncio.start_server(accepted, "127.0.0.1", tcp)
            sess.listeners[lid] = Listener(lid, server, port=tcp)
            return {"type": "listening", "id": lid, "port": tcp}
        except OSError as exc:
            return {"type": "error", "id": lid, "detail": f"can't listen: {exc.strerror}"}

    def unlisten(self, sess: ReverseSession, lid: str) -> None:
        lst = sess.listeners.pop(lid, None)
        if lst:
            lst.server.close()
            if lst.path:
                try:
                    os.unlink(lst.path)
                except OSError:
                    pass

    async def control(self, ws: WebSocket) -> None:
        await ws.accept()
        sess = ReverseSession(send=ws.send_json)
        self.sessions.add(sess)
        try:
            while True:
                m = await ws.receive_json()
                if not isinstance(m, dict):
                    continue
                if m.get("type") == "listen":
                    tcp = m.get("tcp") if isinstance(m.get("tcp"), int) else None
                    await ws.send_json(await self.listen(sess, str(m.get("id", "")), tcp, bool(m.get("unix"))))
                elif m.get("type") == "close":
                    self.unlisten(sess, str(m.get("id", "")))
        except (WebSocketDisconnect, ValueError, RuntimeError):
            pass
        finally:
            for lid in list(sess.listeners):
                self.unlisten(sess, lid)
            self.sessions.discard(sess)

    async def reverse_conn(self, ws: WebSocket, conn: str) -> None:
        self._expire()
        got = self.pending.pop(conn, None)
        if not got:
            await ws.close(code=4404)
            return
        reader, writer, _ = got
        await ws.accept()
        await pipe(ws, reader, writer)

    def _expire(self) -> None:
        now = time.time()
        for conn, (_r, w, t) in list(self.pending.items()):
            if now - t > PENDING_TIMEOUT:
                self.pending.pop(conn, None)
                w.close()


def listening_ports() -> list[dict]:
    """TCP ports something in the builder listens on (for "forward this port?"), with process names."""
    inodes: dict[str, int] = {}
    for name in ("tcp", "tcp6"):
        try:
            lines = Path(f"/proc/net/{name}").read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10 or parts[3] != "0A":  # LISTEN
                continue
            port = int(parts[1].rsplit(":", 1)[1], 16)
            inodes[parts[9]] = port
    procs: dict[int, str] = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            for fd in os.listdir(f"/proc/{pid}/fd"):
                target = os.readlink(f"/proc/{pid}/fd/{fd}")
                if target.startswith("socket:[") and target[8:-1] in inodes:
                    port = inodes[target[8:-1]]
                    if port not in procs:
                        procs[port] = Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            continue
    ports = sorted(set(inodes.values()) - RESERVED_PORTS)
    return [{"port": p, "process": procs.get(p, "")} for p in ports]
