# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Moderation through the boards endpoints: the check before publishing, the
risk confirmation, blocked accounts, and the administrators' /manage side
(finding and blocking posts, strikes, machine rules).

Same setup as test_modules_boards_router.py: the module's router on a
throwaway app, ASGITransport, and boards tables emptied inside each test's
rolled-back transaction."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.database import get_db
from app.models.user import User
from app.modules.boards.config import BoardsConfig, ModerationConfig, get_config
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.moderation.ai import AiFinding, AiReviewResult, MockAiModerator, get_ai_moderator
from app.modules.boards.moderation.topic import build_rules
from app.modules.boards.router import router as boards_router
from app.modules.notifications.models import Notification

BASE = "/api/modules/boards"
MANAGE = f"{BASE}/manage"

_app = FastAPI()
_app.include_router(boards_router, prefix=BASE)

CLEAN = "Attention is the only thing we spend that we can never earn back."
WARN_TEXT = "This is bullshit"  # 35 %
RISK_TEXT = "This is bullshit, shit"  # 58 %
BLOCK_TEXT = "I will kill you tomorrow"  # 80 %

RICH_RULES = build_rules(
    "Philosophy of everyday life",
    "Short thoughts on how we live, decide and doubt. Reflections about habits, choices, meaning, "
    "happiness, friendship and time. No quotes, only your own words.",
)
SPARSE_RULES = build_rules("Technology", "What will software do to us next?")
ON_TOPIC = (
    "Our daily habits shape the meaning we find in life; friendship and time teach us to doubt "
    "our choices, and happiness often hides in ordinary decisions we make without thinking about them."
)
OFF_TOPIC = (
    "The new graphics card renders frames faster than the previous generation, with better ray tracing, "
    "more memory bandwidth and improved driver support for modern games and engines, while consuming "
    "less power under typical gaming load conditions."
)


@pytest.fixture()
def ai():
    return MockAiModerator()


@pytest.fixture(autouse=True)
async def _overrides(db_session, rsa_keypair, monkeypatch, ai):
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20)
    _app.dependency_overrides[get_ai_moderator] = lambda: ai
    yield
    _app.dependency_overrides.clear()


def _use_config(**moderation):
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=20, moderation=ModerationConfig(**moderation))


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


