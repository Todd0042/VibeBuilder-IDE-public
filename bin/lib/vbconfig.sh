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
# 1 = trust Cloudflare's CF-Connecting-IP header for the client's address (use with Cloudflare Tunnel).
: "${VB_TRUST_CF:=1}"
# The name your authenticator app shows for this server.
: "${VB_TOTP_ISSUER:=VibeBuilder}"
# Builder limits.
: "${VB_BUILDER_MEMORY:=16g}"
: "${VB_BUILDER_CPUS:=$(nproc)}"
# Optional: the laptop app's app id (keychain and saved settings are tied to it).
: "${VB_APP_IDENTIFIER:=}"

export VB_PUBLIC_URL VB_WORKSPACE_DIR VB_STATE_DIR VB_CONTAINER_STORAGE VB_SERVER_PORT VB_TRUST_CF \
  VB_TOTP_ISSUER VB_BUILDER_MEMORY VB_BUILDER_CPUS VB_APP_IDENTIFIER
