"""Checkpoint commits: the work in progress of a repo, saved on a side branch so nothing is lost
between real commits. The branch, the index (staging area) and the working tree are never touched.

For a repo on branch B, checkpoints go to `checkpoints/B`. Each one commits the working tree as it is
(what `git add -A` would take, so .gitignore applies), minus:
  - files that look like secrets (.env, keys, credentials...) or contain something that looks like one;
  - dependency and build folders (node_modules, .venv, target...), even without a .gitignore;
  - new files over 5 MB.
The branch rolls: while B hasn't moved, each checkpoint follows the previous one; once B gets a new
commit (you or an agent committed), the next checkpoint starts again on top of it. Nothing is pushed.

Commit messages are written by Claude Haiku from the diff (`claude -p`, no tools, outside the repo);
if that fails, a plain summary is used.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path, PurePosixPath

from .terminals import WORKSPACE

PREFIX = "checkpoints/"
MAX_NEW_FILE = 5 * 1024 * 1024
MAX_DIFF_FOR_MESSAGE = 48 * 1024
CLAUDE = os.environ.get("VB_CHECKPOINT_CLAUDE", "claude")
# Never part of a checkpoint (unless the repo already tracks them: then they keep their committed state).
SKIP_DIRS = ("node_modules", ".venv", "venv", "__pycache__", "target", "dist", "build", ".next", ".nuxt",
             ".svelte-kit", ".gradle", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
             ".turbo", ".parcel-cache", ".expo", "coverage", ".vibebuilder")
SECRET_NAME = re.compile(
    r"(^|/)(\.env(\.(?!example$|sample$|template$|dist$)[^/]+)?|\.npmrc|\.pypirc|\.netrc|\.pgpass|"
    r"id_(rsa|dsa|ecdsa|ed25519)(\.[^/]*)?|[^/]*\.(pem|key|p12|pfx|jks|keystore|ovpn)|"
    r"(credentials|service[-_]?account|client[-_]?secret)[^/]*\.json|secrets?\.(json|ya?ml|toml))$", re.I)
SECRET_TEXT = re.compile(
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
    rb"|hf_[A-Za-z0-9]{30,}|sk-(ant-)?[A-Za-z0-9_-]{20,}|sk_live_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35}"
    rb"|ya29\.[0-9A-Za-z_-]{20,}|GOCSPX-[A-Za-z0-9_-]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|otpauth:" rb"//\S*secret=")  # split so this pattern isn't itself mistaken for a secret link
WHO = {"claude": "Claude", "agy": "agy", "you": "you (in the editor)", "shell": "a terminal command"}

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class Skip(Exception):
    """No checkpoint, for a reason worth showing."""


def checkpoint_folders(folders: list[str], who: list[str]) -> list[dict]:
    """Checkpoint every repo that contains one of these workspace folders."""
    roots: dict[Path, None] = {}
    for f in folders:
        root = _repo_root(f)
        if root:
            roots[root] = None
    return [checkpoint_repo(r, who) for r in roots]


def checkpoint_repo(root: Path, who: list[str]) -> dict:
    rel = "" if root == WORKSPACE.resolve() else str(root.relative_to(WORKSPACE.resolve()))
    with _lock(str(root)):
        try:
            return {"repo": rel, **_checkpoint(root, who)}
        except Skip as exc:
            return {"repo": rel, "status": "skipped", "reason": str(exc)}
        except (subprocess.SubprocessError, OSError) as exc:
            return {"repo": rel, "status": "failed", "reason": str(exc)[:300]}


# ---- the work ----------------------------------------------------------------------------------
def _checkpoint(root: Path, who: list[str]) -> dict:
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir").strip())
    for busy in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG"):
        if (git_dir / busy).exists():
            raise Skip("a merge, rebase or similar is in progress")
    branch = _git(root, "symbolic-ref", "-q", "--short", "HEAD", check=False).strip()
    if not branch:
        raise Skip("not on a branch (detached HEAD)")
    if branch.startswith(PREFIX):
        raise Skip("on a checkpoint branch")
    head = _git(root, "rev-parse", "-q", "--verify", "HEAD^{commit}", check=False).strip() or None
    ref = f"refs/heads/{PREFIX}{branch}"
    prev = _git(root, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}", check=False).strip() or None

    # Roll: follow the previous checkpoint while it still sits on top of the branch, else start again.
    parent = head
    if prev and (head is None or _git(root, "merge-base", "--is-ancestor", head, prev, check=False, rc=True) == 0):
        parent = prev

    with tempfile.TemporaryDirectory(prefix="vb-ckpt-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if head:
            _git(root, "read-tree", head, env=env)
        excludes = [f":(exclude,glob)**/{d}/**" for d in SKIP_DIRS]
        _git(root, "add", "-A", "--", ".", *excludes, env=env)
        left_out = _drop_unsafe(root, head, env)
        tree = _git(root, "write-tree", env=env).strip()

    base_tree = _git(root, "rev-parse", f"{parent}^{{tree}}").strip() if parent else _empty_tree(root)
    if tree == base_tree:
        return {"status": "unchanged", "branch": branch, "left_out": left_out}

    diff = _git(root, "diff", "--no-color", "--no-ext-diff", "-M", "--stat=100", "--patch", base_tree, tree,
                check=False)
    names = _git(root, "diff", "--name-status", "-M", base_tree, tree).splitlines()
    message = _message(diff, names, who)
    cmd = ["commit-tree", tree, "-F", "-"] + (["-p", parent] if parent else [])
    commit = _git(root, *cmd, input=message, env=_identity(root)).strip()
    _git(root, "update-ref", "-m", "VibeBuilder checkpoint", ref, commit, prev or "0" * len(commit))
    return {"status": "committed", "branch": branch, "ref": f"{PREFIX}{branch}", "commit": commit,
            "title": message.splitlines()[0], "files": len(names), "left_out": left_out,
            "rolled": parent == head and prev is not None}


def _drop_unsafe(root: Path, head: str | None, env: dict) -> list[dict]:
    """Take secrets and oversized new files back out of the checkpoint's index."""
    changed = _git(root, "diff", "--cached", "--name-only", "--no-renames", "--diff-filter=AM", "-z",
                   head or _empty_tree(root), env=env).split("\0")
    left_out = []
    for path in filter(None, changed):
        reason = ""
        if SECRET_NAME.search(path):
            reason = "looks like a secrets file"
        else:
            f = root / path
            try:
                if f.is_file() and not f.is_symlink():
                    size = f.stat().st_size
                    tracked = head and _git(root, "cat-file", "-e", f"{head}:{path}", check=False, rc=True) == 0
                    if size > MAX_NEW_FILE and not tracked:
                        reason = "new file over 5 MB"
                    elif size <= 2 * 1024 * 1024 and SECRET_TEXT.search(f.read_bytes()):
                        reason = "contains something that looks like a secret"
            except OSError:
                continue
        if reason:
            if head and _git(root, "cat-file", "-e", f"{head}:{path}", check=False, rc=True) == 0:
                _git(root, "reset", "-q", head, "--", path, env=env)  # keep its committed state
            else:
                _git(root, "rm", "-q", "--cached", "--", path, env=env)
            left_out.append({"path": path, "reason": reason})
    return left_out[:50]


