"""End-to-end: automatic checkpoint commits and the starter agent rules, with the real server and the
real builder agent (git runs for real; `claude -p` is a stand-in that logs what it was given).

Scenario: a vibecoder's project (a git repo with no .gitignore, a half-staged change of their own).
An agent adds a feature, an .env with a key, a config file with a pasted token and a node_modules
folder. A checkpoint lands on checkpoints/main with the feature but none of the secrets or packages,
while main, the staging area and the working tree stay exactly as they were. More work chains onto
it; a failing Claude falls back to a plain message; a real commit restarts the chain on top of it;
a merge in progress is left alone; the off switch stops checkpoints; "checkpoint now" works.
"""

from __future__ import annotations

import subprocess
import time

import httpx
import pytest

from stack import running_stack, signed_in

KEY = "sk-ant-api03-" + "Zq7" * 12  # looks like an Anthropic key
TOKEN = "ghp_" + "a1B2c3D4e5" * 4  # looks like a GitHub token


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    with running_stack(tmp_path_factory.mktemp("vbck")) as s:
        yield s


def git(repo, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def wait_checkpoint(c: httpx.Client, project: str, after: float, timeout: float = 40) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        last = c.get("/api/v1/checkpoints", params={"project": project}).json().get("last")
        if last and last["at"] > after:
            return last
        time.sleep(0.5)
    raise AssertionError("no checkpoint")


def test_checkpoints(stack):
    c, _ = signed_in(stack, "203.0.113.30")
    assert httpx.get(stack["url"] + "/api/v1/checkpoints", params={"project": "shop"}).status_code == 401

    repo = stack["ws"] / "shop"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.js").write_text("console.log('shop');\n")
    (repo / "package.json").write_text('{"name": "shop", "version": "1.0.0"}\n')
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Vibe Coder")
    git(repo, "config", "user.email", "vibe@example.com")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "Initial")
    head0 = git(repo, "rev-parse", "HEAD")
    time.sleep(1.5)
    info = c.get("/api/v1/checkpoints", params={"project": "shop"}).json()
    assert info["enabled"] is True

    # Their own half-done work: one change staged, a different one not.
    (repo / "package.json").write_text('{"name": "shop", "version": "1.1.0"}\n')
    git(repo, "add", "package.json")
    (repo / "package.json").write_text('{"name": "shop", "version": "1.1.0", "private": true}\n')
    staged_before = git(repo, "diff", "--cached")

    # An agent at work.
    t0 = time.time()
    (repo / "src" / "feature.js").write_text("export const greet = (n) => `hi ${n}`;\n")
    (repo / "src" / "app.js").write_text("import { greet } from './feature.js';\nconsole.log(greet('shop'));\n")
    (repo / ".env").write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    (repo / "src" / "config.js").write_text(f"export const token = '{TOKEN}';\n")
    (repo / "node_modules" / "left-pad").mkdir(parents=True)
    (repo / "node_modules" / "left-pad" / "index.js").write_text("module.exports = 1;\n")

    last = wait_checkpoint(c, "shop", t0)
    (r,) = last["results"]
    assert r["status"] == "committed", r
    assert r["ref"] == "checkpoints/main" and r["title"] == "Add the greeting feature"
    first = git(repo, "rev-parse", "checkpoints/main")
    assert r["commit"] == first
    assert {x["path"]: x["reason"] for x in r["left_out"]} == {
        ".env": "looks like a secrets file", "src/config.js": "contains something that looks like a secret"}

    # What the checkpoint holds: the feature and their package.json as it is on disk; no secrets, no packages.
    files = set(git(repo, "ls-tree", "-r", "--name-only", first).splitlines())
    assert files == {"package.json", "src/app.js", "src/feature.js"}
    assert '"private": true' in git(repo, "show", f"{first}:package.json")
    assert git(repo, "rev-parse", f"{first}^") == head0
    msg = git(repo, "log", "-1", "--format=%B", first)
    assert msg.startswith("Add the greeting feature\n\n- Add feature.js")
    assert "Checkpoint by VibeBuilder" in msg
    # Claude saw the diff, never the secrets.
    sent = (stack["base"] / "claude-calls.log").read_text()
    assert "feature.js" in sent and KEY not in sent and TOKEN not in sent and "left-pad" not in sent

    # Their branch, staging area and files are exactly as they left them.
    assert git(repo, "rev-parse", "HEAD") == head0 and git(repo, "symbolic-ref", "--short", "HEAD") == "main"
    assert git(repo, "diff", "--cached") == staged_before
    assert (repo / ".env").read_text().startswith("ANTHROPIC_API_KEY=")

    # More work chains onto the last checkpoint (main hasn't moved).
    t1 = time.time()
    (repo / "src" / "feature.js").write_text("export const greet = (n) => `hello ${n}!`;\n")
    (r,) = wait_checkpoint(c, "shop", t1)["results"]
    assert r["status"] == "committed" and not r["rolled"]
    second = git(repo, "rev-parse", "checkpoints/main")
    assert git(repo, "rev-parse", f"{second}^") == first

    # Claude unavailable: a plain message instead.
    (stack["base"] / "claude-fail").touch()
    t2 = time.time()
    (repo / "src" / "app.js").write_text("import { greet } from './feature.js';\nconsole.log(greet('world'));\n")
    (r,) = wait_checkpoint(c, "shop", t2)["results"]
    (stack["base"] / "claude-fail").unlink()
    assert r["status"] == "committed" and r["title"] == "Checkpoint: 1 file changed (app.js)"
    assert "- Update src/app.js" in git(repo, "log", "-1", "--format=%B", "checkpoints/main")

    # A real commit on main: the next checkpoint starts again on top of it.
    git(repo, "add", "src/app.js", "src/feature.js", "package.json")
    git(repo, "commit", "-qm", "Greeting feature")
    head1 = git(repo, "rev-parse", "HEAD")
    t3 = time.time()
    (repo / "README.md").write_text("# Shop\n")
    (r,) = wait_checkpoint(c, "shop", t3)["results"]
    assert r["status"] == "committed" and r["rolled"]
    assert git(repo, "rev-parse", "checkpoints/main^") == head1

    # A merge in progress: hands off.
    merge_head = repo / ".git" / "MERGE_HEAD"
    merge_head.write_text(head0 + "\n")
    t4 = time.time()
    (repo / "README.md").write_text("# Shop\n\nSells things.\n")
    (r,) = wait_checkpoint(c, "shop", t4)["results"]
    merge_head.unlink()
    assert r["status"] == "skipped" and "merge" in r["reason"]

    # Off: no checkpoints, however long it waits.
    before = git(repo, "rev-parse", "checkpoints/main")
    assert c.put("/api/v1/checkpoints", json={"project": "shop", "enabled": False}).json()["enabled"] is False
    (repo / "README.md").write_text("# Shop\n\nSells nice things.\n")
    time.sleep(7)
    assert git(repo, "rev-parse", "checkpoints/main") == before
    assert c.post("/api/v1/checkpoints/now", json={"project": "shop"}).status_code == 409

    # On again, and "checkpoint now" doesn't wait.
    assert c.put("/api/v1/checkpoints", json={"project": "shop", "enabled": True}).json()["enabled"] is True
    r = c.post("/api/v1/checkpoints/now", json={"project": "shop"}).json()["results"][0]
    assert r["status"] == "committed" and git(repo, "rev-parse", "checkpoints/main^") == before
    assert "nice things" in git(repo, "show", "checkpoints/main:README.md")
    assert git(repo, "rev-parse", "HEAD") == head1  # main never moved by itself

    # Not a project: refused.
    for bad in ("../etc", "shop/src", "nope"):
        assert c.get("/api/v1/checkpoints", params={"project": bad}).status_code in (400, 403, 404)