class Person:
    def __init__(self, user: User, token: str):
        self.user = user
        self.headers = {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_person(db_session, make_access_token):
    async def _make(**fields) -> Person:
        sub = uuid.uuid4()
        user = User(auth_sub=sub, **fields)
        db_session.add(user)
        await db_session.commit()
        return Person(user, make_access_token(sub=str(sub)))

    return _make


@pytest.fixture()
async def alice(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def bob(make_person) -> Person:
    return await make_person()


@pytest.fixture()
async def admin(make_person) -> Person:
    return await make_person(is_admin=True)


async def _category(db_session, person, slug="general", rules=None, title=None) -> Category:
    category = Category(
        title=title or slug,
        slug=slug,
        description="About " + slug,
        created_by_id=person.user.id,
        machine_rules=rules,
        machine_rules_source="algorithm" if rules else None,
    )
    db_session.add(category)
    await db_session.commit()
    return category


async def _post(db_session, person, category, title="p", **fields) -> Post:
    post = Post(category_id=category.id, author_id=person.user.id, title=title, body=f"Body of {title}", **fields)
    db_session.add(post)
    await db_session.commit()
    return post


async def _count(db_session, model=Post) -> int:
    return await db_session.scalar(select(func.count()).select_from(model))


def _payload(body=CLEAN, title="A title", **extra):
    return {"title": title, "body": body, **extra}


async def _publish(client, person, slug="general", **payload):
    return await client.post(f"{BASE}/categories/{slug}/posts", json=_payload(**payload), headers=person.headers)


# --- The check before publishing a post ---------------------------------------


async def test_checking_a_draft_needs_a_login(client, alice, db_session):
    await _category(db_session, alice)
    resp = await client.post(f"{BASE}/categories/general/posts/check", json=_payload())
    assert resp.status_code == 401


async def test_checking_a_draft_in_a_missing_category_is_a_404(client, alice):
    resp = await client.post(f"{BASE}/categories/nope/posts/check", json=_payload(), headers=alice.headers)
    assert resp.status_code == 404


async def test_a_clean_draft_checks_out(client, alice, db_session):
    await _category(db_session, alice)

    resp = await client.post(f"{BASE}/categories/general/posts/check", json=_payload(), headers=alice.headers)

    assert resp.status_code == 200
    assert resp.json() == {
        "level": "ok",
        "violation": {"percent": 0, "level": "ok"},
        "topic": None,  # the category has no machine rules
        "findings": [],
    }


async def test_a_draft_check_reports_the_aspects_behind_the_score(client, alice, db_session):
    await _category(db_session, alice)

    resp = await client.post(
        f"{BASE}/categories/general/posts/check", json=_payload(WARN_TEXT), headers=alice.headers
    )

    body = resp.json()
    assert (body["level"], body["violation"]) == ("warn", {"percent": 35, "level": "warn"})
    assert body["findings"] == [{"code": "profanity", "aspect": "violation", "matches": ["bullshit"]}]


async def test_a_draft_check_never_writes_anything(client, alice, db_session):
    await _category(db_session, alice)

    for text in (CLEAN, WARN_TEXT, RISK_TEXT, BLOCK_TEXT):
        await client.post(f"{BASE}/categories/general/posts/check", json=_payload(text), headers=alice.headers)

    assert await _count(db_session) == 0


async def test_a_draft_check_includes_the_topic_when_the_category_has_rules(client, alice, db_session):
    await _category(db_session, alice, rules=RICH_RULES)

    on = await client.post(f"{BASE}/categories/general/posts/check", json=_payload(ON_TOPIC), headers=alice.headers)
    off = await client.post(f"{BASE}/categories/general/posts/check", json=_payload(OFF_TOPIC), headers=alice.headers)

    assert on.json()["topic"] == {"percent": 0, "level": "ok"}
    assert off.json()["topic"]["level"] == "blocked"
    assert off.json()["level"] == "blocked"
    (finding,) = off.json()["findings"]
    assert (finding["code"], finding["aspect"]) == ("off_topic", "topic")


# --- Publishing a post --------------------------------------------------------


async def test_a_clean_post_is_published_with_its_scores_stored(client, alice, db_session):
    category = await _category(db_session, alice)

    resp = await _publish(client, alice)

    assert resp.status_code == 201
    post = (await db_session.scalars(select(Post).where(Post.category_id == category.id))).one()
    assert (post.status, post.violation_score, post.topic_mismatch_score) == ("published", 0, 0)
    assert post.assessment == {"violation": 0, "topic": None, "ai_reviewed": False, "findings": []}


async def test_a_post_with_a_warning_is_published_and_the_findings_are_kept_for_admins(client, alice, db_session):
    await _category(db_session, alice)

    resp = await _publish(client, alice, body=WARN_TEXT)

    assert resp.status_code == 201
    post = (await db_session.scalars(select(Post))).one()
    assert post.violation_score == 35
    assert post.assessment["findings"] == [{"code": "profanity", "aspect": "violation", "matches": ["bullshit"]}]


async def test_a_risky_post_needs_the_authors_confirmation(client, alice, db_session):
    await _category(db_session, alice)

    first = await _publish(client, alice, body=RISK_TEXT)

    assert first.status_code == 409
    detail = first.json()["detail"]
    assert detail["code"] == "confirmation_required"
    assert detail["assessment"]["level"] == "risk"
    assert detail["assessment"]["findings"][0]["code"] == "profanity"
    assert await _count(db_session) == 0

    confirmed = await _publish(client, alice, body=RISK_TEXT, confirm_risk=True)

    assert confirmed.status_code == 201
    assert (await db_session.scalars(select(Post))).one().violation_score == 58


async def test_a_post_above_the_block_threshold_is_not_published_whatever_the_author_confirms(
    client, alice, db_session
):
    await _category(db_session, alice)

    for confirm in (False, True):
        resp = await _publish(client, alice, body=BLOCK_TEXT, confirm_risk=confirm)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["code"] == "moderation_blocked"
        assert detail["assessment"]["level"] == "blocked"
        assert detail["assessment"]["findings"][0] == {"code": "threat", "aspect": "violation", "matches": ["i will kill you"]}

    assert await _count(db_session) == 0


async def test_the_title_is_checked_too(client, alice, db_session):
    await _category(db_session, alice)
    resp = await _publish(client, alice, title="I will kill you", body=CLEAN)
    assert resp.status_code == 422


async def test_thresholds_come_from_the_configuration(client, alice, db_session):
    await _category(db_session, alice)
    _use_config(warn_percent=5, risk_percent=10, block_percent=30)

    assert (await _publish(client, alice, body=WARN_TEXT)).status_code == 422  # 35 % > 30 %


# --- Topic --------------------------------------------------------------------


async def test_an_on_topic_post_is_published_with_a_zero_topic_score(client, alice, db_session):
    await _category(db_session, alice, rules=RICH_RULES)

    resp = await _publish(client, alice, body=ON_TOPIC)

    assert resp.status_code == 201
    assert (await db_session.scalars(select(Post))).one().topic_mismatch_score == 0


async def test_a_long_off_topic_post_in_a_well_described_category_is_not_published(client, alice, db_session):
    await _category(db_session, alice, rules=RICH_RULES)

    resp = await _publish(client, alice, body=OFF_TOPIC)

    assert resp.status_code == 422
    assessment = resp.json()["detail"]["assessment"]
    assert (assessment["violation"]["level"], assessment["topic"]["level"]) == ("ok", "blocked")
    assert assessment["findings"][0]["code"] == "off_topic"
    assert await _count(db_session) == 0


async def test_a_sparse_category_only_advises_never_blocks(client, alice, db_session):
    await _category(db_session, alice, rules=SPARSE_RULES)

    resp = await _publish(client, alice, body=OFF_TOPIC)

    assert resp.status_code == 201
    assert (await db_session.scalars(select(Post))).one().topic_mismatch_score > 0


async def test_clearing_the_rules_switches_the_topic_check_off(client, alice, admin, db_session):
    await _category(db_session, alice, rules=RICH_RULES)
    assert (await _publish(client, alice, body=OFF_TOPIC)).status_code == 422

    await client.put(f"{MANAGE}/categories/general/rules", json={"keywords": [], "notes": ""}, headers=admin.headers)

    assert (await _publish(client, alice, body=OFF_TOPIC)).status_code == 201


# --- Machine rules and the check on a new category ----------------------------


async def test_a_new_category_gets_algorithmic_machine_rules(client, alice, db_session):
    resp = await client.post(
        f"{BASE}/categories",
        json={"title": "Philosophy of everyday life", "description": "Habits, choices, meaning and time."},
        headers=alice.headers,
    )

    assert resp.status_code == 201
    category = (await db_session.scalars(select(Category))).one()
    assert category.machine_rules_source == "algorithm"
    assert category.machine_rules_updated_at is not None
    terms = [k["term"] for k in category.machine_rules["keywords"]]
    assert terms[:3] == ["philosophy", "everyday", "life"] and "habits" in terms
    assert category.violation_score == 0


async def test_the_new_rules_then_govern_posts_in_that_category(client, alice, db_session):
    await client.post(
        f"{BASE}/categories",
        json={
            "title": "Philosophy of everyday life",
            "description": "Short thoughts on how we live, decide and doubt. Reflections about habits, choices, "
            "meaning, happiness, friendship and time.",
        },
        headers=alice.headers,
    )

    assert (await _publish(client, alice, "philosophy-of-everyday-life", body=ON_TOPIC)).status_code == 201
    assert (await _publish(client, alice, "philosophy-of-everyday-life", body=OFF_TOPIC)).status_code == 422


async def test_a_category_is_checked_like_a_post_but_without_a_topic(client, alice):
    clean = await client.post(
        f"{BASE}/categories/check", json={"title": "Everyday life", "description": "Short thoughts"}, headers=alice.headers
    )
    rude = await client.post(
        f"{BASE}/categories/check", json={"title": "Shit board", "description": WARN_TEXT}, headers=alice.headers
    )

    assert clean.json() == {"level": "ok", "violation": {"percent": 0, "level": "ok"}, "topic": None, "findings": []}
    assert rude.json()["level"] == "risk" and rude.json()["topic"] is None


async def test_checking_a_category_needs_a_login_and_writes_nothing(client, alice, db_session):
    anonymous = await client.post(f"{BASE}/categories/check", json={"title": "T", "description": "D"})
    await client.post(f"{BASE}/categories/check", json={"title": "T", "description": "D"}, headers=alice.headers)

    assert anonymous.status_code == 401
    assert await _count(db_session, Category) == 0


async def test_a_violating_category_is_not_created(client, alice, db_session):
    payload = {"title": "Kill yourself club", "description": "For people to kill yourself"}

    resp = await client.post(f"{BASE}/categories", json=payload, headers=alice.headers)

    assert resp.status_code == 422
    assert resp.json()["detail"]["assessment"]["findings"][0]["code"] == "threat"
    assert await _count(db_session, Category) == 0


async def test_a_risky_category_needs_confirmation_and_keeps_its_score(client, alice, db_session):
    payload = {"title": "Bullshit and shit", "description": "Just a board"}

    first = await client.post(f"{BASE}/categories", json=payload, headers=alice.headers)
    confirmed = await client.post(f"{BASE}/categories", json={**payload, "confirm_risk": True}, headers=alice.headers)

    assert (first.status_code, confirmed.status_code) == (409, 201)
    assert first.json()["detail"]["code"] == "confirmation_required"
    assert (await db_session.scalars(select(Category))).one().violation_score == 58


async def test_ai_machine_rules_replace_the_algorithmic_ones_when_enabled(client, alice, db_session, ai):
    _use_config(ai_review_enabled=True)
    ai.rules = {"keywords": [{"term": "Wisdom", "weight": 2.5}], "notes": "About practical wisdom"}

    await client.post(f"{BASE}/categories", json={"title": "Thinking", "description": "Thoughts"}, headers=alice.headers)

    category = (await db_session.scalars(select(Category))).one()
    assert category.machine_rules_source == "ai"
    assert category.machine_rules == {"keywords": [{"term": "Wisdom", "weight": 2.5}], "notes": "About practical wisdom"}
    assert list(ai.rules_requests) == [("Thinking", "Thoughts")]


@pytest.mark.parametrize("bad_rules", [{"keywords": "none"}, {"keywords": [{"term": "x", "weight": 99}]}, {"nonsense": 1}])
async def test_unusable_ai_machine_rules_leave_the_algorithmic_ones(client, alice, db_session, ai, bad_rules):
    _use_config(ai_review_enabled=True)
    ai.rules = bad_rules

    resp = await client.post(
        f"{BASE}/categories", json={"title": "Thinking", "description": "Thoughts"}, headers=alice.headers
    )

    assert resp.status_code == 201
    assert (await db_session.scalars(select(Category))).one().machine_rules_source == "algorithm"


async def test_ai_rules_are_not_asked_for_while_ai_review_is_off(client, alice, ai):
    ai.rules = {"keywords": [{"term": "Wisdom", "weight": 1}], "notes": ""}
    await client.post(f"{BASE}/categories", json={"title": "Thinking", "description": "Thoughts"}, headers=alice.headers)
    assert not ai.rules_requests


# --- The AI level in the endpoints --------------------------------------------


async def test_an_ai_verdict_can_stop_a_post_the_local_check_let_through(client, alice, db_session, ai):
    await _category(db_session, alice)
    _use_config(ai_review_enabled=True)
    ai.result = AiReviewResult(90, None, (AiFinding("misinformation", ("claim",)),), "mock")

    resp = await _publish(client, alice)

    assert resp.status_code == 422
    assert {f["code"] for f in resp.json()["detail"]["assessment"]["findings"]} == {"misinformation"}
    assert ai.requests[-1].title == "A title"


async def test_the_ai_is_left_out_while_disabled(client, alice, db_session, ai):
    await _category(db_session, alice)
    ai.result = AiReviewResult(90, None, (), "mock")

    assert (await _publish(client, alice)).status_code == 201
    assert not ai.requests


# --- Blocked accounts ---------------------------------------------------------


@pytest.fixture()
async def blocked(make_person):
    return await make_person(is_blocked=True, blocked_at=datetime.now(timezone.utc), blocked_reason="repeated_violations")


async def test_a_blocked_account_cannot_write_anything(client, blocked, alice, db_session):
    category = await _category(db_session, alice)
    post = await _post(db_session, alice, category)
    expected = {"code": "account_blocked", "reason": "repeated_violations"}

    responses = [
        await client.post(f"{BASE}/categories", json={"title": "T", "description": "D"}, headers=blocked.headers),
        await client.post(f"{BASE}/categories/check", json={"title": "T", "description": "D"}, headers=blocked.headers),
        await _publish(client, blocked),
        await client.post(f"{BASE}/categories/general/posts/check", json=_payload(), headers=blocked.headers),
        await client.post(f"{BASE}/posts/{post.id}/resonance", headers=blocked.headers),
    ]

    assert [r.status_code for r in responses] == [403] * 5
    assert all(r.json()["detail"] == expected for r in responses)


async def test_a_blocked_account_can_still_read_the_boards(client, blocked, alice, db_session):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category)

    listing = await client.get(f"{BASE}/categories/general/posts", headers=blocked.headers)

    assert listing.status_code == 200 and len(listing.json()["items"]) == 1


async def test_me_tells_the_standing_of_the_signed_in_user(client, alice, admin, blocked):
    assert (await client.get(f"{BASE}/me")).status_code == 401
    assert (await client.get(f"{BASE}/me", headers=alice.headers)).json() == {
        "is_admin": False, "blocked": False, "blocked_reason": None,
    }
    assert (await client.get(f"{BASE}/me", headers=admin.headers)).json()["is_admin"] is True
    assert (await client.get(f"{BASE}/me", headers=blocked.headers)).json() == {
        "is_admin": False, "blocked": True, "blocked_reason": "repeated_violations",
    }


# --- Only published posts are on the boards -----------------------------------


async def test_blocked_and_removed_posts_are_gone_from_the_boards(client, alice, bob, db_session):
    category = await _category(db_session, alice)
    shown = await _post(db_session, alice, category, "shown")
    gone = await _post(db_session, alice, category, "blocked", status="blocked")
    await _post(db_session, alice, category, "removed", status="removed")

    listing = await client.get(f"{BASE}/categories/general/posts")
    one = await client.get(f"{BASE}/categories/general")
    all_categories = await client.get(f"{BASE}/categories")

    assert [p["title"] for p in listing.json()["items"]] == ["shown"]
    assert one.json()["post_count"] == 1
    assert all_categories.json()["items"][0]["post_count"] == 1
    assert (await client.post(f"{BASE}/posts/{gone.id}/resonance", headers=bob.headers)).status_code == 404
    assert (await client.post(f"{BASE}/posts/{shown.id}/resonance", headers=bob.headers)).status_code == 200


# --- The administrators' endpoints need an administrator ----------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/posts", None),
        ("post", f"/posts/{uuid.uuid4()}/block", {"reason": "x"}),
        ("get", "/categories/general/rules", None),
        ("put", "/categories/general/rules", {"keywords": [], "notes": ""}),
        ("post", "/categories/general/rules/rebuild", None),
        ("get", "/users/blocked", None),
        ("post", f"/users/{uuid.uuid4()}/unblock", None),
    ],
)
async def test_manage_endpoints_refuse_everyone_but_administrators(client, alice, method, path, body):
    kwargs = {} if body is None else {"json": body}

    anonymous = await getattr(client, method)(MANAGE + path, **kwargs)
    ordinary = await getattr(client, method)(MANAGE + path, headers=alice.headers, **kwargs)

    assert anonymous.status_code == 401
    assert ordinary.status_code == 403


