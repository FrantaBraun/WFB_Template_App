# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for what the portfolio module accepts when an administrator
creates or edits an item - required Czech texts, length limits, the http(s)
URL rule, tag limits, status - plus the small pure helpers behind slugs and
languages (app.modules.portfolio.service).

Same setup as test_modules_portfolio_router.py: a throwaway FastAPI app with
just this module's router, ASGITransport, and a rolled-back db_session whose
table is emptied inside the transaction first (the migration seeds rows)."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import get_db
from app.models.user import User
from app.modules.portfolio import service
from app.modules.portfolio.models import PortfolioItem
from app.modules.portfolio.router import router as portfolio_router

BASE = "/api/modules/portfolio"

_app = FastAPI()
_app.include_router(portfolio_router, prefix=BASE)

VALID = {"title_cs": "Projekt", "summary_cs": "Popis."}


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch):
    await db_session.execute(delete(PortfolioItem))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


async def _post(client, admin, **fields):
    return await client.post(f"{BASE}/manage/items", json={**VALID, **fields}, headers=admin)


async def _created(client, admin, **fields) -> dict:
    resp = await _post(client, admin, **fields)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _patch(client, admin, item: dict, **fields):
    return await client.patch(f"{BASE}/manage/items/{item['id']}", json=fields, headers=admin)


async def _count(client, admin) -> int:
    return len((await client.get(f"{BASE}/manage/items", headers=admin)).json())


# --- Required Czech texts ------------------------------------------------------


@pytest.mark.parametrize("missing", ["title_cs", "summary_cs"])
async def test_the_czech_title_and_summary_are_required(client, admin, missing):
    body = {k: v for k, v in VALID.items() if k != missing}

    resp = await client.post(f"{BASE}/manage/items", json=body, headers=admin)

    assert resp.status_code == 422
    assert await _count(client, admin) == 0


@pytest.mark.parametrize("field", ["title_cs", "summary_cs"])
@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
async def test_a_blank_czech_title_or_summary_is_refused(client, admin, field, blank):
    assert (await _post(client, admin, **{field: blank})).status_code == 422


@pytest.mark.parametrize("field", ["title_cs", "summary_cs"])
async def test_the_czech_title_and_summary_cannot_be_blanked_or_nulled_by_a_patch(client, admin, field):
    item = await _created(client, admin)

    assert (await _patch(client, admin, item, **{field: ""})).status_code == 422
    assert (await _patch(client, admin, item, **{field: "   "})).status_code == 422
    assert (await _patch(client, admin, item, **{field: None})).status_code == 422
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json() == item


async def test_the_english_texts_are_optional_and_may_be_cleared(client, admin):
    item = await _created(client, admin, title_en="English", summary_en="Summary.", description_en="Text.")

    cleared = (await _patch(client, admin, item, title_en="", summary_en="", description_en="")).json()

    assert (cleared["title_en"], cleared["summary_en"], cleared["description_en"]) == ("", "", "")


@pytest.mark.parametrize(
    "field",
    ["slug", "title_cs", "title_en", "summary_cs", "summary_en", "description_cs", "description_en", "status", "tags", "published", "sort_order"],
)
async def test_nothing_but_the_url_can_be_set_to_null(client, admin, field):
    item = await _created(client, admin, slug="nic")

    resp = await _patch(client, admin, item, **{field: None})

    assert resp.status_code == 422
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json() == item


async def test_surrounding_whitespace_is_trimmed(client, admin):
    item = await _created(
        client, admin, title_cs="  Projekt  ", summary_cs="\tPopis.\n", title_en=" Project ", description_cs="\n\nText.\n\n"
    )

    assert (item["title_cs"], item["summary_cs"], item["title_en"], item["description_cs"]) == (
        "Projekt",
        "Popis.",
        "Project",
        "Text.",
    )


async def test_windows_line_breaks_in_a_description_become_plain_ones(client, admin):
    item = await _created(client, admin, description_cs="Jedna.\r\n\r\nDvě,\r\nřádek.\rTři.")

    assert item["description_cs"] == "Jedna.\n\nDvě,\nřádek.\nTři."


async def test_a_nul_character_is_a_422_not_a_server_error(client, admin):
    for field in ("title_cs", "summary_cs", "description_en", "url"):
        resp = await _post(client, admin, **{field: "a\x00b"})
        assert resp.status_code == 422, field
    assert (await _post(client, admin, tags=["a\x00b"])).status_code == 422


