"""/api/v1/history: change sets, time-range reviews, per-file timelines, restores."""

from __future__ import annotations

import re
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..auth.routes import SessionDep
from ..files import decode_text
from ..jail import JailError, clean_rel
from ..services import Services, services
from .diffing import hunks
from .recorder import project_of
from .store import BINARY_PREFIX

router = APIRouter(prefix="/api/v1/history", tags=["history"])
_HASH = re.compile(r"^(bin:)?[0-9a-f]{64}$")


def _text(svc: Services, h: str | None) -> str | None:
    data = svc.history.get_blob(h)
    return None if data is None else (decode_text(data) or "")


def file_entry(svc: Services, path: str, before: str | None, after: str | None, context: int) -> dict:
    status = "added" if before is None else "deleted" if after is None else "modified"
    entry = {"path": path, "status": status, "before": before, "after": after, "added": 0, "removed": 0,
             "hunks": [], "note": ""}
    if (before or "").startswith(BINARY_PREFIX) or (after or "").startswith(BINARY_PREFIX):
        entry["note"] = "Binary file"
        return entry
    old = "" if before is None else _text(svc, before)
    new = "" if after is None else _text(svc, after)
    if old is None or new is None:
        entry["note"] = "This version's content was dropped to stay under the history size limit"
        return entry
    try:
        entry["hunks"], entry["added"], entry["removed"] = hunks(old, new, context)
    except ValueError:
        entry["note"] = "Too large to show as a diff"
    return entry


def _in_project(path: str, project: str) -> bool:
    """Is path inside the open folder ("" = everything)? Folders can be nested: "app/web"."""
    project = project.strip("/")
    return not project or path == project or path.startswith(project + "/")


@router.get("/changesets")
async def list_changesets(_: SessionDep, request: Request, before: int | None = None, limit: int = 50,
                          project: str = "") -> dict:
    svc = services(request)

    def run() -> list[dict]:
        out = []
        cursor = before
        while len(out) < limit:
            batch = svc.history.changesets(cursor, min(200, limit * 2))
            if not batch:
                break
            for cs in batch:
                paths = [p for p, _b, _a in svc.history.changeset_files(cs["id"])]
                if project and not any(_in_project(p, project) for p in paths):
                    continue
                if not paths:
                    continue
                cs["projects"] = sorted({project_of(p) for p in paths})
                cs["paths"] = paths[:8]
                cs["file_count"] = len(paths)
                out.append(cs)
                if len(out) >= limit:
                    break
            cursor = batch[-1]["id"]
        return out

    items = await run_in_threadpool(run)
    return {"changesets": items, "open": svc.recorder.open_changeset_info()}


_EAGER_DIFF_LIMIT = 12


def _deferred_file_entry(path: str, before: str | None, after: str | None) -> dict:
    status = "added" if before is None else ("deleted" if after is None else "modified")
    return {
        "path": path,
        "status": status,
        "before": before,
        "after": after,
        "added": 0,
        "removed": 0,
        "hunks": [],
        "note": "",
        "deferred": True,
    }


def _build_diff_entries(svc, pairs: list[tuple[str, str | None, str | None]], context: int, project: str) -> list[dict]:
    filtered = [(p, b, a) for p, b, a in pairs if _in_project(p, project)]
    out: list[dict] = []
    for idx, (p, b, a) in enumerate(filtered):
        if idx < _EAGER_DIFF_LIMIT:
            out.append(file_entry(svc, p, b, a, context))
        else:
            out.append(_deferred_file_entry(p, b, a))
    return out


@router.get("/changesets/{cs_id}")
async def get_changeset(cs_id: int, _: SessionDep, request: Request, context: int = 3, project: str = "") -> dict:
    svc = services(request)
    context = max(0, min(context, 100_000))

    def run() -> dict:
        info = svc.history.changeset(cs_id)
        if not info:
            raise HTTPException(404, "No such change set")
        files = _build_diff_entries(svc, svc.history.changeset_files(cs_id), context, project)
        return {**info, "files": files}

    return await run_in_threadpool(run)


@router.get("/range")
async def get_range(_: SessionDep, request: Request, since: float, until: float | None = None, context: int = 3,
                    project: str = "") -> dict:
    svc = services(request)
    context = max(0, min(context, 100_000))

    def run() -> dict:
        files = _build_diff_entries(svc, svc.history.range_files(since, until), context, project)
        return {"since": since, "until": until or time.time(), "files": files}

    return await run_in_threadpool(run)


