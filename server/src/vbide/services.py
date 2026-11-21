"""The server's parts, built once at startup and reached from routes as request.app.state.svc."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from .agent_link import AgentLink
    from .auth.devices import DeviceStore
    from .auth.guard import Guard
    from .auth.sessions import SessionStore
    from .auth.totp import Totp
    from .checkpoints import Checkpointer
    from .problems import Problems
    from .config import Settings
    from .history.recorder import Recorder
    from .history.store import HistoryStore
    from .jail import Jail
    from .live import LiveHub


@dataclass
class Services:
    settings: "Settings"
    jail: "Jail"
    totp: "Totp"
    devices: "DeviceStore"
    sessions: "SessionStore"
    guard: "Guard"
    live: "LiveHub"
    history: "HistoryStore"
    recorder: "Recorder"
    agent: "AgentLink"
    checkpoints: "Checkpointer"
    problems: "Problems"


def services(request: "Request") -> Services:
    return request.app.state.svc