# --- Lengths -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("title_cs", 120),
        ("title_en", 120),
        ("summary_cs", 400),
        ("summary_en", 400),
        ("description_cs", 8000),
        ("description_en", 8000),
    ],
)
async def test_text_limits_are_enforced_exactly(client, admin, field, limit):
    ok = await _post(client, admin, slug="presne", **{field: "ž" * limit})
    too_long = await _post(client, admin, slug="moc", **{field: "ž" * (limit + 1)})

    assert ok.status_code == 201
    assert ok.json()[field] == "ž" * limit
    assert too_long.status_code == 422


async def test_the_url_limit_is_500_characters(client, admin):
    ok_url = "https://example.com/" + "a" * (500 - len("https://example.com/"))
    assert len(ok_url) == 500

    assert (await _post(client, admin, slug="ok-url", url=ok_url)).status_code == 201
    assert (await _post(client, admin, slug="long-url", url=ok_url + "a")).status_code == 422


async def test_limits_apply_to_a_patch_too(client, admin):
    item = await _created(client, admin)

    assert (await _patch(client, admin, item, title_cs="x" * 121)).status_code == 422
    assert (await _patch(client, admin, item, summary_en="x" * 401)).status_code == 422
    assert (await _patch(client, admin, item, description_cs="x" * 8001)).status_code == 422


# --- URL -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        " javascript:alert(1)//https://example.com",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "mailto:me@example.com",
        "/portfolio/x",
        "//example.com/x",
        "example.com",
        "www.example.com",
        "http://",
        "https:///path",
        "http:example.com",
        "https://exa mple.com",
        "https://example.com/a b",
        "https://example.com/\nsecond",
        "https://[::1",
    ],
)
async def test_only_absolute_http_and_https_urls_are_accepted(client, admin, url):
    resp = await _post(client, admin, slug="odkaz", url=url)

    assert resp.status_code == 422, url
    assert await _count(client, admin) == 0


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://example.com",
        "HTTPS://EXAMPLE.COM/Path",
        "https://sub.example.com:8443/a/b?c=d&e=f#g",
        "https://example.com/čeština",
        "http://localhost:5173",
        "http://127.0.0.1:8000/x",
        "https://[::1]:8080/",
    ],
)
async def test_valid_web_urls_are_accepted_as_sent(client, admin, url):
    item = await _created(client, admin, slug="odkaz", url=url)

    assert item["url"] == url


async def test_a_blank_url_means_no_url(client, admin):
    assert (await _created(client, admin, slug="a-prazdne", url=""))["url"] is None
    assert (await _created(client, admin, slug="b-mezery", url="   "))["url"] is None
    assert (await _created(client, admin, slug="c-null", url=None))["url"] is None


async def test_the_url_is_trimmed(client, admin):
    assert (await _created(client, admin, url="  https://example.com  "))["url"] == "https://example.com"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com", "/relative", "example.com"])
async def test_a_patch_cannot_set_a_bad_url_and_leaves_the_old_one(client, admin, url):
    item = await _created(client, admin, url="https://example.com")

    resp = await _patch(client, admin, item, url=url)

    assert resp.status_code == 422
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json()["url"] == "https://example.com"


# --- Tags ----------------------------------------------------------------------


async def test_ten_tags_are_allowed_and_eleven_are_not(client, admin):
    ten = [f"tag{n}" for n in range(10)]

    assert (await _created(client, admin, slug="deset", tags=ten))["tags"] == ten
    assert (await _post(client, admin, slug="jedenact", tags=ten + ["tag10"])).status_code == 422


async def test_a_tag_may_be_40_characters_and_not_more(client, admin):
    assert (await _created(client, admin, slug="ctyricet", tags=["t" * 40]))["tags"] == ["t" * 40]
    assert (await _post(client, admin, slug="jednactyricet", tags=["t" * 41])).status_code == 422


async def test_tags_are_trimmed_and_blanks_and_repeats_dropped_keeping_the_order(client, admin):
    item = await _created(client, admin, tags=["  React ", "", "   ", "FastAPI", "react", "REACT", "Tailwind CSS"])

    assert item["tags"] == ["React", "FastAPI", "Tailwind CSS"]


