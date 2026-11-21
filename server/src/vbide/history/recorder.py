"""Watches /workspace and records agent edits into change sets.

How a change set happens:
  - inotify reports a file write; the file is snapshotted once it has been quiet for ~2 s (so an agent
    writing a file in pieces is one version, not twenty);
  - the first changed file opens a change set; it closes when nothing has changed for ~5 s, and is then
    labelled with who made it (the builder says which terminal was busy; Claude's edit hook is exact);
  - saves from the editor are expected (expect_own_write) and only update the baseline, so the
    Changes list shows the agents' work, not yours.

Watches are added through jailed folder fds (/proc/self/fd/N), so a symlink can't make us watch
something outside the workspace; contents are read through the Jail too.
"""

from __future__ import annotations

import errno
import os
import stat as st
import threading
import time
from collections.abc import Callable
from pathlib import PurePosixPath

from inotify_simple import INotify, flags as F

from ..jail import Jail, JailError
from .store import BINARY_PREFIX, HistoryStore, content_hash

# Folders that are build output or caches: never watched, never recorded.
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "target", "build", "dist", "out", ".gradle",
    ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache", ".idea", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".direnv", "result", ".vibebuilder", "coverage", ".parcel-cache", ".expo",
    "cmake-build-debug", "cmake-build-release", ".cargo", ".go", ".npm", ".cxx", ".externalNativeBuild",
}
SKIP_SUFFIXES = (".tmp", ".swp", ".swx", "~", ".lock", ".pyc", ".o", ".obj", ".so", ".dll", ".a", ".class")
WATCH_FLAGS = (F.CLOSE_WRITE | F.MOVED_TO | F.MOVED_FROM | F.CREATE | F.DELETE | F.DELETE_SELF | F.MOVE_SELF
               | F.ONLYDIR)


def skip_name(name: str) -> bool:
    return name in SKIP_DIRS or name.endswith(SKIP_SUFFIXES) or (name.startswith(".") and name.endswith(".tmp"))


