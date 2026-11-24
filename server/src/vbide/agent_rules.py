"""Starter agent rules: a project gets templates/AGENTS.md (plus a CLAUDE.md that points Claude Code
at it) the first time it's opened, if it has no agent rules of its own. agy reads AGENTS.md itself.

Only once per project: if the owner deletes the files, they stay deleted (data/agent_rules.json
remembers which projects were given them).

  POST /api/v1/agent-rules   {project} -> {created: [paths]}   (the app calls it when a project opens)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from importlib.resources import files as package_files

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .auth.routes import SessionDep
from .jail import JailError, clean_rel
from .services import services

router = APIRouter(prefix="/api/v1", tags=["agent-rules"])
# Any of these means the project already has rules: leave it alone.
EXISTING = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".claude/CLAUDE.md", "CLAUDE.local.md", ".agents/rules",
            ".cursorrules", ".github/copilot-instructions.md")
CLAUDE_MD = b"# Claude Code reads its rules from AGENTS.md (shared with other agents).\n\n@AGENTS.md\n"
_lock = threading.Lock()


class Ask(BaseModel):
    project: str = Field(max_length=500)


@router.post("/agent-rules")
def ensure_agent_rules(body: Ask, _: SessionDep, request: Request) -> dict:
    svc = services(request)
    try:
        project = clean_rel(body.project)
        if not project or "/" in project:
            raise HTTPException(400, "Pick a project")
        svc.jail.stat(project)
    except JailError as exc:
        raise HTTPException(exc.status, str(exc))
    with _lock:
        given = _given(svc.settings.agent_rules_file)
        if project in given:
            return {"created": []}
        given.add(project)
        if any(_exists(svc, f"{project}/{name}") for name in EXISTING):
            _save(svc.settings.agent_rules_file, given)
            return {"created": []}
        created, failed = [], []
        rules = package_files("vbide").joinpath("templates/AGENTS.md").read_bytes()
        for name, data in (("AGENTS.md", rules), ("CLAUDE.md", CLAUDE_MD)):
            rel = f"{project}/{name}"
            try:
                svc.recorder.expect_own_write(rel, data)  # yours, not an agent's, in the change history
                svc.jail.write_file(rel, data)
                created.append(rel)
            except (JailError, OSError) as exc:
                failed.append({"path": rel, "reason": str(exc)[:200]})
        if failed:
            given.discard(project)  # try again next time the project is opened
        _save(svc.settings.agent_rules_file, given)
    if created:
        svc.live.publish("fs", {"paths": created})
    return {"created": created, "failed": failed}


def _exists(svc, rel: str) -> bool:
    try:
        svc.jail.stat(rel)
        return True
    except JailError as exc:
        logging.getLogger("vbide.agent_rules").debug("Agent rule file absent (%s): %s", rel, exc)
        return False


def _given(path) -> set[str]:
    """Projects that were given the rules. If the file can't be read it's kept aside and treated as empty, which can
    only mean a project without rules gets them offered once more."""
    if not path.exists():
        return set()
    try:
        return {p for p in json.loads(path.read_text()) if isinstance(p, str)}
    except (OSError, ValueError, TypeError) as exc:
        logging.getLogger("vbide.agent_rules").warning("Unreadable %s (%s); kept as %s.unreadable", path, exc, path.name)
        try:
            os.replace(path, path.with_name(path.name + ".unreadable"))
        except OSError as move_exc:
            logging.getLogger("vbide.agent_rules").debug("Could not move %s aside: %s", path, move_exc)
        return set()


def _save(path, given: set[str]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(given)))
    os.replace(tmp, path)