async def test_the_limits_are_checked_on_the_cleaned_tags(client, admin):
    eleven_but_one_blank_and_one_repeat = [f"t{n}" for n in range(9)] + ["", "t0"]

    item = await _created(client, admin, tags=eleven_but_one_blank_and_one_repeat)

    assert len(item["tags"]) == 9


@pytest.mark.parametrize("tags", ["React", [1, 2], [["a"]], {"a": 1}, [None]])
async def test_tags_must_be_a_list_of_strings(client, admin, tags):
    assert (await _post(client, admin, tags=tags)).status_code == 422


async def test_tag_limits_apply_to_a_patch(client, admin):
    item = await _created(client, admin, tags=["A"])

    assert (await _patch(client, admin, item, tags=[f"t{n}" for n in range(11)])).status_code == 422
    assert (await _patch(client, admin, item, tags=["x" * 41])).status_code == 422
    assert (await client.get(f"{BASE}/manage/items/{item['id']}", headers=admin)).json()["tags"] == ["A"]


async def test_tags_with_diacritics_and_symbols_are_kept(client, admin):
    item = await _created(client, admin, tags=["C++", "Čeština", ".NET"])

    assert item["tags"] == ["C++", "Čeština", ".NET"]


# --- Status, flags, sort order -------------------------------------------------


@pytest.mark.parametrize("status", ["live", "in_preparation"])
async def test_both_statuses_are_accepted(client, admin, status):
    assert (await _created(client, admin, status=status))["status"] == status


@pytest.mark.parametrize("status", ["", "draft", "LIVE", "in preparation", 1])
async def test_an_unknown_status_is_refused(client, admin, status):
    assert (await _post(client, admin, status=status)).status_code == 422


@pytest.mark.parametrize("sort_order", [-1, 1_000_001, "abc", 1.5])
async def test_an_invalid_sort_order_is_refused(client, admin, sort_order):
    assert (await _post(client, admin, sort_order=sort_order)).status_code == 422


async def test_published_must_be_a_boolean(client, admin):
    assert (await _post(client, admin, published="maybe")).status_code == 422


async def test_a_body_that_is_not_json_is_a_422(client, admin):
    resp = await client.post(f"{BASE}/manage/items", content=b"not json", headers={**admin, "Content-Type": "application/json"})

    assert resp.status_code == 422


# --- Helpers -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (None, "cs"),
        ("", "cs"),
        ("cs", "cs"),
        ("cs-CZ", "cs"),
        ("en", "en"),
        ("en-GB", "en"),
        ("en_US", "en"),
        ("EN-us", "en"),
        ("fr", "cs"),
        ("-", "cs"),
    ],
)
def test_resolve_language(language, expected):
    assert service.resolve_language(language) == expected


@pytest.mark.parametrize(
    ("language", "cs", "en", "expected"),
    [
        ("cs", "česky", "english", "česky"),
        ("en", "česky", "english", "english"),
        ("en", "česky", "", "česky"),
        ("en", "česky", "  ", "česky"),
        ("cs", "", "english", "english"),
        ("cs", "", "", ""),
        ("en", "", "", ""),
    ],
)
def test_pick(language, cs, en, expected):
    assert service.pick(language, cs, en) == expected


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("My Application", "my-application"),
        ("  Spaces   and --- dashes  ", "spaces-and-dashes"),
        ("Příliš žluťoučký kůň", "prilis-zlutoucky-kun"),
        ("Łódź, Øresund & Straße", "lodz-oresund-strasse"),
        ("ÀÉÎÕÜ ñ ç", "aeiou-n-c"),
        ("C++ / C#", "c-c"),
        ("2026 Plan", "2026-plan"),
        ("★★★", ""),
        ("", ""),
        ("x" * 200, "x" * 80),
        ("ab " * 40, ("ab-" * 27)[:80].strip("-")),
    ],
)
def test_slugify(text, slug):
    assert service.slugify(text) == slug
    assert len(slug) <= 80


def test_base_slug_prefers_english_then_czech_then_a_placeholder():
    assert service.base_slug("English", "Česky") == "english"
    assert service.base_slug("", "Česky") == "cesky"
    assert service.base_slug("★", "Česky") == "cesky"
    assert service.base_slug("a", "Česky") == "cesky"  # one letter is below the slug minimum
    assert service.base_slug("★", "★") == "item"
