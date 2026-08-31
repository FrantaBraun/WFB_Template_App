# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/admin/articles: admin-only CRUD, id-keyed, sanitizing
full_text on write and 409ing on a duplicate slug."""

import uuid
from datetime import date

from app.models.article import Article
from app.models.user import User


async def _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, *, is_admin: bool) -> dict:
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=is_admin))
    await db_session.flush()
    token = make_access_token(sub=str(sub))
    return {"Authorization": f"Bearer {token}"}


async def test_admin_can_create_list_and_edit_article(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    create_resp = await api_client.post(
        "/api/admin/articles/",
        headers=headers,
        json={
            "title": "Podzimní čtení",
            "slug": "podzimni-cteni",
            "short_description": "Krátký popis",
            "full_text": "<p>Text</p>",
            "event_date": str(date.today()),
        },
    )
    assert create_resp.status_code == 201
    article_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "draft"
    assert create_resp.json()["pinned"] is False

    list_resp = await api_client.get("/api/admin/articles/", headers=headers)
    assert list_resp.status_code == 200
    assert any(a["id"] == article_id for a in list_resp.json())

    patch_resp = await api_client.patch(
        f"/api/admin/articles/{article_id}", headers=headers, json={"status": "published", "pinned": True}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "published"
    assert patch_resp.json()["pinned"] is True
    assert patch_resp.json()["title"] == "Podzimní čtení"  # untouched fields preserved


async def test_soft_delete_via_status(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    article = Article(title="X", slug="soft-delete-me", event_date=date.today(), status="published")
    db_session.add(article)
    await db_session.flush()

    resp = await api_client.patch(
        f"/api/admin/articles/{article.id}", headers=headers, json={"status": "deleted"}
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


async def test_full_text_is_sanitized_on_create(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    resp = await api_client.post(
        "/api/admin/articles/",
        headers=headers,
        json={
            "title": "X",
            "slug": "sanitize-me",
            "full_text": '<img src=x onerror="alert(1)"><p>ok</p>',
            "event_date": str(date.today()),
        },
    )

    assert resp.status_code == 201
    assert "onerror" not in resp.json()["full_text"]
    assert "<p>ok</p>" in resp.json()["full_text"]


async def test_duplicate_slug_returns_409(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    db_session.add(Article(title="Existing", slug="dup-article", event_date=date.today(), status="draft"))
    await db_session.flush()

    resp = await api_client.post(
        "/api/admin/articles/",
        headers=headers,
        json={"title": "New", "slug": "dup-article", "event_date": str(date.today())},
    )

    assert resp.status_code == 409


async def test_invalid_slug_rejected(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)

    resp = await api_client.post(
        "/api/admin/articles/",
        headers=headers,
        json={"title": "X", "slug": "Not A Slug!", "event_date": str(date.today())},
    )

    assert resp.status_code == 422


async def test_non_admin_forbidden(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=False)

    resp = await api_client.get("/api/admin/articles/", headers=headers)

    assert resp.status_code == 403


async def test_no_token_unauthorized(api_client):
    resp = await api_client.get("/api/admin/articles/")
    assert resp.status_code in (401, 403)
