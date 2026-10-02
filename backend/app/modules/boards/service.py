# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The rules that don't belong to one endpoint: category slugs and the
post value formula (with the SQL ordering key that matches it).

Post value = paid USD * points_per_usd + resonances * points_per_resonance
- whole days of age * points_per_day (all three factors in BoardsConfig).
It is computed on read, never stored - the age term changes every day.

Ordering by value looks like it would need the age in the query, but it
doesn't: with `now` the same for every post, value_i = base_i - d * (now -
created_i) is `now`-independent apart from a shift common to all posts, so
sorting by base_i + d * created_i (rank_expression) gives the same order at
any moment - which is also what keeps a page boundary stable between two
page loads. rank_expression uses the same whole-point paid term as
post_value, and its age term is the exact (fractional) age where post_value
counts whole days, so a post's key differs from its shown value (up to a
shift common to all posts) only by the fractional part of its age - under
one point, and always in the same direction - and the order never
contradicts the shown values. Only posts with *equal* shown values are
ordered by something else: that fractional part, stable but arbitrary.
"""

import logging
import re
import unicodedata
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boards.config import BoardsConfig, ModerationConfig
from app.modules.boards.models import Category, Post
from app.modules.boards.moderation.ai import AiModerator
from app.modules.boards.moderation.topic import build_rules
from app.modules.boards.schemas import MachineRules

logger = logging.getLogger(__name__)

# Leaves room for a "-<number>" suffix inside models.SLUG_MAX.
SLUG_BASE_MAX = 100
FALLBACK_SLUG = "category"
# Path segments the frontend's own routes use (/categories/new).
RESERVED_SLUGS = frozenset({"new"})

_SECONDS_PER_DAY = 86400.0


def slugify(title: str) -> str:
    """Lowercase, diacritics stripped, anything else collapsed to single
    hyphens. A title with nothing slug-worthy in it (only emoji, say) gets
    FALLBACK_SLUG, so a slug is never empty."""
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    return slug[:SLUG_BASE_MAX].strip("-") or FALLBACK_SLUG


async def unique_slug(db: AsyncSession, title: str) -> str:
    """The title's slug, or on a collision the first free "<slug>-<n>" with
    n counting up from 2. Two requests can still pick the same one at once -
    the unique index decides, and the caller retries (see router.py)."""
    base = slugify(title)
    # base only contains [a-z0-9-], so it is safe inside a LIKE pattern.
    existing = set(
        await db.scalars(select(Category.slug).where(or_(Category.slug == base, Category.slug.like(f"{base}-%"))))
    )
    taken = existing | RESERVED_SLUGS
    if base not in taken:
        return base
    number = 2
    while f"{base}-{number}" in taken:
        number += 1
    return f"{base}-{number}"


def age_in_days(created_at: datetime, now: datetime) -> int:
    return max(0, (now - created_at).days)


def post_value(paid_cents: int, resonance_count: int, created_at: datetime, now: datetime, config: BoardsConfig) -> int:
    """The post's current value in points - may go negative for an old post
    nobody paid for or agreed with."""
    paid_points = paid_cents * config.points_per_usd // 100
    return (
        paid_points
        + resonance_count * config.points_per_resonance
        - age_in_days(created_at, now) * config.points_per_day
    )


def rank_expression(config: BoardsConfig):
    """SQL ordering key, highest first = highest post_value first (see the
    module docstring for why it needs no `now`)."""
    paid_points = Post.paid_cents * config.points_per_usd // 100
    resonance_points = Post.resonance_count * config.points_per_resonance
    created_days = func.extract("epoch", Post.created_at) / _SECONDS_PER_DAY
    return paid_points + resonance_points + config.points_per_day * created_days


async def make_machine_rules(
    title: str, description: str, config: ModerationConfig, ai: AiModerator | None
) -> tuple[dict, str]:
    """The machine rules for a category and where they came from: always the
    algorithmic ones first, then - when AI review is enabled - the AI
    moderator's, which replace them if it offers any that are valid. (With
    only the mock connected it never does.) A failing or malformed AI answer
    just leaves the algorithmic rules in place."""
    rules, source = build_rules(title, description), "algorithm"
    if config.ai_review_enabled and ai is not None:
        try:
            ai_rules = await ai.build_category_rules(title, description)
            if ai_rules is not None:
                rules, source = MachineRules.model_validate(ai_rules).model_dump(), "ai"
        except Exception:
            logger.warning("AI machine rules for a category were not usable - kept the algorithmic ones", exc_info=True)
    return rules, source
