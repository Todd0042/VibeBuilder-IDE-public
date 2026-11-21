"""/api/v1/live: one WebSocket per app window for everything that changes on its own: files touched on
disk, change sets opening and closing, terminals coming and going. Publishing is thread-safe (the
history recorder runs in threads)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .auth.routes import ws_session

router = APIRouter(tags=["live"])


class LiveHub:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: str, payload: dict) -> None:
        if self._loop is None:
            return
        msg = json.dumps({"event": event, **payload})
        try:
            self._loop.call_soon_threadsafe(self._fanout, msg)
        except RuntimeError:
            pass  # loop closed during shutdown

    def _fanout(self, msg: str) -> None:
        for q in list(self._clients):
            if q.qsize() < 1000:  # a stuck client drops events instead of growing memory
                q.put_nowait(msg)

    async def serve(self, ws: WebSocket, end_signal: asyncio.Event) -> None:
        q: asyncio.Queue = asyncio.Queue()
        self._clients.add(q)
        try:
            await ws.send_text(json.dumps({"event": "hello"}))
            while not end_signal.is_set():
                get = asyncio.ensure_future(q.get())
                ended = asyncio.ensure_future(end_signal.wait())
                done, pending = await asyncio.wait({get, ended}, timeout=25, return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                if get in done:
                    await ws.send_text(get.result())
                elif not done:
                    await ws.send_text('{"event":"keepalive"}')
        finally:
            self._clients.discard(q)


@router.websocket("/api/v1/live")
async def live(ws: WebSocket) -> None:
    s = await ws_session(ws)
    if s is None:
        return
    svc = ws.app.state.svc
    ended = asyncio.Event()
    loop = asyncio.get_running_loop()
    remove = svc.sessions.add_closer(s, lambda: loop.call_soon_threadsafe(ended.set))

    async def drain() -> None:  # the app never sends anything after auth; just notice it going away
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ended.set()

    reader = asyncio.ensure_future(drain())
    try:
        await svc.live.serve(ws, ended)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        reader.cancel()
        remove()
        try:
            await ws.close(code=4401 if not svc.sessions.get_by_key(s.key) else 1000)
        except RuntimeError:
            pass
