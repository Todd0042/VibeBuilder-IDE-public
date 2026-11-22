"""Sessions: in memory only, so a server restart signs everyone out.

A session ends when the app says so (closing the app, the lock button), when its device is revoked,
or when the app hasn't been heard from for 10 minutes (it pings every 2 minutes while open, so this
only catches apps that crashed, lost their connection or went to sleep). Anything holding a session
(WebSockets) registers a closer so it is cut off the moment the session ends.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Session:
    key: str  # sha256 of the token; the token itself is never stored
    device_id: str
    created: float
    last_activity: float
    closers: list[Callable[[], None]] = field(default_factory=list)


class SessionStore:
    def __init__(self, idle_sec: int):
        self.idle_sec = idle_sec
        self._by_key: dict[str, Session] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, device_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._by_key[self._key(token)] = Session(self._key(token), device_id, now, now)
        return token

    def get(self, token: str) -> Session | None:
        if not token or len(token) > 128:
            return None
        with self._lock:
            s = self._by_key.get(self._key(token))
        if s and self.idle_sec > 0 and time.time() - s.last_activity > self.idle_sec:
            self.end(s.key)
            return None
        return s

    def get_by_key(self, key: str) -> Session | None:
        with self._lock:
            return self._by_key.get(key)

    def activity(self, s: Session) -> None:
        s.last_activity = time.time()

    def remaining(self, s: Session) -> int:
        return max(0, int(self.idle_sec - (time.time() - s.last_activity)))

    def add_closer(self, s: Session, fn: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            s.closers.append(fn)

        def remove() -> None:
            with self._lock:
                if fn in s.closers:
                    s.closers.remove(fn)
        return remove

    def end(self, key: str) -> None:
        with self._lock:
            s = self._by_key.pop(key, None)
        if s:
            for fn in list(s.closers):
                try:
                    fn()
                except Exception:
                    pass

    def end_device(self, device_id: str) -> None:
        with self._lock:
            keys = [k for k, s in self._by_key.items() if s.device_id == device_id]
        for k in keys:
            self.end(k)

    def device_ids(self) -> set[str]:
        with self._lock:
            return {s.device_id for s in self._by_key.values()}

    def sweep(self) -> None:
        if self.idle_sec <= 0:
            return
        now = time.time()
        with self._lock:
            stale = [k for k, s in self._by_key.items() if now - s.last_activity > self.idle_sec]
        for k in stale:
            self.end(k)
