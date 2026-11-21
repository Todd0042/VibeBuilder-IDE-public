"""The server's side of the builder link.

The builder runs a small agent (builder/agent) that owns the terminals and runs git. The server never
runs git itself: a repo's .git/config can make git execute commands (fsmonitor, filters, hooks), and
the agents control every repo. Run in the builder, that only ever affects the builder.

Everything the agent says is treated as untrusted data (agents are root in there): shapes are checked
and sizes capped before anything is passed on to an app.
"""

from __future__ import annotations

import asyncio
import json
import re
import stat
from typing import Any

import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .auth.routes import SessionDep, ws_session
from .jail import JailError, clean_rel
from .services import services

router = APIRouter(prefix="/api/v1", tags=["terminals"])

KINDS = ("claude", "agy", "shell", "run")
_WAYPIPE = re.compile(r"^(/tmp/vb-rev/[a-z0-9-]{1,40}\.sock)?$")
_ID = re.compile(r"^[a-f0-9]{8,32}$")
MAX_INPUT = 64 * 1024


class AgentLink:
    def __init__(self, base_ws: str, token: str):
        self.ws_base = base_ws.rstrip("/")
        self.http_base = self.ws_base.replace("ws://", "http://", 1).replace("wss://", "https://", 1)
        self.token = token
        self._headers = {"Authorization": f"Bearer {token}"}

    # ---- HTTP ------------------------------------------------------------------------------
    async def get(self, path: str, **params: Any) -> Any:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(self.http_base + path, params=params, headers=self._headers)
        return self._check(r)

    async def post(self, path: str, body: dict, timeout: float = 10) -> Any:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(self.http_base + path, json=body, headers=self._headers)
        return self._check(r)

    async def delete(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(self.http_base + path, headers=self._headers)
        return self._check(r)

    @staticmethod
    def _check(r: httpx.Response) -> Any:
        if len(r.content) > 4 * 1024 * 1024:
            raise HTTPException(502, "The builder sent too much")
        try:
            data = r.json()
        except ValueError:
            raise HTTPException(502, "The builder sent something unreadable")
        if r.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            raise HTTPException(r.status_code if r.status_code < 500 else 502, str(detail or "Builder error")[:300])
        return data

    def attribute(self, started: float, ended: float, paths: list[str]) -> str:
        """Who made a change set (called from the recorder thread). Claude's edit hook names files
        exactly; otherwise it's the terminal that was busy while the files changed."""
        try:
            r = httpx.get(self.http_base + "/activity", params={"since": started - 15, "until": ended + 1},
                          headers=self._headers, timeout=3)
            a = r.json()
        except Exception:
            return "unknown"
        if not isinstance(a, dict):
            return "unknown"
        hooked = a.get("hook_edits") or {}
        if isinstance(hooked, dict):
            for kind in ("claude", "agy"):
                files = hooked.get(kind) or []
                if isinstance(files, list) and any(isinstance(f, str) and f in paths for f in files):
                    return kind
        busy = a.get("output_bytes") or {}
        if not isinstance(busy, dict):
            return "unknown"
        scores = {k: int(v) for k, v in busy.items() if k in KINDS and isinstance(v, (int, float)) and v > 0}
        if not scores:
            return "unknown"
        for kind in ("claude", "agy"):  # an agent at work beats a shell that printed something
            if scores.get(kind, 0) >= max(scores.values()) * 0.25:
                return kind
        return max(scores, key=scores.get)


# ---- terminals ----------------------------------------------------------------------------
def _clean_terminal(t: Any) -> dict | None:
    if not isinstance(t, dict) or not isinstance(t.get("id"), str) or not _ID.match(t["id"]):
        return None
    return {"id": t["id"], "kind": t.get("kind") if t.get("kind") in KINDS else "shell",
            "title": str(t.get("title") or "")[:80], "cwd": str(t.get("cwd") or "")[:500],
            "alive": bool(t.get("alive")), "exit_code": t.get("exit_code") if isinstance(t.get("exit_code"), int) else None,
            "created": float(t.get("created") or 0)}


@router.get("/terminals")
async def list_terminals(_: SessionDep, request: Request) -> dict:
    data = await services(request).agent.get("/terminals")
    items = data.get("terminals") if isinstance(data, dict) else None
    return {"terminals": [t for t in (_clean_terminal(x) for x in (items or [])[:50]) if t]}


class NewTerminal(BaseModel):
    kind: str = Field(pattern="^(claude|agy|shell|run)$")
    cwd: str = Field(default="", max_length=4096)
    cmd: str = Field(default="", max_length=2000)  # kind "run": the app to start
    waypipe_socket: str = Field(default="", max_length=200)  # its windows go to the laptop through this
    cols: int = Field(default=120, ge=10, le=1000)
    rows: int = Field(default=30, ge=4, le=500)


@router.post("/terminals")
async def new_terminal(body: NewTerminal, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    if not _WAYPIPE.match(body.waypipe_socket):
        raise HTTPException(400, "Bad waypipe socket")
    if body.kind == "run" and not body.cmd.strip():
        raise HTTPException(400, "What should it run?")
    try:
        cwd = clean_rel(body.cwd)
        if cwd:
            svc.jail.stat(cwd)  # must be a real folder in the workspace (not a symlink)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    t = _clean_terminal(await svc.agent.post("/terminals", {**body.model_dump(), "cwd": cwd}))
    if not t:
        raise HTTPException(502, "The builder didn't start a terminal")
    svc.live.publish("terminals", {})
    return t


@router.delete("/terminals/{tid}")
async def close_terminal(tid: str, _: SessionDep, request: Request) -> dict:
    if not _ID.match(tid):
        raise HTTPException(400, "Bad terminal")
    svc = services(request)
    await svc.agent.delete(f"/terminals/{tid}")
    svc.live.publish("terminals", {})
    return {"ok": True}


@router.websocket("/pty/{tid}")
async def pty(ws: WebSocket, tid: str) -> None:
    """App <-> server <-> builder. Output goes to the app as binary frames; the app sends JSON
    {"type": "input", "data": "..."} and {"type": "resize", "cols": c, "rows": r}."""
    s = await ws_session(ws)
    if s is None:
        return
    if not _ID.match(tid):
        await ws.close(code=4400)
        return
    svc = ws.app.state.svc
    loop = asyncio.get_running_loop()
    ended = asyncio.Event()
    remove = svc.sessions.add_closer(s, lambda: loop.call_soon_threadsafe(ended.set))
    try:
        async with websockets.connect(f"{svc.agent.ws_base}/pty/{tid}", max_size=4 * 1024 * 1024,
                                      additional_headers={"Authorization": f"Bearer {svc.agent.token}"}) as up:
            await ws.send_text(json.dumps({"type": "ready"}))

            async def down() -> None:  # builder -> app
                async for msg in up:
                    if isinstance(msg, bytes):
                        await ws.send_bytes(msg)
                    else:
                        try:
                            ev = json.loads(msg)
                        except ValueError:
                            continue
                        if isinstance(ev, dict) and ev.get("type") == "exit":
                            code = ev.get("code") if isinstance(ev.get("code"), int) else None
                            await ws.send_text(json.dumps({"type": "exit", "code": code}))

            async def upward() -> None:  # app -> builder (validated)
                while True:
                    raw = await ws.receive_text()
                    if len(raw) > MAX_INPUT + 100:
                        continue
                    try:
                        m = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(m, dict):
                        continue
                    if m.get("type") == "input" and isinstance(m.get("data"), str):
                        svc.sessions.activity(s)  # typing in a terminal counts as using the app
                        await up.send(json.dumps({"type": "input", "data": m["data"][:MAX_INPUT]}))
                    elif m.get("type") == "resize":
                        c, r = m.get("cols"), m.get("rows")
                        if isinstance(c, int) and isinstance(r, int) and 1 <= c <= 1000 and 1 <= r <= 500:
                            await up.send(json.dumps({"type": "resize", "cols": c, "rows": r}))

            tasks = {asyncio.ensure_future(down()), asyncio.ensure_future(upward()),
                     asyncio.ensure_future(ended.wait())}
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except (WebSocketDisconnect, websockets.ConnectionClosed, OSError, websockets.InvalidStatus):
        pass
    finally:
        remove()
        try:
            await ws.close(code=4401 if ended.is_set() else 1000)
        except RuntimeError:
            pass


# ---- git ----------------------------------------------------------------------------------
_XY = re.compile(r"^[ .MADRCU?!T]{2}$")


@router.get("/git/status")
async def git_status(project: str, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    try:
        project = clean_rel(project)
        if not project or not stat.S_ISDIR(svc.jail.stat(project).st_mode):
            raise HTTPException(400, "Pick a folder")
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    data = await svc.agent.get("/git/status", project=project)
    if not isinstance(data, dict) or not data.get("repo"):
        err = data.get("error") if isinstance(data, dict) else None
        return {"repo": False, "error": str(err)[:500]} if err else {"repo": False}
    files = []
    for f in (data.get("files") or [])[:5000]:
        if isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("xy"), str) and _XY.match(f["xy"]):
            try:
                files.append({"path": clean_rel(f["path"]), "xy": f["xy"]})
            except JailError:
                continue
    try:
        root = clean_rel(str(data.get("root") or ""))
    except JailError:
        return {"repo": False}
    return {"repo": True, "root": root, "branch": str(data.get("branch") or "")[:200], "ahead": int(data.get("ahead") or 0),
            "behind": int(data.get("behind") or 0), "files": files}
