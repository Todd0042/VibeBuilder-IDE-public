"""Settings, read once from the environment.

Secrets are files, not environment variables, so they never show up in `podman inspect` or in a
process listing. The data directory lives only in the server container; the builder never sees it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [x.strip() for x in raw.split(",") if x.strip() and x.strip() != "*"]


def _proxy_mode() -> str:
    raw = os.environ.get("VB_PROXY", "").strip().lower()
    if raw:
        if raw in ("none", "cloudflare", "forwarded"):
            return raw
        raise ValueError(f"Unknown VB_PROXY={raw!r}; expected none, cloudflare, or forwarded")
    cf = os.environ.get("VB_TRUST_CF", "").strip()
    if cf == "1":
        return "cloudflare"
    return "none"


@dataclass(frozen=True)
class Settings:
    workspace: Path = field(default_factory=lambda: Path(os.environ.get("VB_WORKSPACE", "/workspace")))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("VB_DATA", "/data")))
    agent_url: str = field(default_factory=lambda: os.environ.get("VB_AGENT_URL", "ws://vb-builder:7070"))
    agent_token_file: Path = field(
        default_factory=lambda: Path(os.environ.get("VB_AGENT_TOKEN_FILE", "/run/vb-link/agent_token")))
    allowed_origins: list[str] = field(default_factory=lambda: _list(
        "VB_ALLOWED_ORIGINS", "tauri://localhost,http://tauri.localhost,http://localhost:1420"))
    # Where devices reach this server (shown in the pairing QR), and the name authenticator apps show.
    public_url: str = field(default_factory=lambda: os.environ.get("VB_PUBLIC_URL", "").strip().rstrip("/"))
    totp_issuer: str = field(default_factory=lambda: os.environ.get("VB_TOTP_ISSUER", "").strip() or "VibeBuilder")
    # How client IPs arrive behind a local tunnel/proxy: none | cloudflare | forwarded.
    proxy_mode: str = field(default_factory=_proxy_mode)

    allow_internal_symlinks: bool = field(
        default_factory=lambda: os.environ.get("VB_ALLOW_INTERNAL_SYMLINKS", "0").strip() == "1")
    allow_file_download: bool = field(
        default_factory=lambda: os.environ.get("VB_ALLOW_FILE_DOWNLOAD", "0").strip() == "1")

    max_devices: int = field(default_factory=lambda: _int("VB_MAX_DEVICES", 3))
    session_idle_sec: int = field(default_factory=lambda: _int("VB_SESSION_IDLE_SEC", 10 * 60))
    pair_code_ttl_sec: int = field(default_factory=lambda: _int("VB_PAIR_TTL_SEC", 30))
    max_failures_per_ip: int = field(default_factory=lambda: _int("VB_MAX_FAILURES", 5))
    lockout_sec: int = field(default_factory=lambda: _int("VB_LOCKOUT_SEC", 15 * 60))
    max_global_failures: int = field(default_factory=lambda: _int("VB_MAX_GLOBAL_FAILURES", 30))

    max_file_bytes: int = field(default_factory=lambda: _int("VB_MAX_FILE_BYTES", 32 * 1024 * 1024))
    history_cap_bytes: int = field(default_factory=lambda: _int("VB_HISTORY_CAP_BYTES", 10 * 1024**3))
    history_max_file_bytes: int = field(default_factory=lambda: _int("VB_HISTORY_MAX_FILE_BYTES", 16 * 1024 * 1024))
    changeset_quiet_sec: float = field(default_factory=lambda: float(os.environ.get("VB_CHANGESET_QUIET_SEC", "5")))
    file_settle_sec: float = field(default_factory=lambda: float(os.environ.get("VB_FILE_SETTLE_SEC", "2")))
    # Checkpoint commits: how long a project must be quiet first (like auto-save).
    checkpoint_delay_sec: float = field(default_factory=lambda: float(os.environ.get("VB_CHECKPOINT_DELAY_SEC", "180")))

    @property
    def secrets_dir(self) -> Path:
        return self.data_dir / "secrets"

    @property
    def totp_secret_file(self) -> Path:
        return self.secrets_dir / "totp_secret"

    @property
    def auth_db(self) -> Path:
        return self.data_dir / "auth.sqlite3"

    @property
    def history_dir(self) -> Path:
        return self.data_dir / "history"

    @property
    def checkpoints_file(self) -> Path:
        return self.data_dir / "checkpoints.json"

    @property
    def agent_rules_file(self) -> Path:
        """Projects that were given the starter AGENTS.md once (never again, even if it's deleted)."""
        return self.data_dir / "agent_rules.json"

    @property
    def folders_file(self) -> Path:
        """Folders hidden from the app's folder list (shared by every device)."""
        return self.data_dir / "folders.json"

    @property
    def pair_dir(self) -> Path:
        """Where `vbide pair` publishes the current pairing code for the running server to accept."""
        return self.data_dir / "pairing"

    def read_secret(self, path: Path) -> str:
        try:
            return path.read_text().strip()
        except FileNotFoundError:
            return ""
