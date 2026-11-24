"""/api/v1/fs: the folder tree, opening and saving files. All paths go through the Jail."""

from __future__ import annotations

import hashlib
import json
import os
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .auth.routes import SessionDep
from .jail import JailError, clean_rel
from .services import services

router = APIRouter(prefix="/api/v1", tags=["files"])


def etag_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_text(data: bytes) -> str | None:
    """UTF-8 text, or None for anything binary."""
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        import logging
        logging.getLogger("vbide.files").debug("Non-UTF-8 file treated as binary: %s", exc)
        return None


def _jail_call(fn, *args):
    try:
        return fn(*args)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    except PermissionError:
        raise HTTPException(403, "Permission denied (owned by root in the builder?)")
    except IsADirectoryError:
        raise HTTPException(400, "That's a folder")
    except OSError as exc:
        raise HTTPException(400, exc.strerror or "File error")


@router.get("/projects")
async def projects(_: SessionDep, request: Request) -> dict:
    svc = services(request)
    entries = await run_in_threadpool(_jail_call, svc.jail.list_dir, "")
    names: list[str] = []
    for e in entries:
        if e.kind != "dir" or e.name.startswith("."):
            continue
        if e.name.lower() == "github":
            try:
                gh_entries = await run_in_threadpool(_jail_call, svc.jail.list_dir, e.name)
                for sub in gh_entries:
                    if sub.kind == "dir" and not sub.name.startswith("."):
                        names.append(f"{e.name}/{sub.name}")
            except Exception:
                pass
        else:
            names.append(e.name)
    names.sort(key=str.lower)
    return {"projects": names, "hidden": sorted(_hidden(svc.settings.folders_file), key=str.lower)}


# ---- folders hidden from the folder list (only hidden: nothing on disk changes) ----------------------
_folders_lock = threading.Lock()
MAX_HIDDEN = 5000


def _hidden(path) -> set[str]:
    try:
        data = json.loads(path.read_text())
        return {p for p in data.get("hidden", []) if isinstance(p, str)}
    except FileNotFoundError:
        return set()
    except (OSError, ValueError, AttributeError) as exc:
        raise HTTPException(500, f"Couldn't read the hidden-folders list ({path}): {exc}")


class HideBody(BaseModel):
    path: str = Field(max_length=4096)
    hidden: bool


@router.put("/folders/hidden")
def set_hidden(body: HideBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    rel = _jail_call(clean_rel, body.path)
    if not rel:
        raise HTTPException(400, "Pick a folder")
    f = svc.settings.folders_file
    with _folders_lock:
        hidden = _hidden(f)
        if body.hidden:
            if len(hidden) >= MAX_HIDDEN:
                raise HTTPException(400, "Too many hidden folders")
            hidden.add(rel)
        else:
            hidden.discard(rel)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"hidden": sorted(hidden)}, indent=1))
        os.replace(tmp, f)
    return {"hidden": sorted(hidden, key=str.lower)}


@router.get("/fs/list")
async def list_dir(path: str, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    rel = _jail_call(clean_rel, path)
    entries = await run_in_threadpool(_jail_call, svc.jail.list_dir, rel)
    entries.sort(key=lambda e: (e.kind != "dir", e.name.lower()))
    return {"path": rel, "entries": [{"name": e.name, "kind": e.kind, "size": e.size, "mtime": e.mtime}
                                     for e in entries[:20_000]], "truncated": len(entries) > 20_000}


@router.get("/fs/file")
async def read_file(path: str, _: SessionDep, request: Request, as_text: bool = False) -> dict:
    svc = services(request)
    rel = _jail_call(clean_rel, path)
    data, s = await run_in_threadpool(_jail_call, svc.jail.read_file, rel, svc.settings.max_file_bytes)
    text = decode_text(data)
    if text is None and as_text:
        text = data.decode("utf-8", errors="replace")
    return {"path": rel, "etag": etag_of(data), "size": len(data), "mtime": s.st_mtime,
            "binary": text is None, "content": text if text is not None else ""}


class SaveBody(BaseModel):
    path: str = Field(max_length=4096)
    content: str
    base_etag: str | None = Field(default=None, max_length=64)  # what the editor opened; None = new file
    force: bool = False


@router.put("/fs/file")
async def save_file(body: SaveBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    rel = _jail_call(clean_rel, body.path)
    data = body.content.encode("utf-8")
    if len(data) > svc.settings.max_file_bytes:
        raise HTTPException(413, "File too large")

    def save() -> dict:
        if not body.force:
            try:
                cur, _s = svc.jail.read_file(rel, svc.settings.max_file_bytes)
                cur_etag = etag_of(cur)
            except JailError as exc:
                if exc.status != 404:
                    raise
                cur_etag = None
            if cur_etag != body.base_etag and cur_etag != etag_of(data):
                raise HTTPException(409, {"message": "The file changed since you opened it", "current_etag": cur_etag})
        svc.recorder.expect_own_write(rel, data)
        s = svc.jail.write_file(rel, data)
        return {"path": rel, "etag": etag_of(data), "size": len(data), "mtime": s.st_mtime}

    return await run_in_threadpool(_jail_call, save)


class CreateBody(BaseModel):
    path: str = Field(max_length=4096)
    kind: str = Field(pattern="^(file|dir)$")


@router.post("/fs/create")
async def create(body: CreateBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    rel = _jail_call(clean_rel, body.path)
    await run_in_threadpool(_jail_call, svc.jail.mkdir if body.kind == "dir" else svc.jail.create_file, rel)
    return {"path": rel}


class RenameBody(BaseModel):
    src: str = Field(max_length=4096)
    dst: str = Field(max_length=4096)


@router.post("/fs/rename")
async def rename(body: RenameBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    src, dst = _jail_call(clean_rel, body.src), _jail_call(clean_rel, body.dst)
    await run_in_threadpool(_jail_call, svc.jail.rename, src, dst)
    return {"src": src, "dst": dst}


class DeleteBody(BaseModel):
    path: str = Field(max_length=4096)


@router.post("/fs/delete")
async def delete(body: DeleteBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    rel = _jail_call(clean_rel, body.path)
    if not rel:
        raise HTTPException(400, "The workspace root itself cannot be deleted")
    await run_in_threadpool(_jail_call, svc.jail.delete, rel)
    return {"path": rel}
