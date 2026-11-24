"""/api/v1/search (Ctrl+Shift+F) and /api/v1/fs/files (Ctrl+P quick open), both with ripgrep.

ripgrep starts in a jailed folder fd (never a path string), doesn't follow symlinks, reads no config
file, and is capped on matches, file size, line length and time. It executes nothing from the
workspace, so it is safe to run here even though agents control the files.
"""

from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .auth.routes import SessionDep
from .jail import JailError, clean_rel
from .services import services

router = APIRouter(prefix="/api/v1", tags=["search"])

MAX_MATCHES = 2000
MAX_FILES_LISTED = 60_000
TIMEOUT_SEC = 15
_BASE = ["rg", "--no-config", "--no-follow", "--hidden", "--glob", "!.git", "--max-filesize", "4M"]


async def _rg(svc, root: str, args: list[str], errors: bool = False):
    """ripgrep in `root` (through the jail). With errors=True its stderr is a pipe: per-file errors such as
    "Permission denied" (the caller must read it alongside stdout)."""
    try:
        fd = svc.jail.fchdir_to(root)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    try:
        proc = await asyncio.create_subprocess_exec(
            *_BASE, *args, cwd=f"/proc/self/fd/{fd}", pass_fds=(fd,),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE if errors else asyncio.subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin"), "LANG": "C.UTF-8"})
    finally:
        os.close(fd)
    return proc


def _u16(s: str, i: int) -> int:
    """Python index -> JavaScript (UTF-16) index."""
    return len(s[:i].encode("utf-16-le")) // 2


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    root: str = Field(default="", max_length=4096)
    regex: bool = False
    case_sensitive: bool = False
    whole_word: bool = False
    include: str = Field(default="", max_length=1000)  # comma-separated globs
    exclude: str = Field(default="", max_length=1000)
    use_ignore_files: bool = True


def _build_rg_args(body: SearchBody) -> list[str]:
    args = ["--json", "--max-columns", "400", "--max-columns-preview", "--max-count", "300"]
    args += [] if body.regex else ["--fixed-strings"]
    args += ["--case-sensitive"] if body.case_sensitive else ["--ignore-case"]
    args += ["--word-regexp"] if body.whole_word else []
    args += [] if body.use_ignore_files else ["--no-ignore"]
    for g in (x.strip() for x in body.include.split(",")):
        if g:
            args += ["--glob", g]
    for g in (x.strip() for x in body.exclude.split(",")):
        if g:
            args += ["--glob", "!" + g.lstrip("!")]
    args += ["--regexp", body.query, "--", "."]
    return args


def _submatch_ranges(text: str, submatches: list[dict]) -> list[list[int]]:
    raw_bytes = text.encode()
    ranges: list[list[int]] = []
    for sm in submatches:
        a = len(raw_bytes[:sm["start"]].decode(errors="ignore"))
        b = len(raw_bytes[:sm["end"]].decode(errors="ignore"))
        ranges.append([_u16(text, a), _u16(text, b)])
    return ranges


@router.post("/search")
async def search(body: SearchBody, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    try:
        root = clean_rel(body.root)
    except JailError as exc:
        raise HTTPException(400, str(exc))
    proc = await _rg(svc, root, _build_rg_args(body), errors=True)
    files: dict[str, dict] = {}
    count, truncated, not_text = 0, False, 0
    skipped: list[dict] = []
    skipped_count = 0

    async def read_errors() -> None:
        """Files ripgrep couldn't search ("rg: ./path: Permission denied (os error 13)"): reported, not dropped."""
        nonlocal skipped_count
        assert proc.stderr
        async for raw in proc.stderr:
            line = raw.decode(errors="replace").strip()
            line = line[4:] if line.startswith("rg: ") else line
            path, _, reason = line.partition(": ")
            if not reason:
                continue
            skipped_count += 1
            if len(skipped) < 20:
                path = path[2:] if path.startswith("./") else path
                skipped.append({"path": (root + "/" + path) if root else path, "reason": reason[:200]})

    async def read() -> None:
        nonlocal count, truncated, not_text
        assert proc.stdout
        async for raw in proc.stdout:
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if ev.get("type") != "match":
                continue
            d = ev["data"]
            path, text = d["path"].get("text"), d["lines"].get("text")
            if path is None or text is None:
                not_text += 1
                continue
            path = path[2:] if path.startswith("./") else path
            text = text.rstrip("\n")
            f = files.setdefault(path, {"path": (root + "/" + path) if root else path, "matches": []})
            f["matches"].append({"line": d["line_number"], "text": text, "ranges": _submatch_ranges(text, d.get("submatches", []))})
            count += 1
            if count >= MAX_MATCHES:
                truncated = True
                return

    errs = asyncio.ensure_future(read_errors())
    try:
        await asyncio.wait_for(read(), TIMEOUT_SEC)
    except TimeoutError:
        truncated = True
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        try:
            await asyncio.wait_for(errs, 2)
        except TimeoutError:
            errs.cancel()  # the pipe closed with the process; only a stuck reader ends up here
    if proc.returncode == 2 and not files and not truncated and not skipped_count:
        raise HTTPException(400, "Search failed (check the regular expression)")
    return {"files": list(files.values()), "match_count": count, "truncated": truncated,
            "skipped": skipped, "skipped_count": skipped_count, "not_text_matches": not_text}


@router.get("/fs/files")
async def all_files(root: str, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    try:
        root = clean_rel(root)
    except JailError as exc:
        raise HTTPException(400, str(exc))
    proc = await _rg(svc, root, ["--files", "."])
    out: list[str] = []
    timed_out = False
    try:
        async def read() -> None:
            assert proc.stdout
            async for raw in proc.stdout:
                p = raw.decode(errors="replace").rstrip("\n")
                out.append(p[2:] if p.startswith("./") else p)
                if len(out) >= MAX_FILES_LISTED:
                    return
        await asyncio.wait_for(read(), TIMEOUT_SEC)
    except TimeoutError:
        timed_out = True  # the list is incomplete: said so below
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    out.sort()
    return {"root": root, "files": out, "truncated": timed_out or len(out) >= MAX_FILES_LISTED}
