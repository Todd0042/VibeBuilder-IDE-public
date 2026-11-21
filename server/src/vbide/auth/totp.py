"""Authenticator codes: only the current 30-second code is accepted, and each one only once.

Most servers also accept the previous and next code (about 90 s in practice); this one doesn't. A code
that was used, or seen over someone's shoulder, can't be replayed: the last accepted time step is kept
and anything at or before it is refused.
"""

from __future__ import annotations

import hmac
import threading
import time

import pyotp


class Totp:
    def __init__(self, secret: str):
        if not secret:
            raise RuntimeError("No authenticator secret configured (data/secrets/totp_secret)")
        self._totp = pyotp.TOTP(secret)  # 6 digits, 30 s, SHA-1: what authenticator apps expect
        self._last_step = -1
        self._lock = threading.Lock()

    def verify(self, code: str, now: float | None = None) -> bool:
        code = (code or "").strip().replace(" ", "")
        if len(code) != 6 or not code.isdigit():
            return False
        now = time.time() if now is None else now
        step = int(now // 30)
        expected = self._totp.at(step * 30)
        if not hmac.compare_digest(expected, code):
            return False
        with self._lock:
            if step <= self._last_step:
                return False  # this code was already used
            self._last_step = step
        return True

    def provisioning_uri(self, account: str, issuer: str) -> str:
        return self._totp.provisioning_uri(name=account, issuer_name=issuer)
