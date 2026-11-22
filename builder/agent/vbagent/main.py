"""The agent's HTTP/WebSocket API, for the IDE server only (bearer token from /run/vb-link/agent_token).

  GET    /terminals             list
  POST   /terminals             {kind, cwd, cols, rows} -> start one
  DELETE /terminals/{id}        close it
  WS     /pty/{id}              attach: scrollback, then live output (binary); input/resize as JSON
  GET    /activity              which terminals were busy, and hook-reported edits, in a time window
  POST   /hook                  {kind, path}: from the Claude Code edit hook in this container
  GET    /git/status?project=   branch + changed files of a project
  POST   /git/checkpoint        {folders, who}: checkpoint commit of the repos holding these folders
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import shutil
import subprocess
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .checkpoints import checkpoint_folders
from .terminals import WORKSPACE, Terminals
from .tunnels import Tunnels, listening_ports

TOKEN = Path(os.environ.get("VB_AGENT_TOKEN_FILE", "/run/vb-link/agent_token")).read_text().strip()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
terms = Terminals()
tunnels = Tunnels()
hook_edits: deque[tuple[float, str, str]] = deque(maxlen=5000)  # (when, kind, workspace-relative path)


def _authorized(headers) -> bool:
    h = headers.get("authorization", "")
    return h[:7].lower() == "bearer " and hmac.compare_digest(h[7:].strip(), TOKEN)


@app.middleware("http")
async def auth(request: Request, call_next):
    if not _authorized(request.headers):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "no"}, status_code=401)
    return await call_next(request)


@app.get("/terminals")
def list_terminals() -> dict:
    return {"terminals": [t.info() for t in sorted(terms.items.values(), key=lambda t: t.created)]}


class NewTerminal(BaseModel):
    kind: str = Field(pattern="^(claude|agy|shell|run)$")
    cwd: str = ""
    cmd: str = Field(default="", max_length=2000)
    waypipe_socket: str = Field(default="", pattern=r"^(/tmp/vb-rev/[a-z0-9-]{1,40}\.sock)?$")
    preview: bool = False
    cols: int = Field(default=120, ge=10, le=1000)
    rows: int = Field(default=30, ge=4, le=500)


@app.post("/terminals")
async def new_terminal(body: NewTerminal) -> dict:
    if len(terms.items) >= 40:
        raise HTTPException(429, "That's a lot of terminals. Close some first.")
    if body.kind == "run" and not body.cmd.strip():
        raise HTTPException(400, "What should it run?")
    return terms.spawn(body.kind, body.cwd, body.cols, body.rows, body.cmd, body.waypipe_socket, body.preview).info()


@app.delete("/terminals/{tid}")
async def close_terminal(tid: str) -> dict:
    if not terms.close(tid):
        raise HTTPException(404, "No such terminal")
    return {"ok": True}


@app.websocket("/preview/{tid}")
async def preview(ws: WebSocket, tid: str) -> None:
    if not _authorized(ws.headers):
        await ws.close(code=4401)
        return
    t = terms.items.get(tid)
    if not t or not t.preview or t.display is None:
        await ws.close(code=4404)
        return
    await ws.accept()
    await ws.send_text(json.dumps({"type": "ready", "display": t.display, "width": 1024, "height": 768}))

    disp = f":{t.display}"
    snap_event = asyncio.Event()
    snap_event.set()

    async def capture_loop():
        while t.alive:
            if shutil.which("import"):
                try:
                    p = await asyncio.create_subprocess_exec(
                        "import", "-window", "root", "-quality", "65", "jpg:-",
                        env={**os.environ, "DISPLAY": disp},
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    stdout, _ = await asyncio.wait_for(p.communicate(), timeout=2.0)
                    if stdout:
                        await ws.send_bytes(stdout)
                except Exception:
                    pass
            try:
                await asyncio.wait_for(snap_event.wait(), timeout=0.35)
                snap_event.clear()
            except asyncio.TimeoutError:
                pass

    async def input_loop():
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "click":
                x_norm = float(msg.get("x", 0))
                y_norm = float(msg.get("y", 0))
                btn = int(msg.get("button", 1))
                px = max(0, min(1024, int(x_norm * 1024)))
                py = max(0, min(768, int(y_norm * 768)))
                if shutil.which("xdotool"):
                    try:
                        subprocess.run(
                            ["xdotool", "mousemove", str(px), str(py), "click", str(btn)],
                            env={**os.environ, "DISPLAY": disp}, timeout=1,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except Exception:
                        pass
                snap_event.set()
            elif mtype == "type":
                text = str(msg.get("text", ""))[:200]
                if text and shutil.which("xdotool"):
                    try:
                        subprocess.run(
                            ["xdotool", "type", "--clearmodifiers", text],
                            env={**os.environ, "DISPLAY": disp}, timeout=2,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except Exception:
                        pass
                snap_event.set()
            elif mtype == "key":
                key = str(msg.get("key", ""))[:50]
                if key and shutil.which("xdotool"):
                    try:
                        subprocess.run(
                            ["xdotool", "key", key],
                            env={**os.environ, "DISPLAY": disp}, timeout=1,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except Exception:
                        pass
                snap_event.set()
            elif mtype == "refresh":
                snap_event.set()

    tasks = [asyncio.ensure_future(capture_loop()), asyncio.ensure_future(input_loop())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for p in pending:
            p.cancel()
    except (WebSocketDisconnect, Exception):
        pass


@app.websocket("/pty/{tid}")
async def pty(ws: WebSocket, tid: str) -> None:
    if not _authorized(ws.headers):
        await ws.close(code=4401)
        return
    t = terms.items.get(tid)
    if not t:
        await ws.close(code=4404)
        return
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    t.watchers.add(q)
    try:
        if t.buffer:
            await ws.send_bytes(bytes(t.buffer))
        if not t.alive:
            await ws.send_text(json.dumps({"type": "exit", "code": t.exit_code}))

        async def out() -> None:
            while True:
                chunk = await q.get()
                if chunk is None:
                    await ws.send_text(json.dumps({"type": "exit", "code": t.exit_code}))
                    continue
                parts = [chunk]
                while not q.empty() and sum(map(len, parts)) < 256 * 1024:  # batch bursts
                    nxt = q.get_nowait()
                    if nxt is None:
                        q.put_nowait(None)
                        break
                    parts.append(nxt)
                await ws.send_bytes(b"".join(parts))

        async def inp() -> None:
            while True:
                m = json.loads(await ws.receive_text())
                if m.get("type") == "input":
                    terms.write(t, str(m.get("data", "")))
                elif m.get("type") == "resize":
                    terms.resize(t, int(m["cols"]), int(m["rows"]))

        tasks = [asyncio.ensure_future(out()), asyncio.ensure_future(inp())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for p in pending:
            p.cancel()
    except (WebSocketDisconnect, ValueError, KeyError, RuntimeError):
        pass
    finally:
        t.watchers.discard(q)


@app.websocket("/tunnel/port/{port}")
async def tunnel_port(ws: WebSocket, port: int) -> None:
    if not _authorized(ws.headers):
        await ws.close(code=4401)
        return
    await tunnels.forward(ws, port)


@app.websocket("/tunnel/reverse/{conn}")
async def tunnel_reverse(ws: WebSocket, conn: str) -> None:
    if not _authorized(ws.headers):
        await ws.close(code=4401)
        return
    await tunnels.reverse_conn(ws, conn)


@app.websocket("/reverse")
async def reverse_control(ws: WebSocket) -> None:
    if not _authorized(ws.headers):
        await ws.close(code=4401)
        return
    await tunnels.control(ws)


@app.get("/ports")
def ports() -> dict:
    return {"ports": [p for p in listening_ports() if not tunnels.reverse_port(p["port"])]}


@app.get("/activity")
def activity(since: float, until: float) -> dict:
    edits: dict[str, list[str]] = {}
    for when, kind, path in hook_edits:
        if since <= when <= until:
            edits.setdefault(kind, []).append(path)
    return {"output_bytes": terms.output_between(since, until), "hook_edits": edits}


class Hook(BaseModel):
    kind: str = Field(pattern="^(claude|agy)$")
    path: str = Field(max_length=4096)


@app.post("/hook")
def hook(body: Hook) -> dict:
    p = body.path
    ws = str(WORKSPACE) + "/"
    if p.startswith(ws):
        hook_edits.append((time.time(), body.kind, p[len(ws):]))
    return {"ok": True}


@app.get("/git/status")
def git_status(project: str) -> dict:
    """Status of the repo containing `project` (any folder in the workspace). Paths are relative to
    the repo root, which is returned (workspace-relative) as "root"."""
    ws = WORKSPACE.resolve()
    folder = (WORKSPACE / project).resolve()
    if not folder.is_dir() or (folder != ws and ws not in folder.parents):
        return {"repo": False}
    try:
        r = subprocess.run(["git", "-C", str(folder), "rev-parse", "--show-toplevel"], capture_output=True,
                           timeout=10, text=True)
        if r.returncode != 0:
            if "not a git repository" in r.stderr:
                return {"repo": False}
            return {"repo": False, "error": r.stderr.strip()[:500] or f"git rev-parse exited {r.returncode}"}
        root = Path(r.stdout.strip()).resolve()
        if root != ws and ws not in root.parents:
            return {"repo": False}  # the repo is above the workspace
        s = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v2", "--branch", "-z",
                            "--untracked-files=all"], capture_output=True, timeout=15)
        if s.returncode != 0:
            return {"repo": False, "error": s.stderr.decode(errors="replace").strip()[:500] or "git status failed"}
        out = s.stdout
    except subprocess.TimeoutExpired:
        return {"repo": False, "error": "git didn't answer within 15 seconds (a very large repo, or a hung git process?)"}
    except OSError as exc:
        return {"repo": False, "error": f"couldn't run git: {exc}"}
    branch, ahead, behind, files = "", 0, 0, []
    items = out.split(b"\0")
    i = 0
    while i < len(items):
        line = items[i].decode(errors="replace")
        i += 1
        if line.startswith("# branch.head "):
            branch = line[14:]
        elif line.startswith("# branch.ab "):
            a, b = line[12:].split()
            ahead, behind = int(a), -int(b)
        elif line[:2] in ("1 ", "u "):
            parts = line.split(" ", 10 if line[0] == "u" else 8)
            files.append({"xy": parts[1], "path": parts[-1]})
        elif line.startswith("2 "):
            parts = line.split(" ", 9)
            files.append({"xy": parts[1], "path": parts[-1]})
            i += 1  # the original path follows
        elif line.startswith("? "):
            files.append({"xy": "??", "path": line[2:]})
        if len(files) >= 5000:
            break
    return {"repo": True, "root": str(root.relative_to(ws)) if root != ws else "", "branch": branch, "ahead": ahead,
            "behind": behind, "files": files}


class Checkpoint(BaseModel):
    folders: list[str] = Field(max_length=200)
    who: list[str] = Field(default=[], max_length=10)


@app.post("/git/checkpoint")
def git_checkpoint(body: Checkpoint) -> dict:
    """Runs in a worker thread: a checkpoint can take a while (Claude writes its message)."""
    folders = [f for f in body.folders if isinstance(f, str) and len(f) < 4096 and "\0" not in f]
    return {"results": checkpoint_folders(folders, [w for w in body.who if w in ("claude", "agy", "you", "shell")])}
