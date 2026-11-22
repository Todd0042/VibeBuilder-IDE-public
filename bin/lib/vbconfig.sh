# Shared settings for the bin/ scripts: sourced, not run.
#
# Everything specific to one machine lives in vibebuilder.env at the repo root (copy
# vibebuilder.env.example to start). Set VIBEBUILDER_ENV to use a file somewhere else.
# The file is plain KEY=value lines, read by bash: quote values that contain spaces.

VB_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VB_ENV_FILE="${VIBEBUILDER_ENV:-$VB_REPO/vibebuilder.env}"
if [[ -f "$VB_ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$VB_ENV_FILE"
  set +a
fi

# Where the IDE is reachable from your other devices, e.g. https://ide.example.com
: "${VB_PUBLIC_URL:=}"
# The folder the IDE shows (and that agents can change).
: "${VB_WORKSPACE_DIR:=$HOME/vibebuilder-workspace}"
# Secrets, history, the builder's home folder and other state. Never inside the workspace.
: "${VB_STATE_DIR:=$HOME/.local/share/vibebuilder}"
# Optional: where Podman keeps images and containers (the builder image is large). Empty = Podman's default.
: "${VB_CONTAINER_STORAGE:=}"
# The port the server listens on (127.0.0.1 only; put a tunnel or reverse proxy in front).
: "${VB_SERVER_PORT:=8765}"
# How the server identifies client IPs for sign-in lockouts:
#   none       = use the socket peer directly (Tailscale Serve, SSH port forward)
#   forwarded  = use the rightmost X-Forwarded-For from your local reverse proxy (Caddy, Nginx, Tailscale Funnel)
#   cloudflare = use CF-Connecting-IP (Cloudflare Tunnel only)
# Legacy VB_TRUST_CF=1 still maps to VB_PROXY=cloudflare when VB_PROXY isn't set.
: "${VB_TRUST_CF:=}"
if [[ -z "${VB_PROXY:-}" ]]; then
  if [[ "$VB_TRUST_CF" == 1 ]]; then
    VB_PROXY=cloudflare
  else
    VB_PROXY=none
  fi
fi
: "${VB_TRUST_CF:=0}"
# The name your authenticator app shows for this server.
: "${VB_TOTP_ISSUER:=VibeBuilder}"
# Builder limits.
: "${VB_BUILDER_MEMORY:=16g}"
: "${VB_BUILDER_CPUS:=$(nproc)}"
# Max file size in bytes that can be opened in the IDE editor (default: 32 MB).
: "${VB_MAX_FILE_BYTES:=33554432}"
# Session idle timeout in seconds (default: 600 = 10 min; 86400 = 24h, 0 = no idle timeout).
: "${VB_SESSION_IDLE_SEC:=600}"
# Allow internal symlinks beneath /workspace (0 = strict ban, 1 = allow internal symlinks).
: "${VB_ALLOW_INTERNAL_SYMLINKS:=0}"
# Allow downloading workspace files and viewing arbitrary binary assets (0 = media only, 1 = allow all).
: "${VB_ALLOW_FILE_DOWNLOAD:=0}"
# Allow all files in local checkpoints (1 = do not drop .env or files > 5MB).
: "${VB_CHECKPOINT_ALLOW_ALL:=0}"
# Optional: the laptop app's app id (keychain and saved settings are tied to it).
: "${VB_APP_IDENTIFIER:=}"

export VB_PUBLIC_URL VB_WORKSPACE_DIR VB_STATE_DIR VB_CONTAINER_STORAGE VB_SERVER_PORT VB_PROXY VB_TRUST_CF \
  VB_TOTP_ISSUER VB_BUILDER_MEMORY VB_BUILDER_CPUS VB_MAX_FILE_BYTES VB_SESSION_IDLE_SEC \
  VB_ALLOW_INTERNAL_SYMLINKS VB_ALLOW_FILE_DOWNLOAD VB_CHECKPOINT_ALLOW_ALL VB_APP_IDENTIFIER
