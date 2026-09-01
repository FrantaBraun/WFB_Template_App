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


async def test_nav_list_only_published_and_shown(db_session, api_client):
    # Presence/absence of this test's own rows, not exact-set equality -
    # db_session only isolates what THIS test writes, not other already-
    # committed rows in the shared dev database (e.g. real content created
    # while manually exercising the admin UI).
    shown = Page(heading="O projektu", slug="o-projektu", content="", status="published", show_in_nav=True)
    hidden = Page(heading="Hidden", slug="hidden-page", content="", status="published", show_in_nav=False)
    draft = Page(heading="Draft", slug="draft-nav-page", content="", status="draft", show_in_nav=True)
    db_session.add_all([shown, hidden, draft])
    await db_session.flush()

    resp = await api_client.get("/api/pages/")

    assert resp.status_code == 200
    slugs = {item["slug"] for item in resp.json()}
    assert "o-projektu" in slugs
    assert "hidden-page" not in slugs
    assert "draft-nav-page" not in slugs
