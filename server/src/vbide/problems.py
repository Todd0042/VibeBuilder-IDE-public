"""Problems the server runs into in the background, reported to whoever runs it instead of being swallowed.

Each problem is logged in full (the journal: `vibebuilder logs`), kept in a short list the app shows (the ⚠ in the
status bar), and pushed to open apps as a live "problem" event. The same problem (same key) is counted, not repeated:
apps are told again only when it comes back after 6 hours. Anything that looks like a secret is masked first.

  GET    /api/v1/problems            the current list, newest first
  DELETE /api/v1/problems/{key}      dismiss one; it comes back if it happens again (keys can contain "/")
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request

from .auth.routes import SessionDep
from .services import services

if TYPE_CHECKING:
    from .live import LiveHub

log = logging.getLogger("vbide.problems")
router = APIRouter(prefix="/api/v1", tags=["problems"])
MAX_ITEMS = 50
RENOTIFY_SEC = 6 * 3600
_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    r"|(?:gh[pousr]_|github_pat_|hf_|sk-(?:ant-)?|sk_live_|xox[abpr]-|AKIA|AIza|ya29\.|GOCSPX-)[A-Za-z0-9_\-.]{8,}"
    r"|(?i:(?:password|passwd|pwd|secret|token|api[_-]?key|authorization)\s*[=:]\s*)\S+"
    r"|(?<=://)[^/\s:@]+:[^/\s@]+(?=@)")


def mask(text: str) -> str:
    """Hide anything secret-looking (tokens, keys, passwords in URLs or key=value pairs), keeping a short hint."""
    def hide(m: re.Match) -> str:
        s = m.group(0)
        if s.startswith("-----BEGIN"):
            return "[private key hidden]"
        named = re.match(r"(?i)^(?:password|passwd|pwd|secret|token|api[_-]?key|authorization)\s*[=:]\s*", s)
        if named:
            return named.group(0) + "…"  # keep "password=", hide the value
        return s[:4] + "…" if len(s) > 12 else "…"  # a token or URL credentials: a hint of which one, no more
    return _SECRET.sub(hide, text)


class Problems:
    def __init__(self, live: "LiveHub"):
        self.live = live
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}

    def report(self, key: str, message: str, detail: str = "", fix: str = "") -> None:
        """Called from any thread. `message` says what went wrong in plain words, `detail` the technical reason
        (error text, path), `fix` what to do about it."""
        key = mask(key)[:300]  # keys can hold paths too; masking is deterministic, so repeats still match
        message, detail, fix = mask(message)[:300], mask(detail)[:2000], mask(fix)[:500]
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            notify = item is None or now - item["notified"] >= RENOTIFY_SEC
            if item is None:
                item = self._items[key] = {"key": key, "first": now, "count": 0, "notified": 0.0}
            item.update(message=message, detail=detail, fix=fix, last=now, count=item["count"] + 1)
            if notify:
                item["notified"] = now
            if len(self._items) > MAX_ITEMS:
                oldest = min(self._items.values(), key=lambda i: i["last"])
                self._items.pop(oldest["key"], None)
            public = self._public(item)
        if notify:  # the full detail goes to the log every time it's new; repeats are only counted
            log.warning("%s: %s%s", key, message, f" ({detail})" if detail else "")
            self.live.publish("problem", public)

    def list(self) -> list[dict]:
        with self._lock:
            return [self._public(i) for i in sorted(self._items.values(), key=lambda i: -i["last"])]

    def dismiss(self, key: str) -> bool:
        with self._lock:
            return self._items.pop(key, None) is not None

    @staticmethod
    def _public(i: dict) -> dict:
        return {k: i[k] for k in ("key", "message", "detail", "fix", "first", "last", "count")}


@router.get("/problems")
def list_problems(_: SessionDep, request: Request) -> dict:
    return {"problems": services(request).problems.list()}


@router.delete("/problems/{key:path}")
def dismiss_problem(key: str, _: SessionDep, request: Request) -> dict:
    if len(key) > 300:
        raise HTTPException(400, "Bad key")
    return {"dismissed": services(request).problems.dismiss(key)}
