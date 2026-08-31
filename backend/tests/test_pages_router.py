# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the public GET /api/pages/{slug} route: only ever serves a
published page, and a draft's slug 404s the same as an unknown one."""

from app.models.page import Page


async def test_published_page_returns_200(db_session, api_client):
    page = Page(heading="O projektu", slug="o-projektu", content="<p>Ahoj</p>", status="published")
    db_session.add(page)
    await db_session.flush()

    resp = await api_client.get("/api/pages/o-projektu")

    assert resp.status_code == 200
    assert resp.json()["heading"] == "O projektu"


async def test_draft_page_returns_404(db_session, api_client):
    page = Page(heading="Draft", slug="draft-page", content="", status="draft")
    db_session.add(page)
    await db_session.flush()

    resp = await api_client.get("/api/pages/draft-page")

    assert resp.status_code == 404


async def test_unknown_slug_returns_404(api_client):
    resp = await api_client.get("/api/pages/does-not-exist")
    assert resp.status_code == 404
