"""Every file operation on the workspace goes through here.

Agents in the builder are root there and can put anything in /workspace: symlinks to /data, to /proc,
or swapped in between a check and an open. So paths are never checked and then opened; the kernel
resolves them with openat2(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS |
RESOLVE_NO_XDEV) against a directory fd of the workspace. A symlink anywhere in a path is refused,
nothing resolves outside the workspace, and the answer can't change between check and use.
"""

from __future__ import annotations

import ctypes
import errno
import os
import posixpath
import secrets
import shutil
import stat as st
from dataclasses import dataclass
from pathlib import Path

_SYS_OPENAT2 = 437  # x86_64 and aarch64
_RESOLVE_NO_XDEV = 0x01
_RESOLVE_NO_MAGICLINKS = 0x02
_RESOLVE_NO_SYMLINKS = 0x04
_RESOLVE_BENEATH = 0x08
_RESOLVE = _RESOLVE_BENEATH | _RESOLVE_NO_SYMLINKS | _RESOLVE_NO_MAGICLINKS | _RESOLVE_NO_XDEV


class _OpenHow(ctypes.Structure):
    _fields_ = [("flags", ctypes.c_uint64), ("mode", ctypes.c_uint64), ("resolve", ctypes.c_uint64)]


_libc = ctypes.CDLL(None, use_errno=True)
_libc.syscall.restype = ctypes.c_long