class Recorder:
    def __init__(self, jail: Jail, store: HistoryStore, *, settle_sec: float, quiet_sec: float, max_file_bytes: int,
                 attribute: Callable[[float, float, list[str]], str], emit: Callable[[str, dict], None],
                 changed: Callable[[str, str], None] = lambda path, who: None,
                 problem: Callable[..., None] = lambda key, message, detail="", fix="": None):
        self.jail = jail
        self.store = store
        self.settle_sec = settle_sec
        self.quiet_sec = quiet_sec
        self.max_file_bytes = max_file_bytes
        self.attribute = attribute  # (started, ended, paths) -> "claude" | "agy" | "shell" | "unknown"
        self.emit = emit  # (event, payload) -> live update to the apps
        self.changed = changed  # (path, who) after each recorded change: checkpoints follow these
        self.problem = problem  # (key, message, detail, fix): reported to whoever runs the IDE (problems.py)
        self._inotify = INotify()
        self._wd: dict[int, str] = {}  # watch descriptor -> folder (relative)
        self._pending: dict[str, float] = {}  # path -> last event time
        self._expected: dict[str, tuple[str, float]] = {}  # path -> (hash of our own save, when)
        self._cs: int | None = None
        self._cs_started = 0.0
        self._cs_last = 0.0
        self._cs_paths: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    # ---- public ----------------------------------------------------------------------------
    def start(self) -> None:
        for target in (self._scan_then_watch, self._tick):
            t = threading.Thread(target=target, daemon=True, name=f"history-{target.__name__}")
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()

    def expect_own_write(self, path: str, data: bytes) -> None:
        with self._lock:
            self._expected[path] = (self._hash(data), time.time())

    def open_changeset_info(self) -> dict | None:
        with self._lock:
            if self._cs is None:
                return None
            return {"id": self._cs, "started": self._cs_started, "files": len(set(self._cs_paths))}

    # ---- scanning --------------------------------------------------------------------------
    def _hash(self, data: bytes) -> str:
        return BINARY_PREFIX + content_hash(data) if b"\x00" in data[:8192] else content_hash(data)

    def _add_watch(self, rel: str) -> None:
        try:
            fd = self.jail.fchdir_to(rel)
        except JailError:
            return
        try:
            wd = self._inotify.add_watch(f"/proc/self/fd/{fd}", WATCH_FLAGS)
            self._wd[wd] = rel
        except OSError as exc:
            if exc.errno == errno.ENOSPC:  # the system's limit on watched folders
                self.problem("history-watch-limit", "Change history stopped following new folders: the system's limit on "
                             "watched folders is reached, so agent edits in them aren't recorded.",
                             f"inotify add_watch failed for {rel or '/'}: {exc.strerror}",
                             "On the desktop: echo fs.inotify.max_user_watches=1048576 | sudo tee /etc/sysctl.d/90-vibebuilder.conf "
                             "&& sudo sysctl --system, then vibebuilder restart")
            elif exc.errno not in (errno.ENOENT, errno.ENOTDIR):  # gone already: nothing to watch
                self.problem(f"history-watch:{rel}", f"Change history can't follow the folder {rel or '/'}",
                             f"inotify add_watch: {exc.strerror}")
        finally:
            os.close(fd)

    def _walk(self, rel: str, files: dict[str, None], watch: bool) -> None:
        if watch:
            self._add_watch(rel)
        try:
            entries = self.jail.list_dir(rel)
        except (JailError, OSError):
            return
        for e in entries:
            if skip_name(e.name):
                continue
            child = f"{rel}/{e.name}" if rel else e.name
            if e.kind == "dir":
                self._walk(child, files, watch)
            elif e.kind == "file":
                files[child] = None

    def _scan_then_watch(self) -> None:
        """First run: remember every file as the baseline. Later runs: anything that changed while the
        server was down becomes one 'while offline' change set. Then follow inotify events."""
        found: dict[str, None] = {}
        self._walk("", found, watch=True)
        first_run = self.store.meta("scanned") is None
        known = self.store.known_paths()
        offline_cs = None
        for path in found:
            h = self._snapshot(path)
            if h is False:
                continue
            if first_run or path not in known:
                if first_run:
                    self.store.set_baseline(path, h)
                    continue
            if known.get(path) != h:
                offline_cs = offline_cs or self.store.open_changeset("offline", "Changed while the IDE server was off")
                self.store.record(path, h, "offline", offline_cs)
        if not first_run:
            for path, h in known.items():
                if h is not None and path not in found:
                    offline_cs = offline_cs or self.store.open_changeset("offline", "Changed while the IDE server was off")
                    self.store.record(path, None, "offline", offline_cs)
        if offline_cs:
            self.store.close_changeset(offline_cs, "offline")
        self.store.set_meta("scanned", str(time.time()))
        self._follow()

    def _snapshot(self, path: str) -> str | None | bool:
        """Store the file's current content. Returns its hash, None if it's gone, False to ignore it."""
        try:
            data, s = self.jail.read_file(path, self.max_file_bytes)
        except JailError as exc:
            if exc.denied:
                self.problem(f"history-record:{path}", f"Change history couldn't read {path}, so its changes aren't recorded",
                             f"PermissionError: {exc}", "Check the file's permissions (ls -l).")
            return None if exc.status == 404 else False  # gone, or deliberately not recorded (symlink, too large)
        except OSError as exc:
            self.problem(f"history-record:{path}", f"Change history couldn't read {path}, so its changes aren't recorded",
                         f"{type(exc).__name__}: {exc.strerror or exc}", "Check the file's permissions (ls -l).")
            return False
        if not st.S_ISREG(s.st_mode):
            return False
        if b"\x00" in data[:8192]:
            return BINARY_PREFIX + content_hash(data)
        return self.store.put_blob(data)

    # ---- following -------------------------------------------------------------------------
    def _follow(self) -> None:
        while not self._stop.is_set():
            try:
                events = self._inotify.read(timeout=500)
            except OSError:
                continue
            now = time.time()
            changed_paths: list[str] = []
            for ev in events:
                if ev.mask & F.Q_OVERFLOW:
                    self._rescan_all()
                    continue
                folder = self._wd.get(ev.wd)
                if folder is None:
                    continue
                if ev.mask & (F.DELETE_SELF | F.MOVE_SELF | F.IGNORED):
                    self._wd.pop(ev.wd, None)
                    continue
                if not ev.name or skip_name(ev.name):
                    continue
                rel = f"{folder}/{ev.name}" if folder else ev.name
                if ev.mask & F.ISDIR:
                    if ev.mask & (F.CREATE | F.MOVED_TO):
                        found: dict[str, None] = {}
                        self._walk(rel, found, watch=True)
                        with self._lock:
                            for p in found:
                                self._pending[p] = now
                    elif ev.mask & (F.DELETE | F.MOVED_FROM):
                        with self._lock:
                            for p, h in self.store.known_paths().items():
                                if h is not None and p.startswith(rel + "/"):
                                    self._pending[p] = now
                    changed_paths.append(rel)
                    continue
                with self._lock:
                    self._pending[rel] = now
                changed_paths.append(rel)
            if changed_paths:
                self.emit("fs", {"paths": sorted(set(changed_paths))[:500]})

    def _rescan_all(self) -> None:
        found: dict[str, None] = {}
        self._walk("", found, watch=False)
        now = time.time()
        with self._lock:
            for p in found:
                self._pending[p] = now
            for p, h in self.store.known_paths().items():
                if h is not None and p not in found:
                    self._pending[p] = now

    def _tick(self) -> None:
        """Snapshot settled files; close the change set once things go quiet."""
        while not self._stop.wait(0.5):
            now = time.time()
            with self._lock:
                ready = [p for p, t in self._pending.items() if now - t >= self.settle_sec]
                for p in ready:
                    del self._pending[p]
                busy = bool(self._pending)
            for path in ready:
                try:
                    self._settle(path)
                except Exception as exc:  # one unreadable file must not stop the recorder, but it's reported
                    self.problem(f"history-record:{path}", f"Change history couldn't record {path}",
                                 f"{type(exc).__name__}: {exc}")
            with self._lock:
                close = self._cs is not None and not busy and now - self._cs_last >= self.quiet_sec
                cs, started, last, paths = self._cs, self._cs_started, self._cs_last, list(self._cs_paths)
                if close:
                    self._cs, self._cs_paths = None, []
                for p, (_h, t) in list(self._expected.items()):
                    if now - t > 120:
                        del self._expected[p]
            if close and cs is not None:
                try:
                    source = self.attribute(started, last, paths)
                except Exception:
                    source = "unknown"
                self.store.close_changeset(cs, source)
                for p in set(paths):
                    self.changed(p, source)
                info = self.store.changeset(cs)
                if info:
                    self.emit("changeset", {**info, "file_count": len(set(paths))})
                self.store.enforce_cap()

    def _settle(self, path: str) -> None:
        h = self._snapshot(path)
        if h is False:
            return
        if self.store.current(path) == h:
            return
        with self._lock:
            exp = self._expected.get(path)
            own = exp is not None and exp[0] == h
            if own:
                del self._expected[path]
        if own:
            self.store.record(path, h, "you", None)
            self.changed(path, "you")
            return
        with self._lock:
            if self._cs is None:
                self._cs = self.store.open_changeset()
                self._cs_started = time.time()
                self.emit("changeset.open", {"id": self._cs, "started": self._cs_started})
            cs = self._cs
            self._cs_last = time.time()
            self._cs_paths.append(path)
        self.store.record(path, h, "agent", cs)


def project_of(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if parts else ""