@router.get("/filediff")
async def file_diff(path: str, _: SessionDep, request: Request, before: str = "", after: str = "",
                    context: int = 3) -> dict:
    """One file again with more context (the review's "show more lines")."""
    svc = services(request)
    for h in (before, after):
        if h and not _HASH.match(h):
            raise HTTPException(400, "Bad version")
    try:
        rel = clean_rel(path)
    except JailError as exc:
        raise HTTPException(400, str(exc))
    return await run_in_threadpool(file_entry, svc, rel, before or None, after or None, max(0, min(context, 100_000)))


@router.get("/file")
async def file_timeline(path: str, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    try:
        rel = clean_rel(path)
    except JailError as exc:
        raise HTTPException(400, str(exc))
    versions = await run_in_threadpool(svc.history.file_versions, rel)
    return {"path": rel, "versions": [{"id": v.id, "ts": v.ts, "before": v.before, "after": v.after,
                                       "changeset": v.changeset, "source": v.source} for v in versions]}


@router.get("/usage")
async def usage(_: SessionDep, request: Request) -> dict:
    return await run_in_threadpool(services(request).history.usage)


class PruneBody(BaseModel):
    cap_gb: float | None = Field(default=None, ge=0.0, le=500.0)


@router.post("/prune")
async def prune(body: PruneBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)

    def run() -> dict:
        if body.cap_gb is not None:
            freed = svc.history.set_cap(int(body.cap_gb * 1024 * 1024 * 1024))
        else:
            freed = svc.history.enforce_cap()
        return {"freed_bytes": freed, "usage": svc.history.usage()}

    return await run_in_threadpool(run)


class RestoreBody(BaseModel):
    changeset: int | None = None  # put every file of this change set back as it was before it
    path: str | None = Field(default=None, max_length=4096)  # or: one file ...
    state: str | None = Field(default=None, max_length=80)  # ... to this version hash ("" = delete it)


def _resolve_restore_targets(svc: Services, body: RestoreBody) -> tuple[list[tuple[str, str | None]], str]:
    if body.changeset is not None:
        if not svc.history.changeset(body.changeset):
            raise HTTPException(404, "No such change set")
        return [(p, b) for p, b, _a in svc.history.changeset_files(body.changeset)], f"Undo of change set #{body.changeset}"
    if body.path is not None and body.state is not None:
        if body.state and not _HASH.match(body.state):
            raise HTTPException(400, "Bad version")
        try:
            rel = clean_rel(body.path)
        except JailError as exc:
            raise HTTPException(400, str(exc))
        return [(rel, body.state or None)], f"Restored {rel}"
    raise HTTPException(400, "Say what to restore")


def _build_restore_plan(svc: Services, targets: list[tuple[str, str | None]]) -> list[tuple[str, str | None, bytes | None]]:
    plan: list[tuple[str, str | None, bytes | None]] = []
    for path, state in targets:
        if state and state.startswith(BINARY_PREFIX):
            raise HTTPException(409, f"{path} was a binary file; its content isn't kept")
        data = None if state is None else svc.history.get_blob(state)
        if state is not None and data is None:
            raise HTTPException(409, f"The old version of {path} is no longer stored")
        plan.append((path, state, data))
    return plan


def _apply_restore_plan(svc: Services, plan: list[tuple[str, str | None, bytes | None]], label: str) -> tuple[int, list[str]]:
    cs = svc.history.open_changeset("restore", label)
    done: list[str] = []
    try:
        for path, state, data in plan:
            if data is None:
                try:
                    svc.jail.delete(path)
                except JailError as exc:
                    if exc.status != 404:
                        raise
            else:
                svc.jail.write_file(path, data)
            svc.history.record(path, state, "restore", cs)
            done.append(path)
    except JailError as exc:
        raise HTTPException(exc.status, f"Restored {len(done)} of {len(plan)} files, then: {exc}")
    finally:
        svc.history.close_changeset(cs, "restore")
    return cs, done


@router.post("/restore")
async def restore(body: RestoreBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)

    def run() -> dict:
        targets, label = _resolve_restore_targets(svc, body)
        plan = _build_restore_plan(svc, targets)
        cs, done = _apply_restore_plan(svc, plan, label)
        svc.live.publish("changeset", {**(svc.history.changeset(cs) or {"id": cs}), "file_count": len(done)})
        return {"changeset": cs, "restored": done}

    return await run_in_threadpool(run)
