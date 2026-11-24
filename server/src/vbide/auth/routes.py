"""/api/v1/auth: the only endpoints that answer without a session are /pair and /login."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from pydantic import BaseModel, Field

from ..services import Services, services
from .devices import DeviceLimit
from .sessions import Session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def client_ip(request_or_ws) -> str:
    svc: Services = request_or_ws.app.state.svc
    mode = svc.settings.proxy_mode
    if mode == "cloudflare":
        cf = request_or_ws.headers.get("cf-connecting-ip", "").strip()
        if cf:
            return cf[:64]
    elif mode == "forwarded":
        # Take the rightmost value appended by our local reverse proxy (Caddy, Nginx, Tailscale Funnel),
        # never the leftmost value that a client can spoof in X-Forwarded-For.
        xff = request_or_ws.headers.get("x-forwarded-for", "")
        if xff:
            last = xff.rsplit(",", 1)[-1].strip()
            if last:
                return last[:64]
        real_ip = request_or_ws.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip[:64]
    return (request_or_ws.client.host if request_or_ws.client else "unknown")[:64]


def _bearer(request: Request) -> str:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h[:7].lower() == "bearer " else ""


def require_session(request: Request) -> Session:
    svc = services(request)
    s = svc.sessions.get(_bearer(request))
    if not s or not svc.devices.exists(s.device_id):
        if s:
            svc.sessions.end(s.key)
        raise HTTPException(401, "Not signed in")
    svc.sessions.activity(s)  # any request from the app (its 2-minute ping included) keeps it alive
    return s


SessionDep = Annotated[Session, Depends(require_session)]


async def ws_session(ws: WebSocket) -> Session | None:
    """Accept, check Origin, then expect {"type":"auth","session":...} within 5 s. The token is never in
    the URL (URLs end up in logs). Returns None after closing the socket if anything is wrong."""
    svc: Services = ws.app.state.svc
    origin = ws.headers.get("origin")
    if origin is not None and origin not in svc.settings.allowed_origins:
        await ws.close(code=4403)
        return None
    await ws.accept()
    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), 5))
        s = svc.sessions.get(str(first.get("session", ""))) if first.get("type") == "auth" else None
    except Exception as exc:
        logging.getLogger("vbide.auth").debug("WebSocket auth failed: %s", exc)
        s = None
    if not s or not svc.devices.exists(s.device_id):
        await ws.close(code=4401)
        return None
    return s


class PairBody(BaseModel):
    code: str = Field(max_length=16)
    device_name: str = Field(default="", max_length=80)


class LoginBody(BaseModel):
    device_token: str = Field(max_length=256)
    code: str = Field(max_length=12)


def _check_guard(svc: Services, ip: str) -> None:
    wait = svc.guard.blocked(ip)
    if wait:
        raise HTTPException(429, f"Too many failed attempts. Try again in {wait // 60 + 1} min.")


@router.post("/pair")
def pair(body: PairBody, request: Request) -> dict:
    svc, ip = services(request), client_ip(request)
    _check_guard(svc, ip)
    try:
        got = svc.devices.redeem_pair_code(body.code, body.device_name, ip)
    except DeviceLimit as exc:
        raise HTTPException(409, str(exc))
    if not got:
        svc.guard.fail(ip)
        raise HTTPException(401, "That code is wrong or expired. Codes last 30 seconds; use the one showing now.")
    dev, token = got
    return {"device_id": dev.id, "device_name": dev.name, "device_token": token}


@router.post("/login")
def login(body: LoginBody, request: Request) -> dict:
    svc, ip = services(request), client_ip(request)
    _check_guard(svc, ip)
    dev = svc.devices.find_by_token(body.device_token)
    if dev is None:
        svc.guard.fail(ip)
        raise HTTPException(401, "This device isn't paired (or was removed). Pair it again.")
    if not svc.totp.verify(body.code):
        svc.guard.fail(ip)
        raise HTTPException(401, "Wrong or already-used code. Wait for the next one and try again.")
    svc.guard.succeed(ip)
    svc.devices.touch(dev.id, ip)
    token = svc.sessions.create(dev.id)
    return {"session": token, "idle_timeout_sec": svc.settings.session_idle_sec, "device_id": dev.id,
            "device_name": dev.name}


@router.post("/logout")
def logout(s: SessionDep, request: Request) -> dict:
    services(request).sessions.end(s.key)
    return {"ok": True}


@router.post("/ping")
def ping(s: SessionDep, request: Request) -> dict:
    return {"idle_remaining_sec": services(request).sessions.remaining(s)}


@router.get("/devices")
def list_devices(s: SessionDep, request: Request) -> dict:
    svc = services(request)
    return {"max": svc.settings.max_devices, "devices": [
        {"id": d.id, "name": d.name, "created": d.created, "last_seen": d.last_seen, "last_ip": d.last_ip,
         "current": d.id == s.device_id} for d in svc.devices.list()]}


@router.delete("/devices/{device_id}")
def revoke_device(device_id: str, s: SessionDep, request: Request) -> dict:
    svc = services(request)
    if not svc.devices.revoke(device_id):
        raise HTTPException(404, "No such device")
    svc.sessions.end_device(device_id)
    return {"ok": True}
