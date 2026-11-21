"""`vbide` commands, run inside the server container (the host `vibebuilder` script calls them):

  vbide pair            show a pairing QR + short code; a new one every 30 s until Ctrl+C
  vbide devices         list paired devices
  vbide revoke ID       remove a device (it's signed out within seconds)
  vbide auth-qr         show the authenticator setup QR for 30 s (never written to disk)
  vbide set-totp        read a secret on stdin and store it (moving the old IDE's secret over)
  vbide new-totp        make a new authenticator secret, then show its QR
  vbide history-usage   how much space the change history uses
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from urllib.parse import urlsplit

import pyotp
import segno

from .auth.devices import DeviceStore, format_pair_code
from .config import Settings

CLEAR = "\x1b[2J\x1b[H"


def _devices(s: Settings) -> DeviceStore:
    return DeviceStore(s.auth_db, s.pair_dir, s.max_devices, s.pair_code_ttl_sec)


def _qr(text: str) -> None:
    segno.make(text, error="m").terminal(compact=True, border=2)


def cmd_pair(s: Settings) -> int:
    if not s.public_url:
        print("VB_PUBLIC_URL isn't set (vibebuilder.env), so the pairing QR has no address to point at.")
        return 1
    store = _devices(s)
    if len(store.list()) >= s.max_devices:
        print(f"Already {s.max_devices} devices paired; remove one first (vibebuilder devices / revoke).")
        return 1
    try:
        while True:
            code, expires = store.new_pair_code()
            print(CLEAR, end="")
            print("Pair a device with VibeBuilder-IDE\n")
            _qr(json.dumps({"vb": 1, "u": s.public_url, "c": code}, separators=(",", ":")))
            print(f"\n  Phone: scan the QR in the app.   Laptop: type this code:  {format_pair_code(code)}\n")
            before = len(store.list())
            while time.time() < expires:
                left = int(expires - time.time()) + 1
                print(f"\r  New code in {left:2d}s   (Ctrl+C to stop)", end="", flush=True)
                time.sleep(0.5)
                if len(store.list()) > before:
                    print(CLEAR + f"Paired: {store.list()[-1].name}")
                    store.clear_pair_code()
                    return 0
    except KeyboardInterrupt:
        store.clear_pair_code()
        print(CLEAR + "Stopped. No pairing code is active.")
        return 0


def cmd_devices(s: Settings) -> int:
    devs = _devices(s).list()
    if not devs:
        print("No devices paired. Run: vibebuilder pair")
    for d in devs:
        seen = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.last_seen))
        print(f"{d.id}  {d.name:<24} last used {seen}  from {d.last_ip or '-'}")
    print(f"\n{len(devs)} of {s.max_devices} devices.")
    return 0


def cmd_revoke(s: Settings, device_id: str) -> int:
    ok = _devices(s).revoke(device_id)
    print("Removed." if ok else "No device with that id.")
    return 0 if ok else 1


def _write_secret(s: Settings, secret: str) -> None:
    s.secrets_dir.mkdir(parents=True, exist_ok=True)
    tmp = s.totp_secret_file.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(secret + "\n")
    os.replace(tmp, s.totp_secret_file)


def cmd_auth_qr(s: Settings) -> int:
    secret = s.read_secret(s.totp_secret_file)
    if not secret:
        print("No authenticator secret yet. Run: vibebuilder new-totp")
        return 1
    uri = pyotp.TOTP(secret).provisioning_uri(name=f"coder@{urlsplit(s.public_url).hostname or 'vibebuilder'}", issuer_name=s.totp_issuer)
    try:
        print(CLEAR + "Scan with your authenticator app (clears in 30 s):\n")
        _qr(uri)
        for left in range(30, 0, -1):
            print(f"\r  Clearing in {left:2d}s ", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    print(CLEAR + "Cleared.")
    return 0


def cmd_set_totp(s: Settings) -> int:
    secret = sys.stdin.read().strip().replace(" ", "").upper()
    try:
        pyotp.TOTP(secret).now()
    except Exception:
        print("That isn't a valid authenticator secret.")
        return 1
    _write_secret(s, secret)
    print("Stored. Restart the server to use it.")
    return 0


def cmd_new_totp(s: Settings) -> int:
    if s.read_secret(s.totp_secret_file) and "--replace" not in sys.argv:
        print("A secret exists already (your phone uses it). Add --replace to make a new one.")
        return 1
    _write_secret(s, pyotp.random_base32(32))
    print("New secret stored. Restart the server, then scan:")
    return cmd_auth_qr(s)


def cmd_history_usage(s: Settings) -> int:
    from .history.store import HistoryStore
    u = HistoryStore(s.history_dir, s.history_cap_bytes).usage()
    gb = 1024 ** 3
    print(f"{u['stored_bytes'] / gb:.2f} GB of {u['cap_bytes'] / gb:.0f} GB used; {u['versions']} versions, "
          f"{u['blobs']} stored contents.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="vbide")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("pair", "devices", "auth-qr", "set-totp", "new-totp", "history-usage"):
        sp = sub.add_parser(name)
        if name == "new-totp":
            sp.add_argument("--replace", action="store_true")
    sub.add_parser("revoke").add_argument("device_id")
    sub.add_parser("agent-token")
    a = p.parse_args()
    s = Settings()
    if a.cmd == "agent-token":  # used once by the installer
        print(secrets.token_urlsafe(32))
        return 0
    return {"pair": lambda: cmd_pair(s), "devices": lambda: cmd_devices(s), "revoke": lambda: cmd_revoke(s, a.device_id),
            "auth-qr": lambda: cmd_auth_qr(s), "set-totp": lambda: cmd_set_totp(s),
            "new-totp": lambda: cmd_new_totp(s), "history-usage": lambda: cmd_history_usage(s)}[a.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
