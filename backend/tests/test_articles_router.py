# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the public articles routes: GET /api/articles/dashboard's three
group filters (upcoming/pinned/recent_past), and GET /api/articles/{slug}."""

import uuid
from datetime import date, timedelta

from app.models.article import Article

TODAY = date.today()


def _slug() -> str:
    return f"a-{uuid.uuid4().hex[:10]}"


def _article(**overrides) -> Article:
    defaults = dict(
        title="Title",
        slug=_slug(),
        short_description="desc",
        full_text="",
        event_date=TODAY,
        status="published",
        pinned=False,
    )
    defaults.update(overrides)
    return Article(**defaults)


async def test_dashboard_upcoming_picks_soonest_future_or_today(db_session, api_client):
    todays = _article(event_date=TODAY)
    later = _article(event_date=TODAY + timedelta(days=10))
    past = _article(event_date=TODAY - timedelta(days=1))
    draft_soon = _article(event_date=TODAY + timedelta(days=1), status="draft")
    db_session.add_all([todays, later, past, draft_soon])
    await db_session.flush()

    resp = await api_client.get("/api/articles/dashboard")

    assert resp.status_code == 200
    assert resp.json()["upcoming"]["slug"] == todays.slug


async def test_dashboard_upcoming_respects_display_window(db_session, api_client):
    db_session.add(_article(event_date=TODAY + timedelta(days=1), display_from=TODAY + timedelta(days=5)))
    await db_session.flush()

    resp = await api_client.get("/api/articles/dashboard")

    assert resp.status_code == 200
    assert resp.json()["upcoming"] is None


async def test_dashboard_upcoming_pinned_collision_excluded_from_pinned_list(db_session, api_client):
    headline = _article(event_date=TODAY + timedelta(days=1), pinned=True)
    other_pinned = _article(event_date=TODAY - timedelta(days=1), pinned=True)
    db_session.add_all([headline, other_pinned])
    await db_session.flush()

    resp = await api_client.get("/api/articles/dashboard")

    body = resp.json()
    assert body["upcoming"]["slug"] == headline.slug
    pinned_slugs = [a["slug"] for a in body["pinned"]]
    assert headline.slug not in pinned_slugs
    assert other_pinned.slug in pinned_slugs


async def test_dashboard_pinned_excludes_out_of_window_and_orders_newest_first(db_session, api_client):
    older = _article(event_date=TODAY - timedelta(days=5), pinned=True)
    newer = _article(event_date=TODAY - timedelta(days=1), pinned=True)
    out_of_window = _article(
        event_date=TODAY - timedelta(days=2), pinned=True, display_to=TODAY - timedelta(days=10)
    )
    not_pinned = _article(event_date=TODAY - timedelta(days=3), pinned=False)
    db_session.add_all([older, newer, out_of_window, not_pinned])
    await db_session.flush()

    resp = await api_client.get("/api/articles/dashboard")

    slugs = [a["slug"] for a in resp.json()["pinned"]]
    assert slugs == [newer.slug, older.slug]


async def test_dashboard_recent_past_caps_at_5_picks_newest(db_session, api_client):
    articles = [_article(event_date=TODAY - timedelta(days=i)) for i in range(1, 8)]
    db_session.add_all(articles)
    await db_session.flush()

    resp = await api_client.get("/api/articles/dashboard")

    slugs = [a["slug"] for a in resp.json()["recent_past"]]
    expected = [a.slug for a in sorted(articles, key=lambda a: a.event_date, reverse=True)[:5]]
    assert slugs == expected


async def test_dashboard_recent_past_excludes_pinned_future_draft_and_out_of_window(db_session, api_client):
    valid = _article(event_date=TODAY - timedelta(days=1))
    pinned = _article(event_date=TODAY - timedelta(days=1), pinned=True)
    future = _article(event_date=TODAY + timedelta(days=1))
    draft = _article(event_date=TODAY - timedelta(days=1), status="draft")
    out_of_window = _article(event_date=TODAY - timedelta(days=1), display_to=TODAY - timedelta(days=5))
    db_session.add_all([valid, pinned, future, draft, out_of_window])
    await db_session.flush()

    resp = await api_client.get("/api/articles/dashboard")

    assert [a["slug"] for a in resp.json()["recent_past"]] == [valid.slug]


async def test_get_article_by_slug_published_returns_200(db_session, api_client):
    article = _article()
    db_session.add(article)
    await db_session.flush()

    resp = await api_client.get(f"/api/articles/{article.slug}")

    assert resp.status_code == 200
    assert resp.json()["title"] == "Title"


async def test_get_article_by_slug_draft_returns_404(db_session, api_client):
    article = _article(status="draft")
    db_session.add(article)
    await db_session.flush()

    resp = await api_client.get(f"/api/articles/{article.slug}")

    assert resp.status_code == 404


async def test_calendar_filters_month_status_and_window(db_session, api_client):
    # A far-future month, and presence/absence of this test's own slugs
    # rather than exact-set equality - robust against whatever else may
    # already be in the shared dev database (see test_pages_router.py's
    # nav-list test for the same rationale).
    year, month = 2031, 6
    in_month = _article(event_date=date(year, month, 15))
    other_month = _article(event_date=date(year, month, 1) - timedelta(days=1))
    draft_in_month = _article(event_date=date(year, month, 10), status="draft")
    out_of_window = _article(event_date=date(year, month, 20), display_to=TODAY - timedelta(days=1))
    db_session.add_all([in_month, other_month, draft_in_month, out_of_window])
    await db_session.flush()

    resp = await api_client.get("/api/articles/calendar", params={"year": year, "month": month})

    assert resp.status_code == 200
    slugs = {a["slug"] for a in resp.json()}
    assert in_month.slug in slugs
    assert other_month.slug not in slugs
    assert draft_in_month.slug not in slugs
    assert out_of_window.slug not in slugs


async def test_calendar_invalid_month_rejected(api_client):
    resp = await api_client.get("/api/articles/calendar", params={"year": 2031, "month": 13})
    assert resp.status_code == 422


async def test_search_matches_title(db_session, api_client):
    unique = _slug()
    article = _article(title=f"Unikátní {unique}", event_date=date(2031, 6, 15))
    draft = _article(title=f"Unikátní draft {unique}", status="draft")
    db_session.add_all([article, draft])
    await db_session.flush()

    resp = await api_client.get("/api/articles/search", params={"q": unique})

    assert resp.status_code == 200
    slugs = {a["slug"] for a in resp.json()}
    assert article.slug in slugs
    assert draft.slug not in slugs


async def test_search_matches_short_description(db_session, api_client):
    unique = _slug()
    article = _article(short_description=f"Popis {unique}", event_date=date(2031, 6, 16))
    db_session.add(article)
    await db_session.flush()

    resp = await api_client.get("/api/articles/search", params={"q": unique})

    assert resp.status_code == 200
    assert article.slug in {a["slug"] for a in resp.json()}


async def test_search_matches_date_in_either_format(db_session, api_client):
    article = _article(event_date=date(2031, 6, 17))
    db_session.add(article)
    await db_session.flush()

    cz_resp = await api_client.get("/api/articles/search", params={"q": "17.06.2031"})
    iso_resp = await api_client.get("/api/articles/search", params={"q": "2031-06-17"})

    assert article.slug in {a["slug"] for a in cz_resp.json()}
    assert article.slug in {a["slug"] for a in iso_resp.json()}


async def test_search_requires_non_empty_query(api_client):
    resp = await api_client.get("/api/articles/search", params={"q": ""})
    assert resp.status_code == 422


async def test_get_article_by_slug_ignores_display_window(db_session, api_client):
    """Direct-link access doesn't re-check display_from/display_to - that
    governs listing visibility, not whether a known link still works."""
    article = _article(display_to=TODAY - timedelta(days=30))
    db_session.add(article)
    await db_session.flush()

    resp = await api_client.get(f"/api/articles/{article.slug}")

    assert resp.status_code == 200
