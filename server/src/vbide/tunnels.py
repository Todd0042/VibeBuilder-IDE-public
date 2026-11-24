"""/api/v1/tunnel, /api/v1/reverse, /api/v1/ports: app testing from the laptop.

The laptop app's native side uses these (never the web page) to:
  - forward a local port to a port in the builder (dev servers): WS /api/v1/tunnel {kind:"port"}
  - let the builder reach the laptop (adb for a plugged-in phone, waypipe for app windows):
      WS /api/v1/reverse     control: {type:"listen", id, tcp|unix} / {type:"close", id}; we pass on
                             the builder's {type:"listening"|"error"|"conn"} messages
      WS /api/v1/tunnel      {kind:"reverse", conn} for each connection the builder reported

Everything is behind the session (first message), and every message from either side is checked
before it's passed on: the builder is untrusted (agents are root there), and so is the network.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import websockets
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from .auth.routes import SessionDep, ws_session
from .services import services

log = logging.getLogger("vbide.tunnels")
router = APIRouter(prefix="/api/v1", tags=["tunnels"])

_LISTENER = re.compile(r"^[a-z0-9-]{1,40}$")
_CONN = re.compile(r"^[a-f0-9]{24}$")
_PATH = re.compile(r"^/tmp/vb-rev/[a-z0-9-]{1,40}\.sock$")
MAX_FRAME = 1 << 20


async def _start(ws: WebSocket):
    """Auth (first message) and the open request (second). Returns (session, request, ended-event)."""
    s = await ws_session(ws)
    if s is None:
        return None
    try:
        req = json.loads(await asyncio.wait_for(ws.receive_text(), 10))
    except Exception:
        await ws.close(code=4400)
        return None
    if not isinstance(req, dict):
        await ws.close(code=4400)
        return None
    svc = ws.app.state.svc
    loop = asyncio.get_running_loop()
    ended = asyncio.Event()
    remove = svc.sessions.add_closer(s, lambda: loop.call_soon_threadsafe(ended.set))
    return s, req, ended, remove


@router.websocket("/tunnel")
async def tunnel(ws: WebSocket) -> None:
    started = await _start(ws)
    if not started:
        return
    _s, req, ended, remove = started
    svc = ws.app.state.svc
    kind = req.get("kind")
    if kind == "port" and isinstance(req.get("port"), int) and 1 <= req["port"] <= 65535:
        path = f"/tunnel/port/{req['port']}"
    elif kind == "reverse" and isinstance(req.get("conn"), str) and _CONN.match(req["conn"]):
        path = f"/tunnel/reverse/{req['conn']}"
    else:
        await ws.close(code=4400)
        remove()
        return
    try:
        async with websockets.connect(svc.agent.ws_base + path, max_size=MAX_FRAME * 4,
                                      additional_headers={"Authorization": f"Bearer {svc.agent.token}"}) as up:
            await ws.send_text('{"type":"open"}')

            async def to_builder() -> None:
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        return
                    if msg.get("bytes"):
                        await up.send(msg["bytes"])

            async def to_laptop() -> None:
                async for data in up:
                    if isinstance(data, bytes):
                        await ws.send_bytes(data)

            tasks = [asyncio.ensure_future(t) for t in (to_builder(), to_laptop(), ended.wait())]
            _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except websockets.InvalidStatus as exc:
        log.debug("Tunnel target unavailable: %s", exc)
    except (WebSocketDisconnect, websockets.ConnectionClosed, OSError, RuntimeError) as exc:
        log.debug("Tunnel proxy closed: %s", exc)
    finally:
        remove()
        try:
            await ws.close(code=4401 if ended.is_set() else 1000)
        except RuntimeError as exc:
            log.debug("Tunnel ws.close ignored: %s", exc)


def _clean_from_laptop(m: object) -> dict | None:
    if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not _LISTENER.match(m["id"]):
        return None
    if m.get("type") == "close":
        return {"type": "close", "id": m["id"]}
    if m.get("type") != "listen":
        return None
    if m.get("unix") is True:
        return {"type": "listen", "id": m["id"], "unix": True}
    if isinstance(m.get("tcp"), int) and 1024 <= m["tcp"] <= 65535:
        return {"type": "listen", "id": m["id"], "tcp": m["tcp"]}
    return None


def _clean_from_builder(m: object) -> dict | None:
    if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not _LISTENER.match(m["id"]):
        return None
    t = m.get("type")
    if t == "conn" and isinstance(m.get("conn"), str) and _CONN.match(m["conn"]):
        return {"type": "conn", "id": m["id"], "conn": m["conn"]}
    if t == "listening":
        out: dict = {"type": "listening", "id": m["id"]}
        if isinstance(m.get("path"), str) and _PATH.match(m["path"]):
            out["path"] = m["path"]
        if isinstance(m.get("port"), int):
            out["port"] = m["port"]
        return out
    if t == "error":
        return {"type": "error", "id": m["id"], "detail": str(m.get("detail") or "")[:200]}
    return None


@router.websocket("/reverse")
async def reverse(ws: WebSocket) -> None:
    s = await ws_session(ws)
    if s is None:
        return
    svc = ws.app.state.svc
    loop = asyncio.get_running_loop()
    ended = asyncio.Event()
    remove = svc.sessions.add_closer(s, lambda: loop.call_soon_threadsafe(ended.set))
    try:
        async with websockets.connect(svc.agent.ws_base + "/reverse",
                                      additional_headers={"Authorization": f"Bearer {svc.agent.token}"}) as up:
            await ws.send_text('{"type":"ready"}')

            async def from_laptop() -> None:
                while True:
                    raw = await ws.receive_text()
                    try:
                        m = _clean_from_laptop(json.loads(raw))
                    except ValueError:
                        m = None
                    if m:
                        await up.send(json.dumps(m))

            async def from_builder() -> None:
                async for raw in up:
                    try:
                        m = _clean_from_builder(json.loads(raw))
                    except (ValueError, TypeError):
                        m = None
                    if m:
                        await ws.send_text(json.dumps(m))

            tasks = [asyncio.ensure_future(t) for t in (from_laptop(), from_builder(), ended.wait())]
            _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except (WebSocketDisconnect, websockets.ConnectionClosed, websockets.InvalidStatus, OSError, RuntimeError) as exc:
        log.debug("Reverse tunnel proxy closed: %s", exc)
    finally:
        remove()
        try:
            await ws.close(code=4401 if ended.is_set() else 1000)
        except RuntimeError as exc:
            log.debug("Reverse tunnel ws.close ignored: %s", exc)


@router.get("/ports")
async def ports(_: SessionDep, request: Request) -> dict:
    data = await services(request).agent.get("/ports")
    out = []
    for p in (data.get("ports") if isinstance(data, dict) else None) or []:
        if isinstance(p, dict) and isinstance(p.get("port"), int) and 1 <= p["port"] <= 65535:
            out.append({"port": p["port"], "process": str(p.get("process") or "")[:40]})
    return {"ports": out[:200]}
