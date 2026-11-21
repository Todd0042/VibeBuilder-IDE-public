"""A real server + builder agent on a throwaway workspace, for the end-to-end tests (server and UI)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pyotp

ROOT = Path(__file__).resolve().parents[2]


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_http(url: str, proc: subprocess.Popen) -> None:
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError(f"{url} process exited: {proc.stderr.read().decode() if proc.stderr else ''}")
        try:
            httpx.get(url, timeout=0.5)
            return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"{url} never came up")


@contextmanager
def running_stack(base: Path, server_port: int | None = None, prepare=None):
    """`prepare(data_dir)`, if given, runs after the folders exist and before the server starts."""
    ws, data, link = base / "workspace", base / "data", base / "link"
    for d in (ws / "proj" / "src", data / "secrets", link):
        d.mkdir(parents=True)
    (ws / "proj" / "src" / "app.py").write_text("def hello():\n    return 'hi'\n\n\nprint(hello())\n")
    (ws / "proj" / "README.md").write_text("# proj\n\nA test project.\n")
    (ws / "proj" / "old.txt").write_text("remove me\n")
    (base / "secret.txt").write_text("outside the workspace\n")
    os.symlink(base / "secret.txt", ws / "proj" / "leak.txt")
    os.symlink(data, ws / "proj" / "datalink")
    # Stand-in for `claude -p` (checkpoint messages): logs what it was given; fails while claude-fail exists.
    fake = base / "fake-claude"
    fake.write_text(f"""#!{sys.executable}
import sys, pathlib
base = pathlib.Path({str(base)!r})
(base / "claude-calls.log").open("a").write(sys.stdin.read() + "\\n=====\\n")
if (base / "claude-fail").exists():
    sys.exit(1)
print("Add the greeting feature\\n\\n- Add feature.js\\n- Wire it into app.js")
""")
    fake.chmod(0o755)
    secret = pyotp.random_base32()
    (data / "secrets" / "totp_secret").write_text(secret)
    (link / "agent_token").write_text("agent-token-for-tests")
    if prepare:
        prepare(data)

    agent_port, server_port = _port(), server_port or _port()
    env = {**os.environ, "VB_WORKSPACE": str(ws), "VB_DATA": str(data), "VB_AGENT_TOKEN_FILE": str(link / "agent_token"),
           "VB_AGENT_URL": f"ws://127.0.0.1:{agent_port}", "VB_CHANGESET_QUIET_SEC": "1.5", "VB_FILE_SETTLE_SEC": "0.5",
           "VB_TRUST_CF": "1", "HOME": str(base / "home"),
           "VB_CHECKPOINT_DELAY_SEC": "2", "VB_CHECKPOINT_CLAUDE": str(fake)}
    (base / "home" / ".config" / "vibebuilder").mkdir(parents=True)
    # bash, not fish: fish asks the terminal questions that only a real terminal (xterm.js) answers
    (base / "home" / ".config" / "vibebuilder" / "terminals.json").write_text(json.dumps({"shell": "bash"}))
    agent = subprocess.Popen([sys.executable, "-m", "uvicorn", "vbagent.main:app", "--port", str(agent_port),
                              "--log-level", "warning"], cwd=ROOT / "builder" / "agent", env=env,
                             stderr=subprocess.PIPE)
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "vbide.app:app", "--port", str(server_port),
                               "--log-level", "warning"], env=env, stderr=subprocess.PIPE)
    try:
        _wait_http(f"http://127.0.0.1:{agent_port}/terminals", agent)
        _wait_http(f"http://127.0.0.1:{server_port}/api/v1/projects", server)
        time.sleep(1.0)  # first scan = baseline
        yield {"base": base, "ws": ws, "data": data, "url": f"http://127.0.0.1:{server_port}",
               "wsurl": f"ws://127.0.0.1:{server_port}", "totp": pyotp.TOTP(secret), "env": env}
    finally:
        for p in (server, agent):
            p.terminate()
            p.wait(5)




def signed_in(stack, ip: str) -> tuple[httpx.Client, str]:
    """A newly paired device, signed in (waits for a fresh 30-second code if needed)."""
    c = httpx.Client(base_url=stack["url"], timeout=15, headers={"cf-connecting-ip": ip})
    r = c.post("/api/v1/auth/pair", json={"code": pair_code(stack["data"]), "device_name": "Test device"})
    assert r.status_code == 200, r.text
    used = stack.setdefault("used_steps", set())
    r = c.post("/api/v1/auth/login", json={"device_token": r.json()["device_token"], "code": fresh_code(stack["totp"], used)})
    assert r.status_code == 200, r.text
    session = r.json()["session"]
    c.headers["authorization"] = f"Bearer {session}"
    return c, session


def pair_code(data: Path) -> str:
    """What `vibebuilder pair` would show on the desktop."""
    sys.path.insert(0, str(ROOT / "server" / "src"))
    from vbide.auth.devices import DeviceStore
    return DeviceStore(data / "auth.sqlite3", data / "pairing", 3, 30).new_pair_code()[0]


def fresh_code(totp: pyotp.TOTP, used: set[int]) -> str:
    """Codes are single-use per 30 s step; wait for the next step when this one was used."""
    while True:
        step = int(time.time() // 30)
        if step not in used:
            used.add(step)
            return totp.at(step * 30)
        time.sleep(0.5)
