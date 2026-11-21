"""Paired devices and pairing codes.

A device holds a long random token (in its keychain); only its SHA-256 is stored here. Pairing needs a
short one-time code that `vbide pair` shows on the desktop: it lives 30 seconds, works once, and only
its hash is written (to data/pairing/current), so the running server and the CLI can share it without
the code itself ever touching the disk.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

PAIR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_pair_code(code: str) -> str:
    return "".join(c for c in (code or "").upper() if c.isalnum())


def format_pair_code(code: str) -> str:
    return f"{code[:3]}-{code[3:]}"


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    created: float
    last_seen: float
    last_ip: str


class DeviceStore:
    def __init__(self, db_path: Path, pair_dir: Path, max_devices: int, pair_ttl: int):
        self.db_path = db_path
        self.pair_dir = pair_dir
        self.max_devices = max_devices
        self.pair_ttl = pair_ttl
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        pair_dir.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
                created REAL NOT NULL, last_seen REAL NOT NULL, last_ip TEXT NOT NULL DEFAULT '')""")

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    # ---- devices ---------------------------------------------------------------------------
    def list(self) -> list[Device]:
        with self._db() as db:
            rows = db.execute("SELECT id, name, created, last_seen, last_ip FROM devices ORDER BY created").fetchall()
        return [Device(*r) for r in rows]

    def find_by_token(self, token: str) -> Device | None:
        if not token or len(token) > 256:
            return None
        th = _h(token)
        with self._db() as db:
            row = db.execute("SELECT id, name, created, last_seen, last_ip, token_hash FROM devices WHERE token_hash=?",
                             (th,)).fetchone()
        if not row or not hmac.compare_digest(row[5], th):
            return None
        return Device(*row[:5])

    def exists(self, device_id: str) -> bool:
        with self._db() as db:
            return db.execute("SELECT 1 FROM devices WHERE id=?", (device_id,)).fetchone() is not None

    def touch(self, device_id: str, ip: str) -> None:
        with self._db() as db:
            db.execute("UPDATE devices SET last_seen=?, last_ip=? WHERE id=?", (time.time(), ip[:64], device_id))

    def revoke(self, device_id: str) -> bool:
        with self._db() as db:
            return db.execute("DELETE FROM devices WHERE id=?", (device_id,)).rowcount > 0

    def rename(self, device_id: str, name: str) -> bool:
        with self._db() as db:
            return db.execute("UPDATE devices SET name=? WHERE id=?", (_clean_name(name), device_id)).rowcount > 0

    # ---- pairing ---------------------------------------------------------------------------
    @property
    def _pair_file(self) -> Path:
        return self.pair_dir / "current"

    def new_pair_code(self) -> tuple[str, float]:
        """Called by the CLI. Returns (code, expires_at) and publishes only its hash."""
        code = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(6))
        expires = time.time() + self.pair_ttl
        tmp = self._pair_file.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"hash": _h(code), "expires": expires}, f)
        os.replace(tmp, self._pair_file)
        return code, expires

    def clear_pair_code(self) -> None:
        self._pair_file.unlink(missing_ok=True)

    def redeem_pair_code(self, code: str, device_name: str, ip: str) -> tuple[Device, str] | None:
        """Single use: the code is consumed on success. Returns (device, token) or None."""
        code = normalize_pair_code(code)
        if len(code) != 6:
            return None
        with self._lock:
            try:
                cur = json.loads(self._pair_file.read_text())
            except (FileNotFoundError, ValueError):
                return None
            if time.time() > float(cur.get("expires", 0)) or not hmac.compare_digest(str(cur.get("hash")), _h(code)):
                return None
            self.clear_pair_code()
            if len(self.list()) >= self.max_devices:
                raise DeviceLimit(self.max_devices)
            token = secrets.token_urlsafe(48)
            dev = Device(secrets.token_hex(8), _clean_name(device_name), time.time(), time.time(), ip[:64])
            with self._db() as db:
                db.execute("INSERT INTO devices (id, name, token_hash, created, last_seen, last_ip) VALUES (?,?,?,?,?,?)",
                           (dev.id, dev.name, _h(token), dev.created, dev.last_seen, dev.last_ip))
            return dev, token


class DeviceLimit(Exception):
    def __init__(self, limit: int):
        super().__init__(f"Already {limit} devices paired. Remove one first (Devices, or `vibebuilder devices`).")


def _clean_name(name: str) -> str:
    name = "".join(c for c in (name or "") if c.isprintable()).strip()[:60]
    return name or "Device"
