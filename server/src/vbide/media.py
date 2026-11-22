"""Media viewing: images, audio and video play in the app's own tab, straight from the workspace.

An <img>/<video>/<audio> element can't send an Authorization header, so the app first asks for a
ticket for one file, then points the element at /api/v1/media/raw?t=<ticket>. A ticket:
  - is random and opaque (it is not the session token, which never goes in a URL);
  - opens only the one file it was made for, read-only;
  - dies with the session that made it (lock, idle timeout, device revoked, server restart), and
    after TICKET_TTL_SEC at the latest.
Range requests are supported so video can seek without downloading the whole file.

  POST /api/v1/media/ticket {path} -> {url, mime, size}
  GET  /api/v1/media/raw?t=...       (bytes; 206 for a Range)
"""

from __future__ import annotations

import os
import posixpath
import re
import secrets
import stat as st
import threading
import time
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from .auth.routes import SessionDep
from .jail import JailError, clean_rel
from .services import services

router = APIRouter(prefix="/api/v1/media", tags=["media"])

TICKET_TTL_SEC = 12 * 3600
MAX_TICKETS = 2000
CHUNK = 256 * 1024

# What the app shows. Anything else is refused, so the endpoint can't be used as a general download.
MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".avif": "image/avif", ".bmp": "image/bmp", ".ico": "image/x-icon", ".svg": "image/svg+xml",
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
    ".ogv": "video/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".oga": "audio/ogg",
    ".opus": "audio/opus", ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac",
}


@dataclass
class Ticket:
    session_key: str
    path: str
    expires: float


_tickets: dict[str, Ticket] = {}
_lock = threading.Lock()


def mime_of(path: str) -> str | None:
    return MIME.get(posixpath.splitext(path)[1].lower())


class TicketBody(BaseModel):
    path: str = Field(max_length=4096)


@router.post("/ticket")
async def ticket(body: TicketBody, s: SessionDep, request: Request) -> dict:
    svc = services(request)
    try:
        rel = clean_rel(body.path)
        mime = mime_of(rel)
        if not mime:
            raise HTTPException(415, "Not a media file the viewer can show")
        info = await run_in_threadpool(svc.jail.stat, rel)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    if not st.S_ISREG(info.st_mode):
        raise HTTPException(400, "Not a regular file")
    now = time.time()
    t = secrets.token_urlsafe(24)
    with _lock:
        for k in [k for k, v in _tickets.items() if v.expires < now or not svc.sessions.get_by_key(v.session_key)]:
            del _tickets[k]
        if len(_tickets) >= MAX_TICKETS:
            raise HTTPException(429, "Too many media files open; close some tabs")
        _tickets[t] = Ticket(s.key, rel, now + TICKET_TTL_SEC)
    return {"url": f"/api/v1/media/raw?t={t}", "mime": mime, "size": info.st_size}


_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(h: str, size: int) -> tuple[int, int] | None:
    """One byte range, inclusive. None = whole file. Raises 416 for one that can't be satisfied."""
    m = _RANGE.match(h.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None  # multi-range or malformed: ignore it and send everything (allowed by RFC 9110)
    if m.group(1):
        start = int(m.group(1))
        end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
    else:
        start, end = max(0, size - int(m.group(2))), size - 1
    if start >= size or start > end:
        raise HTTPException(416, "Range not satisfiable", headers={"Content-Range": f"bytes */{size}"})
    return start, end


@router.get("/raw")
async def raw(t: str, request: Request):
    svc = services(request)
    with _lock:
        tk = _tickets.get(t) if len(t) <= 64 else None
    s = svc.sessions.get_by_key(tk.session_key) if tk else None
    if not tk or tk.expires < time.time() or not s or not svc.devices.exists(s.device_id):
        with _lock:
            _tickets.pop(t, None)
        raise HTTPException(401, "This media link has expired; reopen the file")
    mime = mime_of(tk.path) or "application/octet-stream"

    def open_file() -> tuple[int, int]:
        fd = svc.jail.open(tk.path, os.O_RDONLY | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not st.S_ISREG(info.st_mode):
            os.close(fd)
            raise JailError("Not a regular file", 400)
        return fd, info.st_size

    try:
        fd, size = await run_in_threadpool(open_file)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    except OSError as exc:
        raise HTTPException(400, exc.strerror or "File error")

    try:
        rng = _parse_range(request.headers.get("range", ""), size) if size else None
    except HTTPException:
        os.close(fd)
        raise
    start, end = rng if rng else (0, size - 1)
    length = max(0, end - start + 1)

    closed = False

    def close() -> None:
        nonlocal closed
        if not closed:
            closed = True
            os.close(fd)

    def body():
        try:
            pos, left = start, length
            while left > 0:
                b = os.pread(fd, min(CHUNK, left), pos)
                if not b:
                    break  # the file shrank while playing
                pos += len(b)
                left -= len(b)
                yield b
        finally:
            close()

    headers = {
        "Accept-Ranges": "bytes", "Content-Length": str(length),
        # Shown as media only, never as a page on the server's origin (an SVG's scripts can't run).
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        "Content-Disposition": "inline",
    }
    if rng:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    # The background task closes the file if the player hangs up before the body is read.
    return StreamingResponse(body(), status_code=206 if rng else 200, headers=headers, media_type=mime,
                             background=BackgroundTask(close))