class JailError(Exception):
    """A path that is not allowed, or doesn't exist. `status` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def clean_rel(rel: str) -> str:
    """Normalise a client path to 'a/b/c' ('' is the workspace itself). Never trusted on its own:
    openat2 does the real enforcement; this only gives clear errors and stable keys."""
    if not isinstance(rel, str) or "\x00" in rel or len(rel) > 4096:
        raise JailError("Bad path")
    p = posixpath.normpath("/" + rel.replace("\\", "/")).lstrip("/")
    if p == ".":
        p = ""
    if p.startswith("..") or "/../" in f"/{p}/":
        raise JailError("Path leaves the workspace")
    return p


@dataclass(frozen=True)
class Entry:
    name: str
    kind: str  # "dir" | "file" | "symlink" | "other"
    size: int
    mtime: float


class Jail:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._root_fd = os.open(self.root, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)

    # ---- low level -------------------------------------------------------------------------
    def open(self, rel: str, flags: int, mode: int = 0) -> int:
        rel = clean_rel(rel) or "."
        how = _OpenHow(flags | os.O_CLOEXEC | os.O_NOFOLLOW, mode, _RESOLVE)
        fd = _libc.syscall(ctypes.c_long(_SYS_OPENAT2), ctypes.c_long(self._root_fd), ctypes.c_char_p(rel.encode()),
                           ctypes.byref(how), ctypes.c_size_t(ctypes.sizeof(how)))
        if fd < 0:
            err = ctypes.get_errno()
            if err == errno.ENOENT:
                raise JailError("Not found", 404)
            if err in (errno.ELOOP, errno.EXDEV):
                raise JailError("Symlinks and mount points can't be opened here", 403)
            if err == errno.ENOTDIR:
                raise JailError("Not a folder", 400)
            if err in (errno.EACCES, errno.EPERM):
                raise JailError("Permission denied", 403)
            raise JailError(os.strerror(err), 400)
        return fd

    def _parent(self, rel: str) -> tuple[int, str]:
        rel = clean_rel(rel)
        if not rel:
            raise JailError("That's the workspace itself")
        parent, name = posixpath.split(rel)
        if name in ("", ".", ".."):
            raise JailError("Bad name")
        return self.open(parent, os.O_PATH | os.O_DIRECTORY), name

    # ---- reading ---------------------------------------------------------------------------
    def stat(self, rel: str) -> os.stat_result:
        fd = self.open(rel, os.O_PATH)
        try:
            return os.fstat(fd)
        finally:
            os.close(fd)

    def list_dir(self, rel: str) -> list[Entry]:
        fd = self.open(rel, os.O_RDONLY | os.O_DIRECTORY)
        out: list[Entry] = []
        try:
            with os.scandir(fd) as it:
                for e in it:
                    try:
                        s = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    kind = ("dir" if st.S_ISDIR(s.st_mode) else "file" if st.S_ISREG(s.st_mode)
                            else "symlink" if st.S_ISLNK(s.st_mode) else "other")
                    out.append(Entry(e.name, kind, s.st_size, s.st_mtime))
        finally:
            os.close(fd)
        return out

    def read_file(self, rel: str, max_bytes: int) -> tuple[bytes, os.stat_result]:
        """Regular files only (O_NONBLOCK so a FIFO can't hang us; anything not S_ISREG is refused)."""
        fd = self.open(rel, os.O_RDONLY | os.O_NONBLOCK)
        try:
            s = os.fstat(fd)
            if not st.S_ISREG(s.st_mode):
                raise JailError("Not a regular file", 400)
            if s.st_size > max_bytes:
                raise JailError(f"File is too large to open here ({s.st_size} bytes)", 413)
            chunks, left = [], max_bytes + 1
            while left > 0:
                b = os.read(fd, min(1 << 20, left))
                if not b:
                    break
                chunks.append(b)
                left -= len(b)
            data = b"".join(chunks)
            if len(data) > max_bytes:
                raise JailError("File grew past the size limit while reading", 413)
            return data, s
        finally:
            os.close(fd)

    # ---- writing ---------------------------------------------------------------------------
    def write_file(self, rel: str, data: bytes) -> os.stat_result:
        """Atomic replace: temp file in the same folder, fsync, rename over. Keeps the old mode."""
        pfd, name = self._parent(rel)
        tmp = f".{name}.vb-{secrets.token_hex(4)}.tmp"
        try:
            mode = 0o644
            try:
                old = os.stat(name, dir_fd=pfd, follow_symlinks=False)
                if not st.S_ISREG(old.st_mode):
                    raise JailError("Only regular files can be saved", 400)
                mode = st.S_IMODE(old.st_mode)
            except FileNotFoundError:
                pass
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=pfd)
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, name, src_dir_fd=pfd, dst_dir_fd=pfd)
            return os.stat(name, dir_fd=pfd, follow_symlinks=False)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=pfd)
            except OSError:
                pass
            raise
        finally:
            os.close(pfd)

    def mkdir(self, rel: str) -> None:
        pfd, name = self._parent(rel)
        try:
            os.mkdir(name, 0o755, dir_fd=pfd)
        except FileExistsError:
            raise JailError("Already exists", 409)
        finally:
            os.close(pfd)

    def create_file(self, rel: str) -> None:
        pfd, name = self._parent(rel)
        try:
            os.close(os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644,
                             dir_fd=pfd))
        except FileExistsError:
            raise JailError("Already exists", 409)
        finally:
            os.close(pfd)

    def rename(self, src: str, dst: str) -> None:
        sfd, sname = self._parent(src)
        try:
            dfd, dname = self._parent(dst)
            try:
                try:
                    os.stat(dname, dir_fd=dfd, follow_symlinks=False)
                    raise JailError("Something with that name already exists", 409)
                except FileNotFoundError:
                    pass
                os.rename(sname, dname, src_dir_fd=sfd, dst_dir_fd=dfd)
            finally:
                os.close(dfd)
        finally:
            os.close(sfd)

    def delete(self, rel: str) -> None:
        pfd, name = self._parent(rel)
        try:
            s = os.stat(name, dir_fd=pfd, follow_symlinks=False)
            if st.S_ISDIR(s.st_mode):
                shutil.rmtree(name, dir_fd=pfd)  # fd-based on Linux: never follows symlinks out
            else:
                os.unlink(name, dir_fd=pfd)
        except FileNotFoundError:
            raise JailError("Not found", 404)
        finally:
            os.close(pfd)

    def fchdir_to(self, rel: str) -> int:
        """An fd for a folder, for child processes (ripgrep) to start in via os.fchdir."""
        return self.open(rel, os.O_RDONLY | os.O_DIRECTORY)
