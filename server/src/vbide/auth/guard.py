"""Failed-attempt limits for pairing and login.

Per address: 5 failures lock that address out for 15 minutes. Across all addresses: 30 failures in
15 minutes lock pairing and login for everyone until the window passes, so spreading guesses over
many addresses doesn't help. Successful logins don't reset the global count.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class Guard:
    def __init__(self, max_per_ip: int, lockout_sec: int, max_global: int):
        self.max_per_ip = max_per_ip
        self.lockout_sec = lockout_sec
        self.max_global = max_global
        self._fails: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()
        self._lock = threading.Lock()

    def _trim(self, q: deque[float], now: float) -> None:
        while q and now - q[0] > self.lockout_sec:
            q.popleft()

    def blocked(self, ip: str) -> int:
        """Seconds until this address may try again (0 = allowed)."""
        now = time.time()
        with self._lock:
            self._trim(self._global, now)
            if len(self._global) >= self.max_global:
                return int(self.lockout_sec - (now - self._global[0])) + 1
            q = self._fails.get(ip)
            if q:
                self._trim(q, now)
                if len(q) >= self.max_per_ip:
                    return int(self.lockout_sec - (now - q[0])) + 1
        return 0

    def fail(self, ip: str) -> None:
        now = time.time()
        with self._lock:
            self._fails.setdefault(ip, deque()).append(now)
            self._global.append(now)
            if len(self._fails) > 10_000:  # don't grow forever under a spray
                for k in list(self._fails)[:5_000]:
                    del self._fails[k]

    def succeed(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)
