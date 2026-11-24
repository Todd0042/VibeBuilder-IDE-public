"""History storage.

Content is stored once per distinct version (named by its SHA-256, zstd-compressed) under
history/blobs. SQLite keeps:

  files       path -> its current version hash, and when it last changed
  versions    every recorded change: path, hash before, hash after, when, which change set, who
  changesets  one per burst of agent edits (closed after a few quiet seconds)

A hash of None means "the file doesn't exist" (created from nothing, or deleted). Binary files get a
"bin:" hash and no stored content: the review only shows that they changed.

The size cap is rolling: when stored content passes it, the files that have gone the longest without
changing lose their history first (their current version is always kept, as the baseline).
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from compression import zstd
from dataclasses import dataclass
from pathlib import Path

BINARY_PREFIX = "bin:"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Version:
    id: int
    path: str
    before: str | None
    after: str | None
    ts: float
    changeset: int | None
    source: str


class HistoryStore:
    def __init__(self, root: Path, cap_bytes: int):
        self.root = root
        self.blob_dir = root / "blobs"
        self.cap_bytes = cap_bytes
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._local = threading.local()
        with self._lock:
            db = self._db()
            db.executescript("""
            CREATE TABLE IF NOT EXISTS blobs (hash TEXT PRIMARY KEY, raw_size INTEGER NOT NULL,
                stored_size INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, hash TEXT, changed REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS changesets (id INTEGER PRIMARY KEY AUTOINCREMENT, started REAL NOT NULL,
                ended REAL NOT NULL, source TEXT NOT NULL DEFAULT 'unknown', label TEXT NOT NULL DEFAULT '',
                closed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL,
                before TEXT, after TEXT, ts REAL NOT NULL, changeset INTEGER, source TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS versions_path ON versions(path, ts);
            CREATE INDEX IF NOT EXISTS versions_cs ON versions(changeset);
            CREATE INDEX IF NOT EXISTS versions_ts ON versions(ts);
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
            """)

    def _db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(self.root / "history.sqlite3", timeout=10, isolation_level=None,
                                 check_same_thread=False)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            self._local.db = db
        return db

    # ---- blobs -----------------------------------------------------------------------------
    def _blob_path(self, h: str) -> Path:
        return self.blob_dir / h[:2] / h

    def put_blob(self, data: bytes) -> str:
        h = content_hash(data)
        db = self._db()
        if db.execute("SELECT 1 FROM blobs WHERE hash=?", (h,)).fetchone():
            return h
        packed = zstd.compress(data, level=6)
        p = self._blob_path(h)
        p.parent.mkdir(exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(packed)
        os.replace(tmp, p)
        db.execute("INSERT OR IGNORE INTO blobs (hash, raw_size, stored_size) VALUES (?,?,?)",
                   (h, len(data), len(packed)))
        return h

    def get_blob(self, h: str | None) -> bytes | None:
        """Content of a version; None for 'no file', binary, or content lost to the size cap."""
        if not h or h.startswith(BINARY_PREFIX):
            return None
        try:
            return zstd.decompress(self._blob_path(h).read_bytes())
        except (FileNotFoundError, zstd.ZstdError) as exc:
            logging.getLogger("vbide.history.store").debug("Blob unavailable for %s: %s", h, exc)
            return None

    # ---- files -----------------------------------------------------------------------------
    def meta(self, k: str) -> str | None:
        row = self._db().execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row[0] if row else None

    def set_meta(self, k: str, v: str) -> None:
        self._db().execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?,?)", (k, v))

    def current(self, path: str) -> str | None:
        row = self._db().execute("SELECT hash FROM files WHERE path=?", (path,)).fetchone()
        return row[0] if row else None

    def known_paths(self) -> dict[str, str | None]:
        return dict(self._db().execute("SELECT path, hash FROM files").fetchall())

    def set_baseline(self, path: str, h: str | None) -> None:
        """Remember a file's state without recording a change (first scan, your own saves)."""
        self._db().execute("INSERT INTO files (path, hash, changed) VALUES (?,?,?) "
                           "ON CONFLICT(path) DO UPDATE SET hash=excluded.hash, changed=excluded.changed",
                           (path, h, time.time()))

    # ---- recording -------------------------------------------------------------------------
    def open_changeset(self, source: str = "unknown", label: str = "") -> int:
        now = time.time()
        cur = self._db().execute("INSERT INTO changesets (started, ended, source, label) VALUES (?,?,?,?)",
                                 (now, now, source, label))
        return int(cur.lastrowid)

    def close_changeset(self, cs: int, source: str) -> None:
        db = self._db()
        if not db.execute("SELECT 1 FROM versions WHERE changeset=?", (cs,)).fetchone():
            db.execute("DELETE FROM changesets WHERE id=?", (cs,))  # everything turned out unchanged
            return
        db.execute("UPDATE changesets SET closed=1, source=? WHERE id=?", (source, cs))

    def record(self, path: str, after: str | None, source: str, changeset: int | None) -> Version | None:
        """Record path's new state. Returns None if it didn't actually change."""
        with self._lock:
            db = self._db()
            before = self.current(path)
            if before == after:
                return None
            now = time.time()
            cur = db.execute("INSERT INTO versions (path, before, after, ts, changeset, source) VALUES (?,?,?,?,?,?)",
                             (path, before, after, now, changeset, source))
            self.set_baseline(path, after)
            if changeset is not None:
                db.execute("UPDATE changesets SET ended=? WHERE id=?", (now, changeset))
            return Version(int(cur.lastrowid), path, before, after, now, changeset, source)

    # ---- reading ---------------------------------------------------------------------------
    def changesets(self, before_id: int | None, limit: int, include_own: bool = False) -> list[dict]:
        q = ("SELECT c.id, c.started, c.ended, c.source, c.label, c.closed, COUNT(DISTINCT v.path) "
             "FROM changesets c JOIN versions v ON v.changeset=c.id WHERE 1=1")
        args: list = []
        if before_id:
            q += " AND c.id < ?"
            args.append(before_id)
        if not include_own:
            q += " AND c.source != 'you'"
        q += " GROUP BY c.id ORDER BY c.id DESC LIMIT ?"
        args.append(limit)
        return [{"id": r[0], "started": r[1], "ended": r[2], "source": r[3], "label": r[4], "closed": bool(r[5]),
                 "file_count": r[6]} for r in self._db().execute(q, args).fetchall()]

    def changeset(self, cs: int) -> dict | None:
        r = self._db().execute("SELECT id, started, ended, source, label, closed FROM changesets WHERE id=?",
                               (cs,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "started": r[1], "ended": r[2], "source": r[3], "label": r[4], "closed": bool(r[5])}

    def changeset_files(self, cs: int) -> list[tuple[str, str | None, str | None]]:
        """(path, state before the change set, state after it) for each file it touched."""
        rows = self._db().execute(
            "SELECT path, before, after FROM versions WHERE changeset=? ORDER BY id", (cs,)).fetchall()
        first: dict[str, str | None] = {}
        last: dict[str, str | None] = {}
        for path, before, after in rows:
            first.setdefault(path, before)
            last[path] = after
        return [(p, first[p], last[p]) for p in first if first[p] != last[p]]

    def range_files(self, since: float, until: float | None = None) -> list[tuple[str, str | None, str | None]]:
        """Every file changed in [since, until]: its state before since -> its state at until."""
        until = until or time.time() + 1
        rows = self._db().execute(
            "SELECT path, before, after FROM versions WHERE ts>=? AND ts<=? AND source != 'baseline' ORDER BY id",
            (since, until)).fetchall()
        first: dict[str, str | None] = {}
        last: dict[str, str | None] = {}
        for path, before, after in rows:
            first.setdefault(path, before)
            last[path] = after
        return [(p, first[p], last[p]) for p in first if first[p] != last[p]]

    def file_versions(self, path: str, limit: int = 200) -> list[Version]:
        rows = self._db().execute(
            "SELECT id, path, before, after, ts, changeset, source FROM versions WHERE path=? "
            "ORDER BY id DESC LIMIT ?", (path, limit)).fetchall()
        return [Version(*r) for r in rows]

    def version(self, vid: int) -> Version | None:
        r = self._db().execute("SELECT id, path, before, after, ts, changeset, source FROM versions WHERE id=?",
                               (vid,)).fetchone()
        return Version(*r) if r else None

    def usage(self) -> dict:
        db = self._db()
        stored, raw, n = db.execute("SELECT COALESCE(SUM(stored_size),0), COALESCE(SUM(raw_size),0), COUNT(*) "
                                    "FROM blobs").fetchone()
        versions = db.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
        return {"stored_bytes": stored, "raw_bytes": raw, "blobs": n, "versions": versions, "cap_bytes": self.cap_bytes}

    # ---- the rolling cap -------------------------------------------------------------------
    def set_cap(self, cap_bytes: int) -> int:
        with self._lock:
            self.cap_bytes = max(0, int(cap_bytes))
            return self.enforce_cap()

    def enforce_cap(self, max_bytes: int | None = None) -> int:
        """Drop history of the longest-unchanged files until stored content fits. Returns bytes freed."""
        limit = self.cap_bytes if max_bytes is None else max(0, int(max_bytes))
        freed = 0
        with self._lock:
            db = self._db()
            while self.usage()["stored_bytes"] > limit:
                row = db.execute("SELECT f.path FROM files f WHERE EXISTS (SELECT 1 FROM versions v WHERE v.path=f.path) "
                                 "ORDER BY f.changed ASC LIMIT 1").fetchone()
                if not row:
                    break
                db.execute("DELETE FROM versions WHERE path=?", (row[0],))
                freed += self._collect_garbage()
            db.execute("DELETE FROM changesets WHERE closed=1 AND id NOT IN "
                       "(SELECT DISTINCT changeset FROM versions WHERE changeset IS NOT NULL)")
        return freed

    def _collect_garbage(self) -> int:
        db = self._db()
        dead = db.execute("""SELECT hash, stored_size FROM blobs WHERE hash NOT IN (
            SELECT hash FROM files WHERE hash IS NOT NULL UNION SELECT before FROM versions WHERE before IS NOT NULL
            UNION SELECT after FROM versions WHERE after IS NOT NULL)""").fetchall()
        freed = 0
        for h, size in dead:
            self._blob_path(h).unlink(missing_ok=True)
            db.execute("DELETE FROM blobs WHERE hash=?", (h,))
            freed += size
        return freed
