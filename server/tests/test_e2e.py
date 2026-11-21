"""End-to-end: the real server and the real builder agent as separate processes, a throwaway workspace,
and an "agent" editing files behind the IDE's back, the way Claude and agy do.

Scenario: pair a laptop with a 30-second code, sign in with the authenticator, refuse a replayed code,
try to escape the workspace through symlinks, edit and save with a conflict, let an agent change three
files (one new, one deleted), review the change set, restore it, search, run a terminal, then revoke
the device and watch its session die.

Run: cd server && .venv/bin/pytest -q   (needs ripgrep and fish on PATH)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
import pyotp
import pytest

from stack import fresh_code, pair_code, running_stack, signed_in
import websockets



@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    with running_stack(tmp_path_factory.mktemp("vb")) as s:
        yield s


def _pair_code(stack) -> str:
    return pair_code(stack["data"])


def _fresh_code(totp, used):
    return fresh_code(totp, used)


def test_full_session(stack):
    url, used_steps = stack["url"], stack.setdefault("used_steps", set())
    c = httpx.Client(base_url=url, timeout=15, headers={"cf-connecting-ip": "203.0.113.7"})

    # Nothing is served before sign-in.
    assert c.get("/api/v1/projects").status_code == 401
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404

    # Pairing: wrong code fails, the shown code works once.
    assert c.post("/api/v1/auth/pair", json={"code": "AAA-AAA", "device_name": "x"}).status_code == 401
    code = _pair_code(stack)
    r = c.post("/api/v1/auth/pair", json={"code": code.lower()[:3] + "-" + code[3:], "device_name": "Laptop"})
    assert r.status_code == 200, r.text
    device_token = r.json()["device_token"]
    assert c.post("/api/v1/auth/pair", json={"code": code, "device_name": "again"}).status_code == 401

    # Login needs device token + current code; the same code can't be used twice.
    totp_code = _fresh_code(stack["totp"], used_steps)
    assert c.post("/api/v1/auth/login", json={"device_token": "nope", "code": totp_code}).status_code == 401
    r = c.post("/api/v1/auth/login", json={"device_token": device_token, "code": totp_code})
    assert r.status_code == 200, r.text
    assert c.post("/api/v1/auth/login", json={"device_token": device_token, "code": totp_code}).status_code == 401
    session = r.json()["session"]
    c.headers["authorization"] = f"Bearer {session}"

    assert c.get("/api/v1/projects").json()["projects"] == ["proj"]
    names = {e["name"]: e["kind"] for e in c.get("/api/v1/fs/list", params={"path": "proj"}).json()["entries"]}
    assert names["src"] == "dir" and names["leak.txt"] == "symlink"

    # Escapes: symlinked file, symlinked folder, dot-dot, absolute.
    for bad in ("proj/leak.txt", "proj/datalink/secrets/totp_secret", "../secret.txt", "/etc/passwd",
                "proj/../../secret.txt"):
        r = c.get("/api/v1/fs/file", params={"path": bad})
        assert r.status_code in (403, 404), (bad, r.status_code, r.text)
        assert "outside the workspace" not in r.text
    assert c.put("/api/v1/fs/file", json={"path": "proj/datalink/x", "content": "x", "base_etag": None}).status_code in (403, 404)

    # Open, save, conflict.
    f = c.get("/api/v1/fs/file", params={"path": "proj/src/app.py"}).json()
    new = f["content"].replace("'hi'", "'hello'")
    r = c.put("/api/v1/fs/file", json={"path": "proj/src/app.py", "content": new, "base_etag": f["etag"]})
    assert r.status_code == 200, r.text
    stale = c.put("/api/v1/fs/file", json={"path": "proj/src/app.py", "content": "x", "base_etag": f["etag"]})
    assert stale.status_code == 409
    time.sleep(1.5)

    # An agent edits behind the IDE's back: modify, create, delete in one burst.
    ws = stack["ws"]
    (ws / "proj" / "src" / "app.py").write_text(new.replace("print(hello())", "if __name__ == '__main__':\n    print(hello())"))
    (ws / "proj" / "src" / "util.py").write_text("def add(a, b):\n    return a + b\n")
    (ws / "proj" / "old.txt").unlink()
    deadline = time.time() + 15
    sets = []
    while time.time() < deadline:
        sets = c.get("/api/v1/history/changesets").json()["changesets"]
        if sets and sets[0]["closed"]:
            break
        time.sleep(0.5)
    assert sets, "the agent's change set was not recorded"
    cs = sets[0]
    assert cs["file_count"] == 3, cs
    assert all(s["source"] != "you" for s in sets), "your own save must not show up as an agent change"

    review = c.get(f"/api/v1/history/changesets/{cs['id']}").json()
    by_path = {x["path"]: x for x in review["files"]}
    assert by_path["proj/src/util.py"]["status"] == "added"
    assert by_path["proj/old.txt"]["status"] == "deleted"
    app_diff = by_path["proj/src/app.py"]
    assert app_diff["status"] == "modified" and app_diff["added"] == 2 and app_diff["removed"] == 1
    lines = app_diff["hunks"][0]["lines"]
    assert any(l["t"] == "+" and "__main__" in l["s"] for l in lines)
    assert "return 'hello'" in "\n".join(l["s"] for l in lines), "context lines around the change are included"

    # Restore the whole change set: files go back to how they were before the agent.
    r = c.post("/api/v1/history/restore", json={"changeset": cs["id"]})
    assert r.status_code == 200, r.text
    assert (ws / "proj" / "old.txt").read_text() == "remove me\n"
    assert not (ws / "proj" / "src" / "util.py").exists()
    assert "print(hello())" in (ws / "proj" / "src" / "app.py").read_text()

    # Search the project (Ctrl+Shift+F) and list files (Ctrl+P).
    r = c.post("/api/v1/search", json={"query": "HELLO", "root": "proj"}).json()
    paths = [f["path"] for f in r["files"]]
    assert "proj/src/app.py" in paths and r["match_count"] >= 2
    assert "proj/leak.txt" not in paths, "search must not follow symlinks"
    files = c.get("/api/v1/fs/files", params={"root": "proj"}).json()["files"]
    assert "src/app.py" in files and "leak.txt" not in files

    # A terminal: start a shell, run a command, see its output; it survives detaching.
    t = c.post("/api/v1/terminals", json={"kind": "shell", "cwd": "proj"}).json()

    async def run_terminal() -> str:
        async with websockets.connect(f"{stack['wsurl']}/api/v1/pty/{t['id']}") as w:
            await w.send(json.dumps({"type": "auth", "session": session}))
            got = b""
            await w.send(json.dumps({"type": "input", "data": "echo vb-$((40+2))\r"}))
            end = time.time() + 10
            while time.time() < end and b"vb-42" not in got:
                try:
                    m = await asyncio.wait_for(w.recv(), 1)
                except TimeoutError:
                    continue
                if isinstance(m, bytes):
                    got += m
            return got.decode(errors="replace")

    assert "vb-42" in asyncio.run(run_terminal())
    assert any(x["id"] == t["id"] for x in c.get("/api/v1/terminals").json()["terminals"])

    async def reattach() -> str:  # the scrollback is replayed to a new attach
        async with websockets.connect(f"{stack['wsurl']}/api/v1/pty/{t['id']}") as w:
            await w.send(json.dumps({"type": "auth", "session": session}))
            got = b""
            end = time.time() + 5
            while time.time() < end and b"vb-42" not in got:
                try:
                    m = await asyncio.wait_for(w.recv(), 1)
                except TimeoutError:
                    continue
                if isinstance(m, bytes):
                    got += m
            return got.decode(errors="replace")

    assert "vb-42" in asyncio.run(reattach())
    c.delete(f"/api/v1/terminals/{t['id']}")

    # A WebSocket with a bad session is refused.
    async def bad_ws() -> int | None:
        async with websockets.connect(f"{stack['wsurl']}/api/v1/live") as w:
            await w.send(json.dumps({"type": "auth", "session": "forged"}))
            try:
                await asyncio.wait_for(w.recv(), 3)
            except websockets.ConnectionClosed as exc:
                return exc.rcvd.code if exc.rcvd else None
        return None

    assert asyncio.run(bad_ws()) == 4401

    # Revoking the device ends its session immediately.
    devices = c.get("/api/v1/auth/devices").json()["devices"]
    assert len(devices) == 1 and devices[0]["current"]
    assert c.delete(f"/api/v1/auth/devices/{devices[0]['id']}").status_code == 200
    assert c.get("/api/v1/projects").status_code == 401


def test_lockout(stack):
    c = httpx.Client(base_url=stack["url"], timeout=10, headers={"cf-connecting-ip": "198.51.100.9"})
    for _ in range(5):
        assert c.post("/api/v1/auth/login", json={"device_token": "x", "code": "123456"}).status_code == 401
    assert c.post("/api/v1/auth/login", json={"device_token": "x", "code": "123456"}).status_code == 429
    # A different address isn't locked out by someone else's failures.
    other = httpx.Client(base_url=stack["url"], timeout=10, headers={"cf-connecting-ip": "198.51.100.10"})
    assert other.post("/api/v1/auth/login", json={"device_token": "x", "code": "123456"}).status_code == 401


def _signed_in(stack, ip: str) -> tuple[httpx.Client, str]:
    return signed_in(stack, ip)


def test_tunnels(stack):
    """App testing plumbing: a dev server reached from the laptop (forward), adb/waypipe-style
    connections from the builder to the laptop (reverse), and the "what's listening" list."""
    c, session = _signed_in(stack, "203.0.113.20")
    wsurl = stack["wsurl"]

    async def scenario() -> None:
        # A "dev server" in the builder (the agent runs on this machine in the test).
        async def echo(reader, writer):
            while data := await reader.read(65536):
                writer.write(b"echo:" + data)
                await writer.drain()
            writer.close()
        dev = await asyncio.start_server(echo, "127.0.0.1", 0)
        port = dev.sockets[0].getsockname()[1]

        listed = c.get("/api/v1/ports").json()["ports"]
        assert any(p["port"] == port for p in listed), listed

        # forward: laptop -> builder:port
        async with websockets.connect(f"{wsurl}/api/v1/tunnel") as w:
            await w.send(json.dumps({"type": "auth", "session": session}))
            await w.send(json.dumps({"kind": "port", "port": port}))
            assert json.loads(await w.recv()) == {"type": "open"}
            await w.send(b"GET / HTTP/1.1\r\n\r\n" * 3)
            got = b""
            while len(got) < 5 + 18 * 3:
                got += await asyncio.wait_for(w.recv(), 5)
            assert got.startswith(b"echo:GET / HTTP/1.1")

        # the agent's own port and bad requests are refused
        for bad in ({"kind": "port", "port": 7070}, {"kind": "port", "port": "80"}, {"kind": "reverse", "conn": "../x"}):
            async with websockets.connect(f"{wsurl}/api/v1/tunnel") as w:
                await w.send(json.dumps({"type": "auth", "session": session}))
                await w.send(json.dumps(bad))
                try:
                    msg = await asyncio.wait_for(w.recv(), 5)
                    assert msg != '{"type":"open"}' or bad["port"] != 7070, bad
                except websockets.ConnectionClosed:
                    pass

        # reverse: the laptop asks the builder to listen; a builder program connects; bytes flow both ways
        async with websockets.connect(f"{wsurl}/api/v1/reverse") as ctl:
            await ctl.send(json.dumps({"type": "auth", "session": session}))
            assert json.loads(await ctl.recv()) == {"type": "ready"}
            await ctl.send(json.dumps({"type": "listen", "id": "adb", "tcp": 80}))  # below 1024: dropped
            await ctl.send(json.dumps({"type": "listen", "id": "adb", "tcp": 25037}))
            assert json.loads(await asyncio.wait_for(ctl.recv(), 5)) == {"type": "listening", "id": "adb", "port": 25037}
            await ctl.send(json.dumps({"type": "listen", "id": "wp-run1", "unix": True}))
            m = json.loads(await asyncio.wait_for(ctl.recv(), 5))
            assert m["type"] == "listening" and m["path"] == "/tmp/vb-rev/wp-run1.sock"

            # ports we listen on for the laptop aren't offered for forwarding
            assert not any(p["port"] == 25037 for p in c.get("/api/v1/ports").json()["ports"])

            reader, writer = await asyncio.open_connection("127.0.0.1", 25037)  # "adb" in the builder
            conn = json.loads(await asyncio.wait_for(ctl.recv(), 5))
            assert conn["type"] == "conn" and conn["id"] == "adb"
            async with websockets.connect(f"{wsurl}/api/v1/tunnel") as data:
                await data.send(json.dumps({"type": "auth", "session": session}))
                await data.send(json.dumps({"kind": "reverse", "conn": conn["conn"]}))
                assert json.loads(await data.recv()) == {"type": "open"}
                writer.write(b"host:devices")
                await writer.drain()
                assert await asyncio.wait_for(data.recv(), 5) == b"host:devices"
                await data.send(b"OKAY0000")
                assert await asyncio.wait_for(reader.readexactly(8), 5) == b"OKAY0000"
            writer.close()

            # a connection id works once
            async with websockets.connect(f"{wsurl}/api/v1/tunnel") as again:
                await again.send(json.dumps({"type": "auth", "session": session}))
                await again.send(json.dumps({"kind": "reverse", "conn": conn["conn"]}))
                with pytest.raises(websockets.ConnectionClosed):
                    msg = await asyncio.wait_for(again.recv(), 5)
                    assert msg != '{"type":"open"}'
                    await asyncio.wait_for(again.recv(), 5)
        # closing the control socket stops the listener
        await asyncio.sleep(0.3)
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", 25037)
        dev.close()

    asyncio.run(scenario())

    # run terminals: a command is required, and the waypipe socket must be one of ours
    assert c.post("/api/v1/terminals", json={"kind": "run", "cmd": ""}).status_code == 400
    assert c.post("/api/v1/terminals", json={"kind": "run", "cmd": "true", "waypipe_socket": "/etc/passwd"}).status_code == 400
    r = c.post("/api/v1/terminals", json={"kind": "run", "cmd": "echo hi-from-run"})
    assert r.status_code == 200 and r.json()["kind"] == "run" and r.json()["title"].startswith("▶")
    c.delete(f"/api/v1/terminals/{r.json()['id']}")
