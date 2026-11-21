"""The ASGI app. Run with: uvicorn vbide.app:app --host 0.0.0.0 --port 8765

Nothing is served before sign-in except /api/v1/auth/pair and /api/v1/auth/login: no docs, no
OpenAPI, no health page (an unknown path and an unsigned request both get the same 401/404).
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import agent_link, files, live, search, tunnels
from .agent_link import AgentLink
from .auth import routes as auth_routes
from .auth.devices import DeviceStore
from .auth.guard import Guard
from .auth.sessions import SessionStore
from .auth.totp import Totp
from .config import Settings
from .history import routes as history_routes
from .history.recorder import Recorder
from .history.store import HistoryStore
from .jail import Jail
from .live import LiveHub
from .services import Services

MAX_BODY = 12 * 1024 * 1024


def build_services(settings: Settings) -> Services:
    settings.secrets_dir.mkdir(parents=True, exist_ok=True)
    jail = Jail(settings.workspace)
    hub = LiveHub()
    history = HistoryStore(settings.history_dir, settings.history_cap_bytes)
    agent = AgentLink(settings.agent_url, settings.read_secret(settings.agent_token_file))
    recorder = Recorder(jail, history, settle_sec=settings.file_settle_sec, quiet_sec=settings.changeset_quiet_sec,
                        max_file_bytes=settings.history_max_file_bytes, attribute=agent.attribute, emit=hub.publish)
    return Services(
        settings=settings, jail=jail, totp=Totp(settings.read_secret(settings.totp_secret_file)),
        devices=DeviceStore(settings.auth_db, settings.pair_dir, settings.max_devices, settings.pair_code_ttl_sec),
        sessions=SessionStore(settings.session_idle_sec), guard=Guard(
            settings.max_failures_per_ip, settings.lockout_sec, settings.max_global_failures),
        live=hub, history=history, recorder=recorder, agent=agent)


def create_app(settings: Settings | None = None, svc: Services | None = None) -> FastAPI:
    settings = settings or Settings()
    svc = svc or build_services(settings)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        svc.live.bind(asyncio.get_running_loop())
        svc.recorder.start()

        async def sweeper() -> None:
            while True:  # idle sessions, and devices removed with `vibebuilder revoke`, are cut off quickly
                await asyncio.sleep(5)
                svc.sessions.sweep()
                for dev in svc.sessions.device_ids():
                    if not svc.devices.exists(dev):
                        svc.sessions.end_device(dev)

        task = asyncio.create_task(sweeper())
        yield
        task.cancel()
        svc.recorder.stop()

    app = FastAPI(title="VibeBuilder-IDE", version="1", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.state.svc = svc
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-VB-Background"], max_age=600)

    @app.middleware("http")
    async def limits_and_headers(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    for r in (auth_routes.router, files.router, search.router, history_routes.router, agent_link.router,
              live.router, tunnels.router):
        app.include_router(r)
    return app


def openapi_schema() -> dict:
    """For generating the apps' typed client (scripts/gen-client): built offline, never served."""
    from fastapi.openapi.utils import get_openapi

    app = FastAPI()
    for r in (auth_routes.router, files.router, search.router, history_routes.router, agent_link.router):
        app.include_router(r)
    return get_openapi(title="VibeBuilder-IDE", version="1", routes=app.routes)


def __getattr__(name: str):  # `uvicorn vbide.app:app` builds the app lazily, so imports stay cheap
    if name == "app":
        return create_app()
    raise AttributeError(name)
