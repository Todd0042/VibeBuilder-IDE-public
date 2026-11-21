<p align="center">
  <a href="https://ko-fi.com/todd0042">
    <img src="https://raw.githubusercontent.com/Todd0042/creator-assets/main/banners/todd_creator_banner_v1.0.png" alt="Support Todd on Ko-fi" width="100%" />
  </a>
</p>

---

# 🛠️ VibeBuilder IDE

[![Version](https://img.shields.io/badge/Version-0.1.0-ff8a3d.svg)](https://github.com/Todd0042/VibeBuilder-IDE-public/releases)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-00f0ff.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20(AppImage)-orange.svg)](https://github.com/Todd0042/VibeBuilder-IDE-public/releases)
[![App: Tauri 2 + Svelte 5](https://img.shields.io/badge/App-Tauri%202%20%2B%20Svelte%205-8a6cff.svg)]()
[![Server: FastAPI + WebSockets](https://img.shields.io/badge/Server-FastAPI%20%2B%20WebSockets-teal.svg)]()
[![Containers: Rootless Podman](https://img.shields.io/badge/Containers-Rootless%20Podman-892ca0.svg)]()
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Creator-F16061?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/todd0042)

> **Code on your desktop's horsepower from any laptop: a fast, no-frills IDE whose files, terminals and AI agents (Claude Code, agy) live in a locked-down container at home, with an agent-change timeline that shows exactly what the AI touched, and app testing that streams each window of the app you're building straight to your laptop.**

<p align="center">
  <img src="screenshots/main_window_clean.png" alt="VibeBuilder IDE main window" width="100%">
</p>

---

## 📖 Table of Contents

* **Part 1 — Overview & Quick Start**
  * [🧠 What Is VibeBuilder IDE?](#-what-is-vibebuilder-ide)
  * [🔁 How It Works in 3 Steps](#-how-it-works-in-3-steps)
  * [📸 Visual Tour](#-visual-tour)
  * [✨ Highlights at a Glance](#-highlights-at-a-glance)
  * [🚀 Quick Download & Installation](#-quick-download--installation)
* **Part 2 — Technical Documentation & Architecture Reference**
  * [1. System Architecture ([server/](server/), [builder/](builder/), [desktop/](desktop/))](#1-system-architecture)
  * [2. Authentication & Security Model ([server/src/vbide/auth/](server/src/vbide/auth/), [server/src/vbide/jail.py](server/src/vbide/jail.py))](#2-authentication--security-model)
  * [3. Agent-Change Timeline & History Store ([server/src/vbide/history/](server/src/vbide/history/))](#3-agent-change-timeline--history-store)
  * [4. Terminals & AI Agents ([builder/agent/](builder/agent/))](#4-terminals--ai-agents)
  * [5. App Testing: Window Streaming, Ports & Phone ([desktop/src-tauri/src/tunnel.rs](desktop/src-tauri/src/tunnel.rs), [server/src/vbide/tunnels.py](server/src/vbide/tunnels.py))](#5-app-testing-window-streaming-ports--phone)
  * [6. The Builder Image ([builder/Containerfile](builder/Containerfile))](#6-the-builder-image)
  * [7. Configuration (`vibebuilder.env`) & Commands ([vibebuilder.env.example](vibebuilder.env.example), [bin/vibebuilder](bin/vibebuilder))](#7-configuration-vibebuilderenv--commands)
  * [8. Repository Structure & End-to-End Test Suite ([server/tests/](server/tests/), [desktop/e2e/](desktop/e2e/))](#8-repository-structure--end-to-end-test-suite)
  * [9. Privacy, Agent Trust & Licensing ([LICENSE](LICENSE))](#9-privacy-agent-trust--licensing)

---

# Part 1 — Overview & Quick Start

## 🧠 What Is VibeBuilder IDE?

**VibeBuilder IDE** is a self-hosted remote IDE for people who code with AI agents. Your desktop (the one with the big CPU, the GPU and all your toolchains) does the work; your laptop just needs the small app.

It splits into three pieces:
1. **🖥️ The Server (`vb-server`)**: A hardened container that holds the sign-in, your files' change history and the only door to the internet. It never runs anything from your workspace.
2. **🧰 The Builder (`vb-builder`)**: An Arch Linux container with every common language and toolchain preinstalled. Claude Code, agy and your shells run here as `coder` with passwordless `sudo`, so agents can `pacman -S` whatever they need without touching your real system.
3. **💻 The Laptop App**: A VSCode-style workbench without the frills: folder tree, tabs, editor, find and folder search, diffs, and terminals at the bottom.

---

## 🔁 How It Works in 3 Steps

1. **Set Up the Desktop**: Copy `vibebuilder.env.example` to `vibebuilder.env`, then `vibebuilder install`, `build` and `start`. Put a Cloudflare Tunnel (or any HTTPS reverse proxy) in front of it.
2. **Pair Your Laptop**: Open the app, enter your server's address, run `vibebuilder pair` on the desktop and type the 6-character code (it lasts 30 seconds). Then sign in with your authenticator app's 6-digit code.
3. **Code & Review**: Open a project, start a Claude or agy terminal, and watch the **Changes** timeline fill up with exactly what the agent changed, file by file, ready to review, restore or undo.

---

## 📸 Visual Tour

### 🗂️ Workbench: Explorer, Editor & Terminals
<p align="center">
  <img src="screenshots/terminal_panel_clean.png" alt="Editor with a Claude terminal in the bottom panel" width="100%">
</p>

### 🔍 Agent-Change Timeline (Review)
<p align="center">
  <img src="screenshots/review_timeline_clean.png" alt="The Changes timeline showing an agent's edits as hunks" width="100%">
</p>

### ▶️ App Testing: Run App & Ports
<p align="center">
  <img src="screenshots/run_app_clean.png" alt="An app running in the builder, its window streamed to the laptop" width="49%">
  <img src="screenshots/ports_clean.png" alt="The Ports tab forwarding a dev server" width="49%">
</p>

### 🔐 Pairing & Sign-In
<p align="center">
  <img src="screenshots/sign_in_clean.png" alt="The pairing and sign-in screen" width="60%">
</p>

---

## ✨ Highlights at a Glance

* **🔍 Agent-Change Timeline**: Every burst of agent edits becomes a change set, shown file by file with only the changed lines and 3 lines of context, expandable to more context or the whole file. Restore one file or undo the whole set. Filter by "last 15 minutes", "last hour" or "today", or open any file's own history. Claude's edits are labelled exactly through an edit hook.
* **💾 Auto-Save That Stays Out of the Way**: Each changed file saves itself 3 minutes after its last change (a new change restarts the timer), plus a big orange **Save All** button (`Ctrl+Alt+S`). If an agent edits a file you have unsaved changes in, you choose: Keep mine, Take theirs or Compare.
* **🖥️ Terminals That Keep Running**: Claude, agy and shell terminals live in the builder and keep working while the app is closed. Reopening replays the scrollback.
* **▶️ Per-App Window Streaming**: **Run App** (`F5`) starts your app in the builder, and its windows, dialogs and popups open on your laptop as normal windows you can move and resize (Wayland apps: Qt, GTK/Tauri, SDL, raylib, GLFW). No full-desktop streaming.
* **🌐 Port Forwarding & Phone Testing**: Forward any dev server in the builder to `localhost` on the laptop with one click. A phone plugged into the laptop shows up in the builder's `adb devices`, so `./gradlew installDebug` just works.
* **🔐 Sign-In Before Anything**: Nothing but the sign-in screen answers until you're signed in: no file, no terminal, no health page. A paired device (at most 3) plus the current authenticator code, asked when the app opens.
* **🕰️ Rolling 10 GB History**: Every version of every changed file is kept, compressed. When it hits the cap, the files unchanged the longest lose their history first.
* **📦 Rebuilds Never Lose Your Tools**: Anything installed with pacman inside the builder is recorded and reinstalled automatically when the image is rebuilt.
* **⌨️ Familiar Keys**: `Ctrl+P` go to file, `Ctrl+F` / `Ctrl+H` find and replace, `Ctrl+Shift+F` folder search (ripgrep), `Ctrl+G` go to line, `` Ctrl+` `` terminal panel, `Ctrl+Alt+O` open folder, plus File / Edit / View / Go / Terminal / Help menus.

---

## 🚀 Quick Download & Installation

### 🖥️ Desktop Server (Linux, Rootless Podman)
You need Linux with **Podman** (rootless) and **systemd**. An NVIDIA GPU is optional (the builder gets it automatically when the NVIDIA Container Toolkit's CDI spec exists).
```bash
# 1. Clone the repository
git clone https://github.com/Todd0042/VibeBuilder-IDE-public.git
cd VibeBuilder-IDE-public

# 2. Your settings (at least VB_PUBLIC_URL)
cp vibebuilder.env.example vibebuilder.env
$EDITOR vibebuilder.env

# 3. Install, build (the first builder build downloads a lot: allow 20-40 min) and start
bin/vibebuilder install
bin/vibebuilder build
bin/vibebuilder start

# 4. Create your authenticator secret and scan the QR (it clears after 30 s)
bin/vibebuilder new-totp
bin/vibebuilder auth-qr
```
Then make `VB_PUBLIC_URL` reach `127.0.0.1:8765` over HTTPS. With Cloudflare Tunnel, see [deploy/cloudflared.example.yml](deploy/cloudflared.example.yml). Behind any other reverse proxy, set `VB_TRUST_CF=0`.

### 🐧 Laptop App: Linux AppImage
Download `VibeBuilder IDE_0.1.0_amd64.AppImage` from [GitHub Releases](https://github.com/Todd0042/VibeBuilder-IDE-public/releases):
```bash
chmod +x "VibeBuilder IDE_0.1.0_amd64.AppImage"
./"VibeBuilder IDE_0.1.0_amd64.AppImage"
```
It runs on Ubuntu 22.04 or newer and other distros from 2022 on (Debian 12+, Fedora, Mint, Pop!_OS, Arch...). Enter your server's address, then on the desktop run `bin/vibebuilder pair` and type the code. The app keeps its device token in your keychain (KWallet or GNOME Keyring). For app testing, also install `waypipe` and `android-tools`.

### 🛠️ Run the Laptop App from Source
```bash
git clone https://github.com/Todd0042/VibeBuilder-IDE-public.git
cd VibeBuilder-IDE-public
bin/vb-app            # checks for rust, nodejs/npm, webkit2gtk-4.1 and libsoup3; first run compiles (a few minutes)
bin/vb-app build      # or build your own AppImage (needs only Podman)
```
`bin/vb-app build` builds inside an Ubuntu 22.04 container ([deploy/appimage/Containerfile](deploy/appimage/Containerfile)), so the AppImage works on older distros too, not just on the one you built it on.
`bin/vb-app` also installs a "VibeBuilder IDE" launcher and icon, since Wayland takes a window's icon from its `.desktop` entry. If the clone has a `vibebuilder.env`, its `VB_PUBLIC_URL` becomes the app's default server.

---
---

# Part 2 — Technical Documentation & Architecture Reference

> *The sections below are an engineering reference for VibeBuilder IDE `v0.1.0`: how the pieces fit, what protects what, and every setting.*

---

## 1. System Architecture

The laptop app talks HTTPS and WebSockets to the server, and only the server talks to the builder, over a private Podman network.

```mermaid
flowchart LR
    subgraph Laptop
        APP["Laptop app<br/>Tauri 2 + Svelte 5<br/>CodeMirror 6 · xterm.js"]
        WP["waypipe client<br/>(app windows)"]
        ADB["adb server<br/>(plugged-in phone)"]
    end
    subgraph Desktop["Desktop (rootless Podman)"]
        SRV["vb-server<br/>FastAPI · sign-in · files<br/>search · history · tunnels"]
        BLD["vb-builder<br/>Arch Linux · claude · agy<br/>shells · git · toolchains"]
        WS[("workspace")]
        DATA[("server data<br/>secrets · history")]
    end
    APP -- "HTTPS / WSS<br/>(tunnel or reverse proxy)" --> SRV
    WP -. "rides the signed-in session" .- APP
    ADB -. "reverse tunnel" .- APP
    SRV -- "private network<br/>token-authenticated" --> BLD
    SRV --- WS
    BLD --- WS
    SRV --- DATA
```

* **vb-server** ([server/src/vbide/](server/src/vbide/)) holds everything that must stay out of the agents' reach: the authenticator secret, device tokens, sessions and the change history. It runs with a read-only root, every capability dropped and no new privileges, with the workspace mounted `nodev,nosuid,noexec`. It never runs git or anything from the workspace; git commands go to the builder.
* **vb-builder** ([builder/](builder/)) is the agents' box: a persistent container (your `sudo pacman` installs survive restarts) with `--userns=keep-id`, so `coder` inside is you on the host and "root" inside is an unprivileged host user. Its small agent ([builder/agent/vbagent/](builder/agent/vbagent/)) owns the terminals, runs git and opens tunnel endpoints, and it only accepts the server.
* **client-core** ([client-core/src/](client-core/src/)) is the shared TypeScript layer: the API client, sockets, Myers diff, fuzzy matching, auto-save and path helpers, written once for the laptop app and the planned phone app.

### Live Updates (`/api/v1/live`)
One WebSocket per app carries file changes, git status, change sets and terminal events, so the tree, open editors and the timeline update the moment an agent writes a file.

---

## 2. Authentication & Security Model

| | |
|---|---|
| Before sign-in | only `/api/v1/auth/pair` and `/api/v1/auth/login` answer; no docs, no health page |
| Authenticator | TOTP: only the code for the current 30-second step, and each code works once (no replay) |
| Pairing | `vibebuilder pair`: a QR plus a 6-character code, valid 30 s, single use, stored only as a hash |
| Devices | at most 3; the device token lives in the laptop's keychain; removing a device ends its session within seconds |
| Sessions | in memory only (a server restart signs everyone out); the app checks in every 2 minutes, and the server ends a session it hasn't heard from in 10 minutes |
| Failures | 5 per client address → 15-minute lockout; 30 across all addresses → pairing and login pause |
| Setup QR | shown in the terminal for 30 s, never written to disk |
| WebSockets | authenticate with their first message, so tokens never appear in URLs or logs; the Origin is checked |

### The Workspace Jail ([server/src/vbide/jail.py](server/src/vbide/jail.py))
Every file operation opens paths relative to the workspace with `openat2(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV)`. The kernel itself refuses `..`, symlinks (including ones an agent plants), `/proc` magic links and mount crossings. The end-to-end tests try all of these.

### Client Addresses Behind a Tunnel
With `VB_TRUST_CF=1` the lockouts use Cloudflare's `CF-Connecting-IP` header. Only turn this on when Cloudflare Tunnel is the sole way in (the server listens on `127.0.0.1` only); behind another proxy, a client could fake the header.

---

## 3. Agent-Change Timeline & History Store

* **Recording** ([history/recorder.py](server/src/vbide/history/recorder.py)): inotify watches the workspace. Each changed file is stored once it has settled (2 s), and edits that arrive close together (5 s of quiet ends a set) become one **change set**.
* **Attribution**: Claude Code reports each edit through a PostToolUse hook ([builder/agent/vb-edit-hook](builder/agent/vb-edit-hook)), so its changes are labelled exactly. Other changes are credited to whichever terminal was busy at the time.
* **Storage** ([history/store.py](server/src/vbide/history/store.py)): SQLite for the index, zstd-compressed blobs for file versions (Python 3.14's `compression.zstd`). Files over 4 MB are skipped.
* **The 10 GB cap**: when history passes `history_cap_bytes`, the files that have gone longest without a change lose their history first, so what you're actively working on keeps its full past.
* **Review** ([desktop/src/components/ReviewView.svelte](desktop/src/components/ReviewView.svelte)): hunks with 3 lines of context, "More context" and "Whole file", restore a file, or undo a whole set.

---

## 4. Terminals & AI Agents

* **Kinds**: `claude`, `agy`, `shell` (fish) and `run` (Run App). Terminals are real PTYs in the builder that keep running with no app attached; reattaching replays their scrollback.
* **Claude Code** is installed into the builder's home on first start, along with the edit hook. **agy** is used if it exists at `~/.local/bin/agy` on the desktop (mounted read-only). Agents run with `--dangerously-skip-permissions`: the container is the boundary, not a permission prompt.
* **Signing agents in**: sign in once in a builder shell. For agy, the builder has no keyring, so it keeps its token in a file in the builder's home.
* **New shells** greet you with a short, witty fastfetch ([builder/rootfs/etc/vibebuilder/](builder/rootfs/etc/vibebuilder/)).

---

## 5. App Testing: Window Streaming, Ports & Phone

All three ride the signed-in session (`/api/v1/tunnel`, `/api/v1/reverse`) and stop when you lock or close the app. The laptop only connects to targets it registered itself.

* **Run App** (`F5`): runs a command in the builder under `waypipe server`; the laptop runs the `waypipe` client, so each window, dialog and popup arrives as its own native window, scaled and resizable. Output goes to a ▶ terminal tab, and closing the tab stops the app. Wayland apps only (no X11). No audio yet.
* **Ports**: lists what's listening in the builder and forwards a port to `localhost` on the laptop (it picks another local port if that one is taken).
* **Phone**: the builder's `adb` uses the laptop's adb server through a reverse tunnel, so a phone plugged into the laptop is visible to Gradle and `adb` in the builder.

The laptop needs `waypipe` (windows) and `android-tools` (phone).

---

## 6. The Builder Image

Arch Linux (`base-devel`) with fish, and:

* **Python** (uv, ruff, pyright), **Node** (npm, pnpm, yarn, bun, deno), **Rust** (stable, plus Windows-gnu, wasm and Android targets), **Go**
* **C/C++**: GCC, Clang, CMake, Ninja, Meson, mingw-w64 (Windows builds)
* **JVM & Android**: JDK 21 and 17, Kotlin, Gradle, Android SDK (platforms 34–36, NDK 27.2 and 28.2)
* **GUI & games**: Qt 6/QML, GTK/WebKit (Tauri), SDL, raylib, GLFW, Vulkan
* **Media & testing**: ffmpeg, ImageMagick, Chromium and Xvfb (browser tests), waypipe
* **More**: Lua, Zig, Nix (single-user), gdb, lldb, valgrind, perf, git, gh, ripgrep, fd, fzf, jq

**Rebuilds.** A pacman hook writes every package you install to `/workspace/.vibebuilder/packages.txt`. `vibebuilder rebuild` builds a fresh image that reinstalls them, and the entrypoint reinstalls anything missing on start. Rebuilding ends running terminals (`claude -c` resumes a conversation).

**GPU.** `vibebuilder gpu-sync` turns NVIDIA's CDI spec into plain device and read-only file mounts ([bin/vb-gpu-sync](bin/vb-gpu-sync)), because Podman's CDI mounts don't work together with `keep-id`. Run it after a driver update.

---

## 7. Configuration (`vibebuilder.env`) & Commands

### `vibebuilder.env` ([vibebuilder.env.example](vibebuilder.env.example))

| Key | Default | What it does |
|---|---|---|
| `VB_PUBLIC_URL` | *(required)* | Where your devices reach the IDE; shown in the pairing QR and used as the laptop app's default server |
| `VB_WORKSPACE_DIR` | `~/vibebuilder-workspace` | The folder the IDE shows; agents can change anything in it |
| `VB_STATE_DIR` | `~/.local/share/vibebuilder` | Secrets, history, the builder's home, Nix store, pacman cache (must not overlap the workspace) |
| `VB_CONTAINER_STORAGE` | *(Podman's default)* | Put Podman's images on a bigger disk (written to `~/.config/containers/storage.conf` if it doesn't exist) |
| `VB_SERVER_PORT` | `8765` | The `127.0.0.1` port your tunnel or proxy forwards to |
| `VB_TRUST_CF` | `1` | Use `CF-Connecting-IP` for client addresses (Cloudflare Tunnel only; set `0` otherwise) |
| `VB_TOTP_ISSUER` | `VibeBuilder` | The name your authenticator app shows |
| `VB_BUILDER_MEMORY` / `VB_BUILDER_CPUS` | `16g` / all cores | Builder limits |
| `VB_APP_IDENTIFIER` | *(tauri.conf.json's)* | Laptop app: your own app id (keychain entry and saved settings belong to it) |

Changes take effect on `vibebuilder restart` (builder limits: on `vibebuilder rebuild`). No secrets go in this file: the authenticator secret, link token and device tokens are created by the commands below and stay in `VB_STATE_DIR`.

### Commands ([bin/vibebuilder](bin/vibebuilder))

```text
vibebuilder install          one-time setup: folders, link token, systemd units
vibebuilder build [what]     build images: builder | server | all
vibebuilder rebuild          fresh builder image (keeps your pacman installs), then restart it
vibebuilder start|stop|restart|status
vibebuilder logs [server|builder]
vibebuilder pair             pair a laptop or phone (QR + 30-second code)
vibebuilder devices          list paired devices;  vibebuilder revoke <id>
vibebuilder new-totp         make a new authenticator secret
vibebuilder auth-qr          show the authenticator QR for 30 s
vibebuilder history          change-history disk use
vibebuilder shell [root]     a shell in the builder (as coder, or root)
vibebuilder gpu-sync         after an NVIDIA driver update: refresh the builder's GPU files
```

---

## 8. Repository Structure & End-to-End Test Suite

```text
VibeBuilder-IDE/
├── server/                      # vb-server (FastAPI, Python 3.14)
│   ├── src/vbide/
│   │   ├── auth/                # TOTP, devices & pairing, sessions, lockouts, routes
│   │   ├── history/             # inotify recorder, SQLite + zstd store, diffs, routes
│   │   ├── jail.py              # openat2 workspace jail
│   │   ├── files.py             # read, write, rename, delete through the jail
│   │   ├── search.py            # ripgrep folder search
│   │   ├── agent_link.py        # the only client of the builder agent (terminals, git)
│   │   ├── tunnels.py           # port, reverse and window tunnels for app testing
│   │   ├── live.py              # the live-update WebSocket hub
│   │   └── cli.py               # vbide pair / devices / revoke / auth-qr / new-totp
│   ├── tests/                   # end-to-end: a real server + builder agent on a throwaway workspace
│   └── Containerfile
├── builder/                     # vb-builder image
│   ├── Containerfile            # Arch + toolchains + Android SDK + Nix
│   ├── rootfs/                  # entrypoint, pacman hook, fish greeting, fastfetch
│   └── agent/                   # vbagent: PTY terminals, git, tunnel endpoints; vb-edit-hook
├── client-core/                 # shared TypeScript: API client, sockets, diff, fuzzy, auto-save
├── desktop/                     # laptop app (Tauri 2 + Svelte 5)
│   ├── src/                     # components, commands & menus, editor, terminals, testing
│   ├── src-tauri/               # Rust: keychain, tunnels, waypipe, adb
│   └── e2e/                     # the real UI in Chromium against a real server
├── deploy/                      # Podman quadlet template, systemd unit, cloudflared example
├── bin/                         # vibebuilder, vb-app, vb-builder-create, vb-gpu-sync
└── vibebuilder.env.example      # every machine-specific setting
```

### Running the End-to-End Test Suite
```bash
cd server && uv venv .venv && uv pip install -p .venv -e '.[test]' -e ../builder/agent playwright
.venv/bin/playwright install chromium
.venv/bin/pytest -q                  # server + builder agent: auth, jail escapes, history, restore, search, terminals, tunnels
.venv/bin/pytest -q ../desktop/e2e   # the real UI in Chromium: first run, pairing, sign-in, editing, review, menus
```
The same suite runs on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

---

## 9. Privacy, Agent Trust & Licensing

### 🔒 1. Your Code Stays Home
* VibeBuilder IDE has **no analytics, no telemetry and no accounts**. Your files, history and terminals stay on your desktop; the only outside connection is the tunnel or proxy you set up. (The AI agents you run talk to their own providers, as they would anywhere.)

### 🤖 2. Know What You're Giving the Agents
* Agents run with full rights **inside the builder**: passwordless `sudo`, and no permission prompts. The container keeps them off your real system, but they can change or delete anything in your workspace. The change history lets you undo what they did, within its 10 GB. Keep secrets out of the workspace.

### ⚖️ 3. Software License & Commercial Inquiries
* **Non-Commercial Use**: VibeBuilder IDE is licensed for personal, hobbyist, educational and other non-commercial use under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.
* **Commercial Licensing Inquiries**: Commercial use (inside a company, as a paid service, or bundled into a product) is not permitted under this license. To ask about a separate commercial license, reach out to **[todd.0042.git@gmail.com](mailto:todd.0042.git@gmail.com)**.
* **Third-Party Open-Source Attributions**: Tauri (MIT/Apache-2.0), Svelte (MIT), CodeMirror (MIT), xterm.js (MIT), FastAPI (MIT), Uvicorn (BSD-3-Clause), pyotp (MIT), segno (BSD-3-Clause), waypipe (MIT), ripgrep (MIT/Unlicense) and the packages in each `package.json` and `pyproject.toml` keep their own licenses. Claude Code and agy are their vendors' products, installed under their own terms.

---

<p align="center">
  If VibeBuilder IDE makes your coding setup better, consider supporting development:<br/><br/>
  <a href="https://ko-fi.com/todd0042" target="_blank">
    <img src="https://img.shields.io/badge/☕_Support_VibeBuilder_IDE_on_Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Support on Ko-fi">
  </a>
</p>

---

<p align="center">
  <a href="https://ko-fi.com/todd0042">
    <img src="https://raw.githubusercontent.com/Todd0042/creator-assets/main/banners/todd_creator_banner_v2.0.png" alt="Support Todd on Ko-fi" width="100%" />
  </a>
</p>
