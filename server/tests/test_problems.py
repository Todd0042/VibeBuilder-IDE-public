"""End-to-end: problems the server runs into in the background reach the app instead of vanishing.

Scenario: the server starts with an unreadable checkpoint settings file (kept aside, reported, checkpoints still
work). An agent writes a file nobody can read, whose name contains a token: the change history reports it, with the
token masked, once (repeats are counted). A repo git refuses to read shows git's own error instead of "not a repo".
The starter agent rules can't be written into a read-only project: the reply says why, and it's tried again later.
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from stack import running_stack, signed_in

TOKEN = "ghp_" + "Zx9" * 12


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    def corrupt_settings(data):
        (data / "checkpoints.json").write_text('{"off": ["proj"], "last": {')  # cut off mid-write
    with running_stack(tmp_path_factory.mktemp("vbprob"), prepare=corrupt_settings) as s:
        yield s


def wait_problem(c, key_part: str, timeout: float = 15) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        for p in c.get("/api/v1/problems").json()["problems"]:
            if key_part in p["key"]:
                return p
        time.sleep(0.3)
    raise AssertionError(f"no problem {key_part!r}: {c.get('/api/v1/problems').json()}")


def test_problems_reach_the_app(stack):
    c, _ = signed_in(stack, "203.0.113.40")
    ws, data = stack["ws"], stack["data"]
    assert c.get("/api/v1/problems").status_code == 200

    # The unreadable settings file: reported, kept aside for inspection, and checkpoints are on again.
    p = wait_problem(c, "checkpoints-settings")
    assert "checkpoints on" in p["message"] and "Devices view" in p["fix"]
    assert any(f.name.startswith("checkpoints.json.unreadable-") for f in data.iterdir())
    assert c.get("/api/v1/checkpoints", params={"project": "proj"}).json()["enabled"] is True

    # An agent writes a file nobody can read.
    secret = ws / "proj" / f"notes-{TOKEN}.txt"
    secret.write_text("x")
    secret.chmod(0o200)  # write-only: the agent can keep writing it, nobody can read it
    try:
        p = wait_problem(c, "history-record:")
        assert "couldn't read" in p["message"] and "PermissionError" in p["detail"] and "permissions" in p["fix"]
        everything = str(c.get("/api/v1/problems").json())
        assert TOKEN not in everything and "ghp_…" in everything  # masked everywhere it appears
        with open(secret, "a") as f:  # the agent writes it again: counted, not a new problem
            f.write("y")
        time.sleep(3)
        again = [q for q in c.get("/api/v1/problems").json()["problems"] if q["key"] == p["key"]]
        assert len(again) == 1 and again[0]["count"] >= 2
        # Searching the project: the unreadable file is reported, not silently left out.
        r = c.post("/api/v1/search", json={"query": "def", "root": "proj"}).json()
        assert r["match_count"] >= 1 and r["skipped_count"] == 1
        assert r["skipped"][0]["path"].startswith("proj/notes-") and "Permission denied" in r["skipped"][0]["reason"]
        assert c.delete(f"/api/v1/problems/{p['key']}").json()["dismissed"] is True
        assert all(q["key"] != p["key"] for q in c.get("/api/v1/problems").json()["problems"])
    finally:
        secret.chmod(0o644)

    # git refuses the repo: its own words, not "not a repo".
    repo = ws / "broken"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.repositoryformatversion", "99"], check=True)
    g = c.get("/api/v1/git/status", params={"project": "broken"}).json()
    assert g["repo"] is False and "repo version" in g["error"]
    assert "error" not in c.get("/api/v1/git/status", params={"project": "proj"}).json()  # plain "not a repo"

    # Starter agent rules into a read-only project: the reason comes back, and it's tried again next time.
    ro = ws / "readonly"
    ro.mkdir()
    ro.chmod(0o555)
    try:
        r = c.post("/api/v1/agent-rules", json={"project": "readonly"}).json()
        assert r["created"] == [] and r["failed"] and "readonly/AGENTS.md" == r["failed"][0]["path"]
        ro.chmod(0o755)
        r = c.post("/api/v1/agent-rules", json={"project": "readonly"}).json()
        assert r["created"] == ["readonly/AGENTS.md", "readonly/CLAUDE.md"]
    finally:
        ro.chmod(0o755)

    assert c.get("/api/v1/problems", headers={"authorization": "Bearer nope"}).status_code == 401
