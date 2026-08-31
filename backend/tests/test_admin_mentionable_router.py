# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for GET /api/admin/mentionable: admin-only, combined Page+Article
list including drafts, backing the WYSIWYG editor's @-mention suggestions."""

import uuid
from datetime import date

from app.models.article import Article
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


async def test_includes_pages_and_articles_of_any_status(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=True)
    db_session.add_all([
        Page(heading="Draft Page", slug="draft-page-m", content="", status="draft"),
        Article(title="Draft Article", slug="draft-article-m", event_date=date.today(), status="draft"),
    ])
    await db_session.flush()

    resp = await api_client.get("/api/admin/mentionable/", headers=headers)

    assert resp.status_code == 200
    types_and_slugs = {(item["type"], item["slug"]) for item in resp.json()}
    assert ("page", "draft-page-m") in types_and_slugs
    assert ("article", "draft-article-m") in types_and_slugs


async def test_non_admin_forbidden(db_session, api_client, make_access_token, rsa_keypair, monkeypatch):
    headers = await _admin_headers(db_session, make_access_token, rsa_keypair, monkeypatch, is_admin=False)

    resp = await api_client.get("/api/admin/mentionable/", headers=headers)

    assert resp.status_code == 403


async def test_no_token_unauthorized(api_client):
    resp = await api_client.get("/api/admin/mentionable/")
    assert resp.status_code in (401, 403)
