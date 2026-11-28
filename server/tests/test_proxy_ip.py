"""Tests for VB_PROXY / legacy VB_TRUST_CF configuration and proxy client_ip resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from vbide.auth.routes import client_ip
from vbide.config import Settings


def _fake_request(mode: str, headers: dict[str, str], host: str = "127.0.0.1"):
    settings = Settings(proxy_mode=mode)
    svc = SimpleNamespace(settings=settings)
    app = SimpleNamespace(state=SimpleNamespace(svc=svc))
    low_headers = {k.lower(): v for k, v in headers.items()}
    return SimpleNamespace(app=app, headers=low_headers, client=SimpleNamespace(host=host))


def test_proxy_mode_env_and_legacy_fallback(monkeypatch):
    monkeypatch.delenv("VB_PROXY", raising=False)
    monkeypatch.delenv("VB_TRUST_CF", raising=False)
    assert Settings().proxy_mode == "none"

    monkeypatch.setenv("VB_TRUST_CF", "1")
    assert Settings().proxy_mode == "cloudflare"

    monkeypatch.setenv("VB_TRUST_CF", "0")
    assert Settings().proxy_mode == "none"

    # Explicit VB_PROXY takes precedence over legacy VB_TRUST_CF.
    monkeypatch.setenv("VB_PROXY", "forwarded")
    monkeypatch.setenv("VB_TRUST_CF", "1")
    assert Settings().proxy_mode == "forwarded"

    monkeypatch.setenv("VB_PROXY", "bogus")
    with pytest.raises(ValueError, match="Unknown VB_PROXY"):
        Settings()


def test_client_ip_none_ignores_proxy_headers():
    req = _fake_request(
        "none",
        {"CF-Connecting-IP": "198.51.100.5", "X-Forwarded-For": "198.51.100.6", "X-Real-IP": "198.51.100.7"},
        host="127.0.0.1",
    )
    assert client_ip(req) == "127.0.0.1"


def test_client_ip_cloudflare_reads_cf_header():
    req = _fake_request(
        "cloudflare",
        {"CF-Connecting-IP": "203.0.113.42", "X-Forwarded-For": "198.51.100.9"},
        host="127.0.0.1",
    )
    assert client_ip(req) == "203.0.113.42"


def test_client_ip_forwarded_uses_rightmost_xff_and_rejects_spoof():
    # Client sent spoofed leftmost XFF "9.9.9.9"; local reverse proxy appended real peer "198.51.100.25".
    req = _fake_request(
        "forwarded",
        {"CF-Connecting-IP": "1.1.1.1", "X-Forwarded-For": "9.9.9.9, 198.51.100.25"},
        host="127.0.0.1",
    )
    assert client_ip(req) == "198.51.100.25"

    req_real_ip = _fake_request("forwarded", {"X-Real-IP": "198.51.100.30"}, host="127.0.0.1")
    assert client_ip(req_real_ip) == "198.51.100.30"


def test_cf_login_and_web_serving(tmp_path):
    from fastapi.testclient import TestClient
    from vbide.app import create_app

    ws = tmp_path / "github"
    ws.mkdir()
    (ws / "demo").mkdir()
    (ws / "demo" / "README.md").write_text("# Demo\n")

    # Under default totp mode, /cf-login is disabled (404).
    import pyotp

    d1_sec = tmp_path / "d1" / "secrets"
    d1_sec.mkdir(parents=True)
    (d1_sec / "totp_secret").write_text(pyotp.random_base32())
    (d1_sec / "agent_token").write_text("tok123")
    totp_app = create_app(
        Settings(
            workspace=ws,
            data_dir=tmp_path / "d1",
            agent_token_file=d1_sec / "agent_token",
            auth_mode="totp",
            serve_web=False,
        )
    )
    with TestClient(totp_app) as c:
        assert c.post("/api/v1/auth/cf-login").status_code == 404

    # Under cloudflare mode, CF Access header issues a working session and serves web UI.
    cf_app = create_app(
        Settings(workspace=ws, data_dir=tmp_path / "d2", proxy_mode="cloudflare", auth_mode="cloudflare")
    )
    with TestClient(cf_app) as c:
        root_r = c.get("/")
        assert root_r.status_code == 200
        assert "<title>" in root_r.text.lower()

        r = c.post(
            "/api/v1/auth/cf-login",
            headers={"CF-Connecting-IP": "203.0.113.5", "Cf-Access-Authenticated-User-Email": "todd@example.com"},
        )
        assert r.status_code == 200
        tok = r.json()["session"]
        assert r.json()["device_name"] == "todd@example.com"

        r_files = c.get("/api/v1/projects", headers={"Authorization": f"Bearer {tok}"})
        assert r_files.status_code == 200
        assert "demo" in r_files.text
