# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for POST /api/admin/uploads/image: admin-only, content-type/size
validated, never trusts the client's own filename."""

import uuid

from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.models.user import User

# A minimal valid 1x1 transparent PNG.
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a4944415478da6360000002000155e59fdb0000000049454e44ae426082"
)


async def _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, *, is_admin: bool) -> dict:
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=is_admin))
    await db_session.flush()
    token = make_access_token(sub=str(sub))
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_upload_image(db_session, api_client, make_access_token, rsa_keypair, monkeypatch, tmp_path):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: Settings(uploads_dir=str(tmp_path))
    try:
        resp = await api_client.post(
            "/api/admin/uploads/image",
            headers=headers,
            files={"file": ("my-photo.png", _PNG_BYTES, "image/png")},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 200
    assert resp.json()["url"].startswith("http")
    saved = list(tmp_path.iterdir())
    assert len(saved) == 1
    assert saved[0].suffix == ".png"
    assert saved[0].stem != "my-photo"  # never trusts the client's own filename


async def test_unsupported_content_type_rejected(db_session, api_client, make_access_token, rsa_keypair, monkeypatch, tmp_path):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: Settings(uploads_dir=str(tmp_path))
    try:
        resp = await api_client.post(
            "/api/admin/uploads/image",
            headers=headers,
            files={"file": ("evil.svg", b"<svg></svg>", "image/svg+xml")},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 415


async def test_oversized_upload_rejected(db_session, api_client, make_access_token, rsa_keypair, monkeypatch, tmp_path):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    fastapi_app.dependency_overrides[get_settings] = lambda: Settings(uploads_dir=str(tmp_path))
    try:
        oversized = b"0" * (5 * 1024 * 1024 + 1)
        resp = await api_client.post(
            "/api/admin/uploads/image",
            headers=headers,
            files={"file": ("big.png", oversized, "image/png")},
        )
    finally:
        fastapi_app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 413
    assert list(tmp_path.iterdir()) == []


async def test_non_admin_forbidden(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=False)

    resp = await api_client.post(
        "/api/admin/uploads/image", headers=headers, files={"file": ("x.png", _PNG_BYTES, "image/png")}
    )

    assert resp.status_code == 403


async def test_no_token_unauthorized(api_client):
    resp = await api_client.post(
        "/api/admin/uploads/image", files={"file": ("x.png", _PNG_BYTES, "image/png")}
    )
    assert resp.status_code in (401, 403)