def _message(diff: str, names: list[str], who: list[str]) -> str:
    makers = [WHO.get(w, w) for w in dict.fromkeys(who) if w in WHO] or ["an agent"]
    trailer = f"\n\nCheckpoint by VibeBuilder · changes by {', '.join(makers)}\n"
    prompt = ("You write git commit messages. The diff on stdin is a work-in-progress checkpoint of a project. "
              "Reply with ONLY the message: a title line in the imperative mood, at most 72 characters; a blank line; "
              "then 1 to 6 short bullet points starting with '- ' naming the main changes. "
              "No code fences, no quotes, no preamble.")
    text = diff if len(diff) <= MAX_DIFF_FOR_MESSAGE else diff[:MAX_DIFF_FOR_MESSAGE] + "\n[diff truncated]\n"
    try:
        r = subprocess.run([CLAUDE, "-p", "--model", "haiku", "--tools", "", "--no-session-persistence",
                            "--disable-slash-commands", "--strict-mcp-config", prompt],
                           input=text, capture_output=True, text=True, timeout=120, cwd=tempfile.gettempdir())
        out = _clean_message(r.stdout) if r.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        out = ""
    return (out or _plain_message(names)) + trailer


def _clean_message(raw: str) -> str:
    lines = [l.rstrip() for l in raw.strip().strip("`").splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or len(lines[0]) > 100 or len(raw) > 4000:
        return ""
    return "\n".join(lines).strip()


def _plain_message(names: list[str]) -> str:
    verbs = {"A": "Add", "M": "Update", "D": "Delete", "R": "Rename"}
    files = [PurePosixPath(n.split("\t")[-1]).name for n in names]
    shown = ", ".join(files[:3]) + (f" and {len(files) - 3} more" if len(files) > 3 else "")
    bullets = "\n".join(f"- {verbs.get(n[:1], 'Change')} {n.split(chr(9))[-1]}" for n in names[:12])
    return f"Checkpoint: {len(files)} file{'s' if len(files) != 1 else ''} changed ({shown})\n\n{bullets}"


# ---- git helpers ---------------------------------------------------------------------------------
def _git(root: Path, *args: str, env: dict | None = None, check: bool = True, rc: bool = False,
         input: str | None = None):
    # No hooks, no fsmonitor, no signing prompts: nothing in the repo's config gets to run here.
    cmd = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false",
           "-C", str(root), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=input,
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})})
    if rc:
        return r.returncode
    if check and r.returncode != 0:
        raise subprocess.SubprocessError(f"git {args[0]}: {r.stderr.strip()[:200]}")
    return r.stdout


def _empty_tree(root: Path) -> str:
    return _git(root, "hash-object", "-t", "tree", "/dev/null").strip()


def _identity(root: Path) -> dict:
    """The repo's own author if it has one, else a clearly-labelled checkpoint author."""
    env = {}
    if not _git(root, "config", "user.name", check=False).strip():
        env.update(GIT_AUTHOR_NAME="VibeBuilder Checkpoint", GIT_COMMITTER_NAME="VibeBuilder Checkpoint")
    if not _git(root, "config", "user.email", check=False).strip():
        env.update(GIT_AUTHOR_EMAIL="checkpoint@vibebuilder.invalid", GIT_COMMITTER_EMAIL="checkpoint@vibebuilder.invalid")
    return env


def _repo_root(folder: str) -> Path | None:
    ws = WORKSPACE.resolve()
    p = (WORKSPACE / folder).resolve()
    while p != ws and ws in p.parents and not p.is_dir():  # the folder may be gone (files deleted)
        p = p.parent
    if not p.is_dir() or (p != ws and ws not in p.parents):
        return None
    try:
        top = subprocess.run(["git", "-C", str(p), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             timeout=10, check=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    root = Path(top).resolve()
    return root if root == ws or ws in root.parents else None


def _lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())
