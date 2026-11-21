"""Automatic checkpoint commits (the git work itself runs in the builder: see builder/agent/vbagent/checkpoints.py).

Every recorded change (an agent's change set closing, or a save from the editor) marks its folder as
touched. Once a project has been quiet for `delay` seconds (3 minutes, like auto-save), the builder
commits a checkpoint of each repo those folders belong to, on the side branch checkpoints/<branch>.

Checkpoints are on by default, per project (a top-level workspace folder); the switch and the last
result are kept in data/checkpoints.json.

  GET  /api/v1/checkpoints?project=     {enabled, delay_sec, pending, last}
  PUT  /api/v1/checkpoints              {project, enabled}
  POST /api/v1/checkpoints/now          {project}: checkpoint now, without waiting
"""

from __future__ import annotations

import asyncio
import json
import os
import posixpath
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .auth.routes import SessionDep
from .jail import JailError, clean_rel
from .services import services

if TYPE_CHECKING:
    from .agent_link import AgentLink
    from .live import LiveHub
    from .problems import Problems

router = APIRouter(prefix="/api/v1", tags=["checkpoints"])
_STATUSES = ("committed", "unchanged", "skipped", "failed")


def project_of(path: str) -> str:
    return path.split("/", 1)[0]


class Checkpointer:
    def __init__(self, agent: "AgentLink", live: "LiveHub", state_file: Path, delay_sec: float,
                 problems: "Problems | None" = None):
        self.agent = agent
        self.live = live
        self.problems = problems
        self.state_file = state_file
        self.delay_sec = delay_sec
        self._lock = threading.Lock()
        self._touched: dict[str, dict[str, Any]] = {}  # project -> {"at": last change, "folders": {}, "who": {}}
        self._state = self._load()

    # ---- called from the recorder thread ----------------------------------------------------
    def touched(self, path: str, who: str) -> None:
        project = project_of(path)
        if not project or not self.enabled(project):
            return
        with self._lock:
            t = self._touched.setdefault(project, {"at": 0.0, "folders": {}, "who": {}})
            t["at"] = time.time()
            if len(t["folders"]) < 200:
                t["folders"][posixpath.dirname(path) or project] = None
            t["who"][who] = None

    # ---- settings ---------------------------------------------------------------------------
    def enabled(self, project: str) -> bool:
        return project not in self._state["off"]

    def set_enabled(self, project: str, on: bool) -> None:
        with self._lock:
            off = set(self._state["off"])
            (off.discard if on else off.add)(project)
            self._state["off"] = sorted(off)
            if not on:
                self._touched.pop(project, None)
            self._save()

    def info(self, project: str) -> dict:
        with self._lock:
            pending = self._touched.get(project)
            return {"enabled": self.enabled(project), "delay_sec": self.delay_sec,
                    "pending_since": pending["at"] if pending else None, "last": self._state["last"].get(project)}

    # ---- the loop ---------------------------------------------------------------------------
    async def run(self) -> None:
        while True:
            await asyncio.sleep(2)
            now = time.time()
            with self._lock:
                due = [p for p, t in self._touched.items() if now - t["at"] >= self.delay_sec]
            for project in due:
                await self.checkpoint(project)

    async def checkpoint(self, project: str, folders: list[str] | None = None) -> dict:
        with self._lock:
            t = self._touched.pop(project, None)
        body = {"folders": folders or (list(t["folders"]) if t else [project]), "who": list(t["who"]) if t else ["you"]}
        try:
            data = await self.agent.post("/git/checkpoint", body, timeout=300)
            results = [r for r in (_clean(x) for x in (data.get("results") or [])[:20]) if r]
        except Exception as exc:  # the builder is down or slow: try again after the next change
            results = [{"repo": project, "status": "failed", "reason": str(getattr(exc, "detail", exc))[:300]}]
        summary = {"at": time.time(), "results": results}
        with self._lock:
            self._state["last"][project] = summary
            self._save()
        self.live.publish("checkpoint", {"project": project, **summary})
        return summary

    # ---- state file -------------------------------------------------------------------------
    def _load(self) -> dict:
        if not self.state_file.exists():
            return {"off": [], "last": {}}  # first run
        try:
            s = json.loads(self.state_file.read_text())
            return {"off": [p for p in s.get("off", []) if isinstance(p, str)],
                    "last": {k: v for k, v in (s.get("last") or {}).items() if isinstance(k, str) and isinstance(v, dict)}}
        except (OSError, ValueError, AttributeError) as exc:
            # Unreadable: keep a copy for whoever wants to look, start from the defaults (checkpoints on everywhere).
            kept = self.state_file.with_name(f"{self.state_file.name}.unreadable-{int(time.time())}")
            try:
                os.replace(self.state_file, kept)
            except OSError:
                kept = self.state_file
            if self.problems:
                self.problems.report("checkpoints-settings", "The checkpoint settings couldn't be read, so every project "
                                     "is back to checkpoints on.", f"{type(exc).__name__}: {exc}; the file was kept as {kept.name}",
                                     "Turn checkpoints off again for any project that had them off (Devices view).")
            return {"off": [], "last": {}}

    def _save(self) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state))
        os.replace(tmp, self.state_file)


def _clean(r: Any) -> dict | None:
    """The builder's answer is untrusted: keep known fields, checked and capped."""
    if not isinstance(r, dict) or r.get("status") not in _STATUSES:
        return None
    out: dict[str, Any] = {"status": r["status"]}
    for key, cap in (("repo", 500), ("branch", 200), ("ref", 220), ("title", 200), ("reason", 300)):
        if isinstance(r.get(key), str):
            out[key] = r[key][:cap]
    if isinstance(r.get("commit"), str) and r["commit"].isalnum() and len(r["commit"]) <= 64:
        out["commit"] = r["commit"]
    if isinstance(r.get("files"), int):
        out["files"] = r["files"]
    out["rolled"] = bool(r.get("rolled"))
    out["left_out"] = [{"path": str(x.get("path"))[:500], "reason": str(x.get("reason"))[:100]}
                       for x in (r.get("left_out") or [])[:50] if isinstance(x, dict)]
    return out


# ---- routes ----------------------------------------------------------------------------------
def _project(request: Request, project: str) -> str:
    try:
        p = clean_rel(project)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    if not p or "/" in p or not (services(request).settings.workspace / p).is_dir():
        raise HTTPException(400, "Pick a project")
    return p


@router.get("/checkpoints")
def get_checkpoints(project: str, _: SessionDep, request: Request) -> dict:
    return services(request).checkpoints.info(_project(request, project))


class Toggle(BaseModel):
    project: str = Field(max_length=500)
    enabled: bool


@router.put("/checkpoints")
def put_checkpoints(body: Toggle, _: SessionDep, request: Request) -> dict:
    cp = services(request).checkpoints
    project = _project(request, body.project)
    cp.set_enabled(project, body.enabled)
    return cp.info(project)


class Now(BaseModel):
    project: str = Field(max_length=500)


@router.post("/checkpoints/now")
async def checkpoint_now(body: Now, _: SessionDep, request: Request) -> dict:
    cp = services(request).checkpoints
    project = _project(request, body.project)
    if not cp.enabled(project):
        raise HTTPException(409, "Checkpoints are off for this project")
    return await cp.checkpoint(project)
