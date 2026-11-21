# Security Policy

## Supported Versions

Security fixes go into the latest release line of **VibeBuilder IDE**:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Architectural Security Guarantees

* **Sign-In Before Anything**: Every file, search, diff, terminal and tunnel endpoint requires a session. A session needs a paired device token (stored hashed, at most 3 devices) **and** a 6-digit authenticator code. Only the code for the current 30-second step is accepted, and each code works once.
* **Short-Lived Pairing**: Pairing codes expire after 30 seconds and work once. Repeated failures lock out the client's address, plus a global failure limit.
* **Server ↔ Builder Split**: The internet-facing server runs read-only, with every capability dropped, no new privileges, and the workspace mounted `noexec`. AI agents and terminals run in a separate builder container that can't see the server's secrets or data. The builder agent accepts only the server (shared token on a private Podman network).
* **Workspace Jail**: Every file operation resolves through `openat2(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV)`, so symlinks, `..` and mount tricks can't reach outside the workspace.
* **No Tokens in URLs**: WebSockets authenticate with their first message, so session tokens never land in proxy or server logs. The laptop app keeps its device token in the system keychain.
* **Rootless Containers**: Both containers run under rootless Podman. "root" inside the builder is an unprivileged user on the host.

**What the builder is for:** agents run there with full rights *inside the container* (`--dangerously-skip-permissions`, passwordless `sudo`), and they can change anything in your workspace. Treat the workspace as theirs, and keep secrets you care about out of it.

## Reporting a Vulnerability

If you discover a potential security vulnerability, please report it privately via email to **todd.0042.git@gmail.com** or through [GitHub Private Vulnerability Reporting](https://github.com/Todd0042/VibeBuilder-IDE-public/security/advisories/new) rather than filing a public issue. Security reports will receive an acknowledgment within 48 hours.