async def test_the_auth_service_role_does_not_make_an_administrator(client, make_access_token, db_session):
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub))
    await db_session.commit()
    headers = {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='admin')}"}

    assert (await client.get(f"{MANAGE}/posts", headers=headers)).status_code == 403


# --- Finding posts ------------------------------------------------------------


async def test_an_administrator_finds_posts_with_everything_needed_to_judge_them(client, alice, admin, db_session):
    category = await _category(db_session, alice, title="General")
    await _post(
        db_session,
        alice,
        category,
        "flagged",
        violation_score=58,
        topic_mismatch_score=12,
        resonance_count=3,
        assessment={"violation": 58, "topic": 12, "findings": [{"code": "profanity", "aspect": "violation", "matches": ["shit"]}]},
    )

    resp = await client.get(f"{MANAGE}/posts", headers=admin.headers)

    assert resp.status_code == 200
    (item,) = resp.json()["items"]
    assert item["title"] == "flagged"
    assert (item["category_slug"], item["category_title"]) == ("general", "General")
    assert (item["status"], item["violation_score"], item["topic_mismatch_score"]) == ("published", 58, 12)
    assert item["findings"] == [{"code": "profanity", "aspect": "violation", "matches": ["shit"]}]
    assert (item["value"], item["resonance_count"]) == (3, 3)
    assert item["author_id"] == str(alice.user.id)
    assert item["author_blocked"] is False


