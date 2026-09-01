# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/admin/pages: admin-only CRUD, id-keyed, sanitizing
content on write and 409ing on a duplicate slug."""

import uuid

from app.models.page import Page
from app.models.user import User


async def _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, *, is_admin: bool) -> dict:
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=is_admin))
    await db_session.flush()
    token = make_access_token(sub=str(sub))
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_create_list_and_edit_page(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    create_resp = await api_client.post(
        "/api/admin/pages/",
        headers=headers,
        json={"heading": "O projektu", "slug": "o-projektu", "content": "<p>Ahoj</p>"},
    )
    assert create_resp.status_code == 201
    page_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "draft"

    list_resp = await api_client.get("/api/admin/pages/", headers=headers)
    assert list_resp.status_code == 200
    assert any(p["id"] == page_id for p in list_resp.json())

    patch_resp = await api_client.patch(
        f"/api/admin/pages/{page_id}", headers=headers, json={"status": "published"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "published"
    assert patch_resp.json()["heading"] == "O projektu"  # untouched fields preserved


async def test_content_is_sanitized_on_create(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    resp = await api_client.post(
        "/api/admin/pages/",
        headers=headers,
        json={"heading": "X", "slug": "x-page", "content": '<img src=x onerror="alert(1)"><p>ok</p>'},
    )

    assert resp.status_code == 201
    assert "onerror" not in resp.json()["content"]
    assert "<p>ok</p>" in resp.json()["content"]


async def test_duplicate_slug_returns_409(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    db_session.add(Page(heading="Existing", slug="dup-slug", content="", status="draft"))
    await db_session.flush()

    resp = await api_client.post(
        "/api/admin/pages/", headers=headers, json={"heading": "New", "slug": "dup-slug", "content": ""}
    )

    assert resp.status_code == 409


async def test_invalid_slug_rejected(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    resp = await api_client.post(
        "/api/admin/pages/", headers=headers, json={"heading": "X", "slug": "Not A Slug!", "content": ""}
    )

    assert resp.status_code == 422


async def test_reserved_slug_rejected(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    """A page slug matching a real app route (e.g. "login") would render at
    root level and silently lose to React Router's static route - reject it
    at save time instead of letting an admin create an unreachable page."""
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    resp = await api_client.post(
        "/api/admin/pages/", headers=headers, json={"heading": "X", "slug": "login", "content": ""}
    )

    assert resp.status_code == 422


async def test_non_admin_forbidden(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=False)

    resp = await api_client.get("/api/admin/pages/", headers=headers)

    assert resp.status_code == 403


async def test_no_token_unauthorized(api_client):
    resp = await api_client.get("/api/admin/pages/")
    assert resp.status_code in (401, 403)
