# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The boards module's own rules: slugs, the post value formula, and that
the SQL ordering key never contradicts the value the formula shows."""

import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.models.user import User
from app.modules.boards.config import BoardsConfig
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.service import (
    FALLBACK_SLUG,
    SLUG_BASE_MAX,
    age_in_days,
    post_value,
    rank_expression,
    slugify,
    unique_slug,
)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
CONFIG = BoardsConfig()


# --- slugify ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Rezervace Salónu", "rezervace-salonu"),
        ("Příliš žluťoučký kůň", "prilis-zlutoucky-kun"),
        ("  Hello,   World!!  ", "hello-world"),
        ("a--b__c", "a-b-c"),
        ("Café Münster 2", "cafe-munster-2"),
    ],
)
def test_slugify(title, slug):
    assert slugify(title) == slug


@pytest.mark.parametrize("title", ["😀😀", "!!!", "   "])
def test_slugify_never_returns_an_empty_slug(title):
    assert slugify(title) == FALLBACK_SLUG


def test_slugify_truncates_without_a_trailing_hyphen():
    slug = slugify("word " * 60)
    assert len(slug) <= SLUG_BASE_MAX
    assert not slug.endswith("-")
    assert slug.startswith("word-word")


# --- post value ---------------------------------------------------------------


def _value(paid_cents=0, resonances=0, age=timedelta(0), config=CONFIG):
    return post_value(paid_cents, resonances, NOW - age, NOW, config)


def test_a_new_unpaid_post_is_worth_nothing():
    assert _value() == 0


def test_one_usd_is_ten_points():
    assert _value(paid_cents=100) == 10
    assert _value(paid_cents=2500) == 250


def test_paid_cents_count_in_whole_points():
    assert _value(paid_cents=5) == 0  # half a point
    assert _value(paid_cents=19) == 1  # 1.9 points


def test_one_resonance_is_one_point():
    assert _value(resonances=7) == 7


def test_one_day_of_age_costs_one_point():
    assert _value(age=timedelta(days=3)) == -3


def test_age_counts_whole_days_only():
    assert _value(age=timedelta(days=2, hours=23, minutes=59)) == -2
    assert _value(age=timedelta(hours=23)) == 0


def test_the_parts_add_up():
    # 25 (paid $2.50) + 4 resonances - 3 days
    assert _value(paid_cents=250, resonances=4, age=timedelta(days=3, hours=2)) == 26


def test_payments_accumulate_into_the_value():
    """A new payment raises the value by exactly what was paid (1 USD = 10)."""
    assert _value(paid_cents=300 + 200) - _value(paid_cents=300) == 20


def test_a_clock_skewed_future_post_is_not_negative_age():
    assert age_in_days(NOW + timedelta(hours=5), NOW) == 0
    assert _value(age=timedelta(hours=-5)) == 0


def test_factors_come_from_the_config():
    config = BoardsConfig(points_per_usd=20, points_per_resonance=3, points_per_day=2)
    assert _value(paid_cents=100, resonances=2, age=timedelta(days=4, hours=1), config=config) == 20 + 6 - 8


# --- unique slugs (database) --------------------------------------------------


@pytest.fixture()
async def user(db_session) -> User:
    user = User(auth_sub=uuid.uuid4())
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture(autouse=True)
async def _clean_tables(db_session):
    await db_session.execute(delete(Resonance))
    await db_session.execute(delete(Post))
    await db_session.execute(delete(Category))


async def _seed_category(db_session, user, slug, title=None) -> Category:
    category = Category(title=title or slug, slug=slug, description="d", created_by_id=user.id)
    db_session.add(category)
    await db_session.commit()
    return category


async def test_a_free_title_gets_its_plain_slug(db_session):
    assert await unique_slug(db_session, "My Board") == "my-board"


async def test_a_taken_slug_gets_the_next_number(db_session, user):
    await _seed_category(db_session, user, "my-board")
    assert await unique_slug(db_session, "My Board") == "my-board-2"

    await _seed_category(db_session, user, "my-board-2")
    assert await unique_slug(db_session, "My Board") == "my-board-3"


async def test_a_gap_in_the_numbering_is_filled(db_session, user):
    await _seed_category(db_session, user, "my-board")
    await _seed_category(db_session, user, "my-board-3")
    assert await unique_slug(db_session, "My Board") == "my-board-2"


async def test_a_longer_slug_sharing_the_prefix_is_not_a_collision(db_session, user):
    await _seed_category(db_session, user, "my-board")
    await _seed_category(db_session, user, "my-board-extra")
    assert await unique_slug(db_session, "My Board") == "my-board-2"
    assert await unique_slug(db_session, "My Board Extra") == "my-board-extra-2"


async def test_a_reserved_slug_is_numbered_even_when_free(db_session):
    assert await unique_slug(db_session, "New") == "new-2"


async def test_titles_without_letters_fall_back_and_still_number(db_session, user):
    assert await unique_slug(db_session, "😀") == FALLBACK_SLUG
    await _seed_category(db_session, user, FALLBACK_SLUG)
    assert await unique_slug(db_session, "🎉") == f"{FALLBACK_SLUG}-2"


# --- ordering key vs. value (database) ----------------------------------------


async def test_the_sql_ordering_never_contradicts_the_shown_values(db_session, user):
    """rank_expression has no notion of `now`; this checks that it still
    never lists a post above one with a higher post_value, over a spread of
    payments, resonances and ages - including fractional-point payments.
    (Posts with equal values may come in either order.)"""
    category = await _seed_category(db_session, user, "ordering")
    rng = random.Random(20261002)
    now = datetime.now(timezone.utc)
    for _ in range(60):
        db_session.add(
            Post(
                category_id=category.id,
                author_id=user.id,
                title="t",
                body="b",
                paid_cents=rng.choice([0, 0, 5, 19, 100, 250, 1234]),
                resonance_count=rng.randint(0, 40),
                created_at=now - timedelta(minutes=rng.randint(0, 60 * 24 * 90)),
            )
        )
    await db_session.commit()

    posts = (
        await db_session.scalars(
            select(Post).where(Post.category_id == category.id).order_by(rank_expression(CONFIG).desc(), Post.id.desc())
        )
    ).all()
    assert len(posts) == 60

    probe = datetime.now(timezone.utc)
    shown = [post_value(p.paid_cents, p.resonance_count, p.created_at, probe, CONFIG) for p in posts]
    assert shown == sorted(shown, reverse=True)


async def test_the_ordering_follows_the_configured_factors(db_session, user):
    """With age costing nothing, an old heavily-resonated post beats a new one."""
    category = await _seed_category(db_session, user, "factors")
    now = datetime.now(timezone.utc)
    old = Post(category_id=category.id, author_id=user.id, title="old", body="b", resonance_count=5,
               created_at=now - timedelta(days=30))
    new = Post(category_id=category.id, author_id=user.id, title="new", body="b", resonance_count=1, created_at=now)
    db_session.add_all([old, new])
    await db_session.commit()

    async def titles(config):
        rows = await db_session.scalars(
            select(Post.title).where(Post.category_id == category.id).order_by(rank_expression(config).desc())
        )
        return list(rows)

    assert await titles(BoardsConfig(points_per_day=1)) == ["new", "old"]
    assert await titles(BoardsConfig(points_per_day=0)) == ["old", "new"]
