# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Language resolution and slug generation for the portfolio module."""

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portfolio.models import PortfolioItem
from app.modules.portfolio.schemas import RESERVED_SLUGS, SLUG_MAX, SLUG_MIN

LANGUAGES = ("cs", "en")
DEFAULT_LANGUAGE = "cs"

# Letters that do not decompose into a base letter plus an accent.
_TRANSLITERATE = str.maketrans(
    {
        "ß": "ss", "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D",
        "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "þ": "th", "Þ": "TH", "ð": "d", "Ð": "D",
    }
)


def resolve_language(language: str | None) -> str:
    """The language to show: the requested one if the portfolio has it, else
    its primary subtag ("en-GB" / "en_US" -> "en"), else Czech - the same
    matching the contact module does for its page texts."""
    if language:
        code = language.strip().lower().replace("_", "-")
        for candidate in (code, code.split("-")[0]):
            if candidate in LANGUAGES:
                return candidate
    return DEFAULT_LANGUAGE


def pick(language: str, cs: str, en: str) -> str:
    """The text in `language`; when that one is empty, the other language's
    (English falls back to Czech and, should Czech ever be empty, back)."""
    preferred, other = (en, cs) if language == "en" else (cs, en)
    return preferred if preferred.strip() else other


def slugify(text: str) -> str:
    """Diacritics transliterated, lowercase, runs of anything else become a
    single hyphen, at most SLUG_MAX characters. May be empty or too short
    (a title of only symbols) - base_slug deals with that."""
    text = unicodedata.normalize("NFKD", text.translate(_TRANSLITERATE))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:SLUG_MAX].strip("-")


def base_slug(title_en: str, title_cs: str) -> str:
    """From the English title, else the Czech one, else "item"."""
    for title in (title_en, title_cs):
        slug = slugify(title)
        if len(slug) >= SLUG_MIN:
            return slug
    return "item"


async def slug_taken(db: AsyncSession, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
    query = select(PortfolioItem.id).where(PortfolioItem.slug == slug)
    if exclude_id is not None:
        query = query.where(PortfolioItem.id != exclude_id)
    return (await db.scalar(query.limit(1))) is not None


async def unique_slug(db: AsyncSession, base: str) -> str:
    """`base`, or `base-2`, `base-3` ... - the first one that is neither used
    by another item nor reserved. The base is shortened to make room for the
    suffix, so a long title still ends up within the length limit."""
    candidate, number = base, 1
    while candidate in RESERVED_SLUGS or await slug_taken(db, candidate):
        number += 1
        suffix = f"-{number}"
        candidate = base[: SLUG_MAX - len(suffix)].rstrip("-") + suffix
    return candidate