async def test_the_post_list_filters_by_text_category_state_and_score(client, alice, admin, db_session):
    one = await _category(db_session, alice, "one")
    two = await _category(db_session, alice, "two")
    await _post(db_session, alice, one, "Apples are red", violation_score=10)
    await _post(db_session, alice, one, "Pears", violation_score=60)
    await _post(db_session, alice, two, "Plums", topic_mismatch_score=80)
    await _post(db_session, alice, two, "Gone", status="blocked")

    async def titles(**params):
        resp = await client.get(f"{MANAGE}/posts", params=params, headers=admin.headers)
        return sorted(item["title"] for item in resp.json()["items"])

    assert await titles() == ["Apples are red", "Pears", "Plums"]  # published by default
    assert await titles(status="blocked") == ["Gone"]
    assert await titles(status="all") == ["Apples are red", "Gone", "Pears", "Plums"]
    assert await titles(category="two") == ["Plums"]
    assert await titles(q="APPLES") == ["Apples are red"]
    assert await titles(q="body of pe") == ["Pears"]  # the text is searched too
    assert await titles(min_score=50) == ["Pears", "Plums"]  # the worse of the two scores


async def test_a_search_for_percent_or_underscore_is_literal(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    await _post(db_session, alice, category, "100% sure")
    await _post(db_session, alice, category, "snake_case")
    await _post(db_session, alice, category, "plain")

    async def titles(q):
        resp = await client.get(f"{MANAGE}/posts", params={"q": q}, headers=admin.headers)
        return [item["title"] for item in resp.json()["items"]]

    assert await titles("%") == ["100% sure"]
    assert await titles("_") == ["snake_case"]


async def test_the_review_queue_can_be_sorted_by_score_and_pages(client, alice, admin, db_session):
    _app.dependency_overrides[get_config] = lambda: BoardsConfig(page_size=2)
    category = await _category(db_session, alice)
    for title, score in (("a", 10), ("b", 90), ("c", 50), ("d", 70), ("e", 30)):
        await _post(db_session, alice, category, title, violation_score=score)

    pages = [
        (await client.get(f"{MANAGE}/posts", params={"sort": "score", "offset": offset}, headers=admin.headers)).json()
        for offset in (0, 2, 4)
    ]

    assert [[i["title"] for i in p["items"]] for p in pages] == [["b", "d"], ["c", "e"], ["a"]]
    assert [p["has_more"] for p in pages] == [True, True, False]


async def test_the_post_list_says_when_an_author_is_blocked(client, blocked, admin, db_session):
    category = await _category(db_session, blocked)
    await _post(db_session, blocked, category, status="removed")

    resp = await client.get(f"{MANAGE}/posts", params={"status": "removed"}, headers=admin.headers)

    assert resp.json()["items"][0]["author_blocked"] is True


# --- Blocking a post ----------------------------------------------------------


async def _block(client, admin, post, reason="Breaks rule 3: personal attacks."):
    return await client.post(f"{MANAGE}/posts/{post.id}/block", json={"reason": reason}, headers=admin.headers)


async def test_blocking_a_post_removes_it_and_tells_the_author_why(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    post = await _post(db_session, alice, category, "bad post", paid_cents=2500)

    resp = await _block(client, admin, post, "Personal attacks on other users.")

    assert resp.status_code == 200
    body = resp.json()
    assert body["account_blocked"] is False
    assert body["post"]["status"] == "blocked"
    assert body["post"]["moderation_reason"] == "Personal attacks on other users."

    await db_session.refresh(post)
    assert (post.status, post.moderated_by_id) == ("blocked", admin.user.id)
    assert post.moderated_at is not None
    assert post.paid_cents == 2500  # nothing is refunded - the payment record stays as it was

    notification = (await db_session.scalars(select(Notification).where(Notification.user_id == alice.user.id))).one()
    assert notification.message_key == "boards:notification.postBlocked"
    assert notification.message_params == {"title": "bad post", "reason": "Personal attacks on other users."}
    assert notification.reference_id == post.id
    assert (await client.get(f"{BASE}/categories/general/posts")).json()["items"] == []


async def test_blocking_needs_a_reason(client, alice, admin, db_session):
    post = await _post(db_session, alice, await _category(db_session, alice))
    for reason in ("", "   "):
        resp = await client.post(f"{MANAGE}/posts/{post.id}/block", json={"reason": reason}, headers=admin.headers)
        assert resp.status_code == 422
    too_long = await client.post(f"{MANAGE}/posts/{post.id}/block", json={"reason": "x" * 1001}, headers=admin.headers)
    assert too_long.status_code == 422
    await db_session.refresh(post)
    assert post.status == "published"


async def test_only_a_published_post_can_be_blocked(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    post = await _post(db_session, alice, category)
    assert (await _block(client, admin, post)).status_code == 200

    again = await _block(client, admin, post)
    missing = await client.post(f"{MANAGE}/posts/{uuid.uuid4()}/block", json={"reason": "x"}, headers=admin.headers)

    assert (again.status_code, missing.status_code) == (409, 404)
    notifications = await db_session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == alice.user.id))
    assert notifications == 1  # not told twice


# --- Strikes and account blocks -----------------------------------------------


async def _published_posts(db_session, person, category, count):
    return [await _post(db_session, person, category, f"post {i}") for i in range(count)]


async def test_the_third_violation_within_the_period_blocks_the_account_and_removes_its_posts(
    client, alice, admin, db_session
):
    category = await _category(db_session, alice)
    posts = await _published_posts(db_session, alice, category, 5)

    results = [await _block(client, admin, post) for post in posts[:3]]

    assert [r.json()["account_blocked"] for r in results] == [False, False, True]
    await db_session.refresh(alice.user)
    assert alice.user.is_blocked is True
    assert alice.user.blocked_reason == "repeated_violations"
    assert alice.user.blocked_at is not None

    statuses = []
    for post in posts:
        await db_session.refresh(post)
        statuses.append((post.status, post.moderation_reason))
    assert statuses == [("blocked", "Breaks rule 3: personal attacks.")] * 3 + [("removed", "account_blocked")] * 2

    keys = list(
        await db_session.scalars(
            select(Notification.message_key).where(Notification.user_id == alice.user.id).order_by(Notification.created_at)
        )
    )
    assert keys.count("boards:notification.postBlocked") == 3
    assert keys.count("boards:notification.accountBlocked") == 1
    assert (await client.get(f"{BASE}/categories/general/posts")).json()["items"] == []


async def test_a_blocked_account_is_reported_in_the_answer_and_cannot_post_afterwards(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    _use_config(strike_limit=1)
    post = await _post(db_session, alice, category)

    assert (await _block(client, admin, post)).json()["account_blocked"] is True

    resp = await _publish(client, alice)
    assert (resp.status_code, resp.json()["detail"]["code"]) == (403, "account_blocked")


async def test_violations_older_than_the_period_do_not_count(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    for i in range(2):
        await _post(db_session, alice, category, f"old {i}", status="blocked", moderated_at=old)
    fresh = await _published_posts(db_session, alice, category, 2)

    assert (await _block(client, admin, fresh[0])).json()["account_blocked"] is False
    assert (await _block(client, admin, fresh[1])).json()["account_blocked"] is False  # 2 old ones don't count


async def test_the_period_and_the_limit_are_parameters(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    _use_config(strike_limit=2, strike_period_days=60)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    await _post(db_session, alice, category, "old", status="blocked", moderated_at=old)
    post = await _post(db_session, alice, category)

    assert (await _block(client, admin, post)).json()["account_blocked"] is True  # 31 days ago is within 60


async def test_strikes_of_different_authors_are_not_added_together(client, alice, bob, admin, db_session):
    category = await _category(db_session, alice)
    posts = [*await _published_posts(db_session, alice, category, 2), *await _published_posts(db_session, bob, category, 2)]

    results = [await _block(client, admin, post) for post in posts]

    assert [r.json()["account_blocked"] for r in results] == [False] * 4


async def test_unblocking_an_account_gives_it_a_clean_start(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    posts = await _published_posts(db_session, alice, category, 3)
    for post in posts:
        await _block(client, admin, post)
    await db_session.refresh(alice.user)
    assert alice.user.is_blocked

    await client.post(f"{MANAGE}/users/{alice.user.id}/unblock", headers=admin.headers)
    await db_session.refresh(alice.user)
    assert alice.user.strikes_reset_at is not None

    fresh = await _published_posts(db_session, alice, category, 3)
    results = [await _block(client, admin, post) for post in fresh]
    # The three violations from before the unblock no longer count: it takes
    # three new ones to block the account again.
    assert [r.json()["account_blocked"] for r in results] == [False, False, True]


async def test_removed_posts_alone_never_add_up_to_a_block(client, alice, admin, db_session):
    category = await _category(db_session, alice)
    for i in range(5):
        await _post(db_session, alice, category, f"removed {i}", status="removed", moderated_at=datetime.now(timezone.utc))
    post = await _post(db_session, alice, category)

    assert (await _block(client, admin, post)).json()["account_blocked"] is False


# --- Blocked accounts: listing and unblocking ---------------------------------


async def test_blocked_accounts_are_listed_and_can_be_unblocked(client, blocked, admin, db_session):
    await _category(db_session, blocked)

    listing = await client.get(f"{MANAGE}/users/blocked", headers=admin.headers)
    assert [u["id"] for u in listing.json()] == [str(blocked.user.id)]
    assert listing.json()[0]["blocked_reason"] == "repeated_violations"

    resp = await client.post(f"{MANAGE}/users/{blocked.user.id}/unblock", headers=admin.headers)

    assert resp.status_code == 200
    assert (resp.json()["blocked_at"], resp.json()["blocked_reason"]) == (None, None)
    assert (await client.get(f"{MANAGE}/users/blocked", headers=admin.headers)).json() == []
    assert (await _publish(client, blocked)).status_code == 201


async def test_unblocking_checks_the_user(client, alice, admin):
    not_blocked = await client.post(f"{MANAGE}/users/{alice.user.id}/unblock", headers=admin.headers)
    missing = await client.post(f"{MANAGE}/users/{uuid.uuid4()}/unblock", headers=admin.headers)
    assert (not_blocked.status_code, missing.status_code) == (409, 404)


# --- Machine rules, administrator's side --------------------------------------


async def test_the_rules_of_a_category_without_any_read_as_empty(client, alice, admin, db_session):
    await _category(db_session, alice)

    resp = await client.get(f"{MANAGE}/categories/general/rules", headers=admin.headers)

    assert resp.json() == {"rules": {"keywords": [], "notes": ""}, "source": None, "updated_at": None}
    assert (await client.get(f"{MANAGE}/categories/nope/rules", headers=admin.headers)).status_code == 404


async def test_an_administrator_reads_and_edits_the_rules(client, alice, admin, db_session):
    await _category(db_session, alice, rules=build_rules("Technology", "Software and networks"))

    read = await client.get(f"{MANAGE}/categories/general/rules", headers=admin.headers)
    assert read.json()["source"] == "algorithm"
    assert [k["term"] for k in read.json()["rules"]["keywords"]][:2] == ["technology", "software"]

    edited = await client.put(
        f"{MANAGE}/categories/general/rules",
        json={"keywords": [{"term": "Gadgets", "weight": 2}, {"term": "ŠIFRY", "weight": 1}], "notes": "Hardware too"},
        headers=admin.headers,
    )

    assert edited.status_code == 200
    assert edited.json()["source"] == "admin"
    assert edited.json()["rules"] == {
        "keywords": [{"term": "Gadgets", "weight": 2.0}, {"term": "ŠIFRY", "weight": 1.0}],
        "notes": "Hardware too",
    }
    assert edited.json()["updated_at"] is not None
    assert (await client.get(f"{MANAGE}/categories/general/rules", headers=admin.headers)).json() == edited.json()


async def test_repeated_keywords_are_merged_keeping_the_heavier_weight(client, alice, admin, db_session):
    await _category(db_session, alice)

    resp = await client.put(
        f"{MANAGE}/categories/general/rules",
        json={"keywords": [{"term": "Zvyky", "weight": 1}, {"term": "zvyky", "weight": 3}, {"term": "ZVYKY", "weight": 2}], "notes": ""},
        headers=admin.headers,
    )

    assert resp.json()["rules"]["keywords"] == [{"term": "zvyky", "weight": 3.0}]


@pytest.mark.parametrize(
    "payload",
    [
        {"keywords": [{"term": "", "weight": 1}], "notes": ""},
        {"keywords": [{"term": "x", "weight": 0}], "notes": ""},
        {"keywords": [{"term": "x", "weight": 11}], "notes": ""},
        {"keywords": [{"term": "two\nlines", "weight": 1}], "notes": ""},
        {"keywords": [{"term": f"w{i}", "weight": 1} for i in range(101)], "notes": ""},
        {"keywords": [], "notes": "x" * 2001},
        {"keywords": [], "notes": "", "source": "ai"},
        {"notes": ""},
    ],
)
async def test_invalid_rules_are_refused_and_change_nothing(client, alice, admin, db_session, payload):
    category = await _category(db_session, alice, rules=SPARSE_RULES)

    resp = await client.put(f"{MANAGE}/categories/general/rules", json=payload, headers=admin.headers)

    assert resp.status_code == 422
    await db_session.refresh(category)
    assert category.machine_rules == SPARSE_RULES


async def test_rebuilding_the_rules_starts_over_from_the_title_and_description(client, alice, admin, db_session):
    category = await _category(db_session, alice, title="Technology")
    category.description = "Software, hardware and networks"
    category.machine_rules = {"keywords": [{"term": "mine", "weight": 1}], "notes": "edited"}
    category.machine_rules_source = "admin"
    await db_session.commit()

    resp = await client.post(f"{MANAGE}/categories/general/rules/rebuild", headers=admin.headers)

    assert resp.status_code == 200
    assert resp.json()["source"] == "algorithm"
    assert [k["term"] for k in resp.json()["rules"]["keywords"]] == ["technology", "software", "hardware", "networks"]
    assert resp.json()["rules"]["notes"] == ""
    assert (await client.post(f"{MANAGE}/categories/nope/rules/rebuild", headers=admin.headers)).status_code == 404


async def test_rebuilding_uses_the_ai_rules_when_enabled_and_valid(client, alice, admin, db_session, ai):
    await _category(db_session, alice, rules=SPARSE_RULES)
    _use_config(ai_review_enabled=True)
    ai.rules = {"keywords": [{"term": "wisdom", "weight": 2}], "notes": ""}

    resp = await client.post(f"{MANAGE}/categories/general/rules/rebuild", headers=admin.headers)

    assert (resp.json()["source"], resp.json()["rules"]["keywords"]) == ("ai", [{"term": "wisdom", "weight": 2.0}])


# --- Only what is over the threshold is explained to the author ---------------


def _distinct_words(count: int, offset: int = 0) -> str:
    """Made-up words whose five-letter stems all differ - each counts as its own word to the topic check."""
    return " ".join("".join(chr(97 + ((offset + i) // 26**k) % 26) for k in range(5)) + "z" for i in range(count))


def _eight_keywords(first_weight: float = 1.0) -> dict:
    others = _distinct_words(7, offset=5000).split()
    return {"keywords": [{"term": "alpha", "weight": first_weight}, *({"term": w, "weight": 1} for w in others)], "notes": ""}


async def test_a_faint_topic_finding_is_not_listed_under_a_verdict_about_violations(client, alice, db_session):
    """Three of the keywords are covered (a low, "ok" mismatch) while the
    text swears: the author is told about the swearing, not about a 1 %
    topic mismatch."""
    rules = {"keywords": [{"term": w, "weight": 1} for w in ("alpha", "bravo", "charlie")]
             + [{"term": w, "weight": 1} for w in _distinct_words(6, offset=5000).split()], "notes": ""}
    await _category(db_session, alice, rules=rules)
    body = f"alpha bravo charlie {_distinct_words(30)} this is bullshit"

    resp = await client.post(f"{BASE}/categories/general/posts/check", json=_payload(body), headers=alice.headers)

    assessment = resp.json()
    assert assessment["violation"]["level"] == "warn"
    assert 0 < assessment["topic"]["percent"] <= 30 and assessment["topic"]["level"] == "ok"
    assert [f["code"] for f in assessment["findings"]] == ["profanity"]


async def test_a_faint_violation_finding_is_not_listed_under_a_verdict_about_the_topic(client, alice, db_session):
    """"You idiot" alone is 20 % ("ok"), but the post is also somewhat off
    topic ("warn"): the author sees the topic reason only. An administrator
    still gets every finding with the stored post."""
    await _category(db_session, alice, rules=_eight_keywords(first_weight=1.5))
    body = f"alpha {_distinct_words(30)} you idiot"

    check = await client.post(f"{BASE}/categories/general/posts/check", json=_payload(body), headers=alice.headers)

    assessment = check.json()
    assert (assessment["violation"]["level"], assessment["topic"]["level"]) == ("ok", "warn")
    assert [(f["code"], f["aspect"]) for f in assessment["findings"]] == [("off_topic", "topic")]

    assert (await _publish(client, alice, body=body)).status_code == 201
    stored = (await db_session.scalars(select(Post))).one().assessment
    assert {f["code"] for f in stored["findings"]} == {"off_topic", "insult"}
