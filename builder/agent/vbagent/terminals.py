"""Terminals that outlive the app: closing the laptop lid doesn't stop Claude mid-task. Each keeps the
last 2 MB of output, replayed to whoever attaches, and any number of apps can watch one at once.

What each kind runs comes from ~/.config/vibebuilder/terminals.json (made with the defaults below on
first start). Agent kinds drop back to a shell when the agent exits, so the tab stays useful.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import secrets
import shutil
import signal
import struct
import subprocess
import termios
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(os.environ.get("VB_WORKSPACE", "/workspace"))
CONFIG = Path.home() / ".config" / "vibebuilder" / "terminals.json"
SCROLLBACK = 2 * 1024 * 1024
DEFAULTS = {
    "shell": "fish",
    "claude": "claude",
    "agy": "agy",
}
AGENT_FLAGS = {
    "claude": {"--dangerously-skip-permissions", "--rc"},
    "agy": {"--dangerously-skip-permissions", "--remote-control"},
}
TITLES = {"claude": "claude", "agy": "agy", "shell": "shell", "run": "run"}
RUNTIME_DIR = "/tmp/xdg-coder"  # XDG_RUNTIME_DIR for apps (waypipe makes its Wayland socket here)


def _find_free_display() -> int:
    for d in range(95, 150):
        if not os.path.exists(f"/tmp/.X11-unix/X{d}"):
            return d
    return 99


def _cleanup_xvfb(t: Terminal) -> None:
    if t.xvfb_proc:
        try:
            t.xvfb_proc.terminate()
            t.xvfb_proc.wait(timeout=1)
        except Exception:
            try:
                t.xvfb_proc.kill()
            except Exception:
                pass
        t.xvfb_proc = None
    if t.display is not None:
        sock = f"/tmp/.X11-unix/X{t.display}"
        if os.path.exists(sock):
            try:
                os.remove(sock)
            except OSError:
                pass


def load_commands() -> dict[str, str]:
    try:
        user = json.loads(CONFIG.read_text())
    except (FileNotFoundError, ValueError):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(DEFAULTS, indent=2) + "\n")
        user = {}
    return {**DEFAULTS, **{k: v for k, v in user.items() if k in DEFAULTS and isinstance(v, str) and v.strip()}}


@dataclass
class Terminal:
    id: str
    kind: str
    cwd: str
    proc: subprocess.Popen
    fd: int
    created: float = field(default_factory=time.time)
    buffer: bytearray = field(default_factory=bytearray)
    watchers: set[asyncio.Queue] = field(default_factory=set)
    exit_code: int | None = None
    out_log: deque = field(default_factory=lambda: deque(maxlen=3600))  # (second, bytes) for attribution
    title: str = ""
    preview: bool = False
    display: int | None = None
    xvfb_proc: subprocess.Popen | None = None

    @property
    def alive(self) -> bool:
        return self.exit_code is None

    def info(self) -> dict:
        return {"id": self.id, "kind": self.kind, "title": self.title or TITLES[self.kind], "cwd": self.cwd,
                "alive": self.alive, "exit_code": self.exit_code, "created": self.created,
                "preview": self.preview, "display": self.display}


class Terminals:
    def __init__(self) -> None:
        self.items: dict[str, Terminal] = {}

    def spawn(self, kind: str, cwd_rel: str, cols: int, rows: int, cmd: str = "", waypipe_socket: str = "", preview: bool = False) -> Terminal:
        """kind "run" runs `cmd` (an app you're testing). With waypipe_socket its windows go to the
        laptop: waypipe's server side connects to that socket (a reverse listener, see tunnels.py).
        With preview=True, it runs under headless Xvfb with screen capture & interaction."""
        cmds = load_commands()
        shell = cmds["shell"]
        cwd = (WORKSPACE / cwd_rel).resolve() if cwd_rel else WORKSPACE
        if not str(cwd).startswith(str(WORKSPACE)) or not cwd.is_dir():
            cwd = WORKSPACE
        disp_num: int | None = None
        xvfb_proc: subprocess.Popen | None = None
        if kind == "run":
            app = ["bash", "-lc", f"{cmd}; echo; echo \"[exited with code $?]\""]
            if preview:
                disp_num = _find_free_display()
                if shutil.which("Xvfb"):
                    try:
                        xvfb_proc = subprocess.Popen(
                            ["Xvfb", f":{disp_num}", "-screen", "0", "1024x768x24", "-nolisten", "tcp", "+extension", "GLX"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        sock_path = f"/tmp/.X11-unix/X{disp_num}"
                        for _ in range(25):
                            if os.path.exists(sock_path):
                                break
                            time.sleep(0.04)
                    except Exception:
                        xvfb_proc = None
            xwls = ["--xwls"] if shutil.which("xwayland-satellite") else []
            argv = (["waypipe", "--socket", waypipe_socket, "--compress", "zstd", *xwls, "server", "--", *app]
                    if waypipe_socket and not preview else app)
        elif kind == "shell":
            argv = ["bash", "-lc", f"exec {shell} -l"]
        else:
            if cmd.startswith("flags:"):
                base = cmds[kind].replace("--dangerously-skip-permissions", "").strip()
                allowed = AGENT_FLAGS[kind]
                extra = [tok for tok in cmd[6:].split() if tok in allowed]
                launch = f"{base} {' '.join(extra)}".strip()
            else:
                launch = cmds[kind]
            argv = ["bash", "-lc", f"{launch}; echo; echo '[{kind} exited, here is a shell]'; exec {shell} -l"]
        master, slave = os.openpty()
        _set_size(slave, cols, rows)
        os.makedirs(RUNTIME_DIR, mode=0o700, exist_ok=True)
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", "VB_TERMINAL_KIND": kind,
               "XDG_RUNTIME_DIR": RUNTIME_DIR}
        if kind == "run":
            if preview and disp_num is not None:
                env["DISPLAY"] = f":{disp_num}"
                env.update({"GDK_BACKEND": "x11", "QT_QPA_PLATFORM": "xcb", "SDL_VIDEODRIVER": "x11",
                            "WINIT_UNIX_BACKEND": "x11"})
            else:  # toolkits: prefer Wayland (waypipe carries Wayland, not X11)
                env.update({"GDK_BACKEND": "wayland", "QT_QPA_PLATFORM": "wayland;xcb", "SDL_VIDEODRIVER": "wayland,x11",
                            "WINIT_UNIX_BACKEND": "wayland", "ELECTRON_OZONE_PLATFORM_HINT": "wayland",
                            "MOZ_ENABLE_WAYLAND": "1", "WEBKIT_DISABLE_DMABUF_RENDERER": "1"})
        proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, cwd=cwd, env=env,
                                start_new_session=True, close_fds=True,
                                preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
        os.close(slave)
        os.set_blocking(master, False)
        t = Terminal(secrets.token_hex(8), kind, str(cwd.relative_to(WORKSPACE)) if cwd != WORKSPACE else "",
                     proc, master, title=(f"▶ {cmd[:40]}" if kind == "run" else f"{TITLES[kind]}" + (f" · {cwd.name}" if cwd != WORKSPACE else "")),
                     preview=bool(preview and disp_num is not None), display=disp_num, xvfb_proc=xvfb_proc)
        self.items[t.id] = t
        asyncio.get_running_loop().add_reader(master, self._on_output, t)
        return t

    def _on_output(self, t: Terminal) -> None:
        try:
            data = os.read(t.fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._on_exit(t)
            return
        t.buffer += data
        if len(t.buffer) > SCROLLBACK:
            del t.buffer[: len(t.buffer) - SCROLLBACK]
        sec = int(time.time())
        if t.out_log and t.out_log[-1][0] == sec:
            t.out_log[-1] = (sec, t.out_log[-1][1] + len(data))
        else:
            t.out_log.append((sec, len(data)))
        for q in list(t.watchers):
            if q.qsize() < 2000:
                q.put_nowait(data)

    def _on_exit(self, t: Terminal) -> None:
        loop = asyncio.get_running_loop()
        loop.remove_reader(t.fd)
        try:
            os.close(t.fd)
        except OSError:
            pass
        try:
            t.exit_code = t.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            t.proc.kill()
            t.exit_code = -9
        _cleanup_xvfb(t)
        for q in list(t.watchers):
            q.put_nowait(None)

    def write(self, t: Terminal, data: str) -> None:
        if not t.alive:
            return
        raw = data.encode()
        while raw:
            try:
                n = os.write(t.fd, raw)
            except BlockingIOError:
                time.sleep(0.005)
                continue
            except OSError:
                return
            raw = raw[n:]

    def resize(self, t: Terminal, cols: int, rows: int) -> None:
        if t.alive:
            try:
                _set_size(t.fd, cols, rows)
            except OSError:
                pass

    def close(self, tid: str) -> bool:
        t = self.items.pop(tid, None)
        if not t:
            return False
        _cleanup_xvfb(t)
        if t.alive:
            try:
                os.killpg(t.proc.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            asyncio.get_running_loop().call_later(3, _force_kill, t.proc)
        return True

    def output_between(self, since: float, until: float) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in self.items.values():
            n = sum(b for s, b in t.out_log if since <= s <= until)
            if n:
                out[t.kind] = out.get(t.kind, 0) + n
        return out


def _set_size(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _force_kill(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