def test_starter_agent_rules(stack):
    c, _ = signed_in(stack, "203.0.113.31")
    ws = stack["ws"]
    (ws / "fresh").mkdir()
    (ws / "fresh" / "index.html").write_text("<h1>hi</h1>\n")
    (ws / "legacy").mkdir()
    (ws / "legacy" / "CLAUDE.md").write_text("Use tabs.\n")
    time.sleep(1)

    # A project without rules gets them once.
    r = c.post("/api/v1/agent-rules", json={"project": "fresh"}).json()
    assert r["created"] == ["fresh/AGENTS.md", "fresh/CLAUDE.md"]
    rules = (ws / "fresh" / "AGENTS.md").read_text()
    assert "No file over 500 lines" in rules and "Never put secrets" in rules and "Commit at the end" in rules
    assert "Every error must be visible, with full details, to whoever runs the software" in rules
    assert "Secrets never appear in any error" in rules and "reference ID" in rules
    assert "@AGENTS.md" in (ws / "fresh" / "CLAUDE.md").read_text()
    assert c.post("/api/v1/agent-rules", json={"project": "fresh"}).json()["created"] == []

    # Deleted by the owner: they stay deleted.
    (ws / "fresh" / "AGENTS.md").unlink()
    (ws / "fresh" / "CLAUDE.md").unlink()
    assert c.post("/api/v1/agent-rules", json={"project": "fresh"}).json()["created"] == []
    assert not (ws / "fresh" / "AGENTS.md").exists()

    # A project with its own rules is left alone.
    assert c.post("/api/v1/agent-rules", json={"project": "legacy"}).json()["created"] == []
    assert (ws / "legacy" / "CLAUDE.md").read_text() == "Use tabs.\n" and not (ws / "legacy" / "AGENTS.md").exists()

    for bad in ("../x", "fresh/sub", "missing"):
        assert c.post("/api/v1/agent-rules", json={"project": bad}).status_code in (400, 403, 404)
