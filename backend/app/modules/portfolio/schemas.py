# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

ItemStatus = Literal["live", "in_preparation"]

# The column sizes in models.py - changing one needs a migration.
SLUG_MIN = 2
SLUG_MAX = 80
TITLE_MAX = 120
SUMMARY_MAX = 400
DESCRIPTION_MAX = 8000
URL_MAX = 500
TAGS_MAX = 10
TAG_MAX = 40
SORT_ORDER_MAX = 1_000_000

# The public list is /portfolio and the editor's area is /portfolio/manage,
# so an item with that slug could never be opened.
RESERVED_SLUGS = frozenset({"manage"})

_SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _strip(value):
    """Surrounding whitespace never matters. NUL is refused because Postgres
    cannot store it in text - without this it would be a 500, not a 422."""
    if not isinstance(value, str):
        return value
    if "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value.strip()


def _strip_multiline(value):
    """As _strip, with line breaks normalised to \\n - a description's
    paragraphs are split on a blank line, whatever client typed them."""
    value = _strip(value)
    return value.replace("\r\n", "\n").replace("\r", "\n") if isinstance(value, str) else value


def _blank_to_none(value):
    """A cleared form field arrives as "" - treat it as no value at all."""
    value = _strip(value)
    return None if value == "" else value


Text = Annotated[str, BeforeValidator(_strip)]
Paragraphs = Annotated[str, BeforeValidator(_strip_multiline)]
OptionalText = Annotated[str | None, BeforeValidator(_blank_to_none)]


def has_slug_shape(value: str) -> bool:
    """Length and characters only (a reserved word has the shape too)."""
    return SLUG_MIN <= len(value) <= SLUG_MAX and _SLUG_PATTERN.fullmatch(value) is not None


def validate_slug(value: str | None) -> str | None:
    if value is None:
        return None
    if not SLUG_MIN <= len(value) <= SLUG_MAX:
        raise ValueError(f"slug must be {SLUG_MIN}-{SLUG_MAX} characters long")
    if not has_slug_shape(value):
        raise ValueError("slug may contain only lowercase letters a-z, digits and single hyphens between them")
    if value in RESERVED_SLUGS:
        raise ValueError(f"slug {value!r} is reserved")
    return value


def validate_url(value: str | None) -> str | None:
    """The page puts the URL in an href, so only an absolute http(s) address
    gets through - a javascript: or data: URL, a relative one or a bare
    host name is refused."""
    if value is None:
        return None
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("url must not contain spaces or control characters")
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError as exc:
        raise ValueError("url is not valid") from exc
    if parts.scheme not in ("http", "https") or not host:
        raise ValueError("url must be an absolute http:// or https:// address")
    return value


def clean_tags(tags: list[str]) -> list[str]:
    """Trimmed, blanks dropped, repeats (ignoring case) dropped, then the
    limits checked on what is actually stored."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        tag = _strip(tag)
        if not tag or tag.casefold() in seen:
            continue
        if len(tag) > TAG_MAX:
            raise ValueError(f"a tag may be at most {TAG_MAX} characters long")
        seen.add(tag.casefold())
        cleaned.append(tag)
    if len(cleaned) > TAGS_MAX:
        raise ValueError(f"at most {TAGS_MAX} tags are allowed")
    return cleaned


class ItemCreate(BaseModel):
    """Czech title and summary are required, everything in English is
    optional. Without a `slug` one is made from the English (else the Czech)
    title; without a `sort_order` the item goes to the end of the list."""

    slug: Annotated[str | None, BeforeValidator(_blank_to_none)] = None
    title_cs: Text = Field(min_length=1, max_length=TITLE_MAX)
    title_en: Text = Field(default="", max_length=TITLE_MAX)
    summary_cs: Text = Field(min_length=1, max_length=SUMMARY_MAX)
    summary_en: Text = Field(default="", max_length=SUMMARY_MAX)
    description_cs: Paragraphs = Field(default="", max_length=DESCRIPTION_MAX)
    description_en: Paragraphs = Field(default="", max_length=DESCRIPTION_MAX)
    url: OptionalText = Field(default=None, max_length=URL_MAX)
    status: ItemStatus = "live"
    tags: list[str] = Field(default_factory=list)
    published: bool = True
    sort_order: int | None = Field(default=None, ge=0, le=SORT_ORDER_MAX)

    _check_slug = field_validator("slug")(validate_slug)
    _check_url = field_validator("url")(validate_url)
    _check_tags = field_validator("tags")(clean_tags)


class ItemUpdate(BaseModel):
    """Partial update: only the fields sent change. `url` can be cleared with
    null (or ""); nothing else can be set to null."""

    slug: Annotated[str | None, BeforeValidator(_blank_to_none)] = None
    title_cs: Text | None = Field(default=None, min_length=1, max_length=TITLE_MAX)
    title_en: Text | None = Field(default=None, max_length=TITLE_MAX)
    summary_cs: Text | None = Field(default=None, min_length=1, max_length=SUMMARY_MAX)
    summary_en: Text | None = Field(default=None, max_length=SUMMARY_MAX)
    description_cs: Paragraphs | None = Field(default=None, max_length=DESCRIPTION_MAX)
    description_en: Paragraphs | None = Field(default=None, max_length=DESCRIPTION_MAX)
    url: OptionalText = Field(default=None, max_length=URL_MAX)
    status: ItemStatus | None = None
    tags: list[str] | None = None
    published: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=SORT_ORDER_MAX)

    _check_slug = field_validator("slug")(validate_slug)
    _check_url = field_validator("url")(validate_url)

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, tags: list[str] | None) -> list[str] | None:
        return clean_tags(tags) if tags is not None else None

    @model_validator(mode="after")
    def _required_fields_not_null(self):
        for field in self.model_fields_set - {"url"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class MoveRequest(BaseModel):
    direction: Literal["up", "down"]


class AdminItem(BaseModel):
    """Everything about an item, both languages - for the editor only."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title_cs: str
    title_en: str
    summary_cs: str
    summary_en: str
    description_cs: str
    description_en: str
    url: str | None
    status: ItemStatus
    tags: list[str]
    published: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class PublicItem(BaseModel):
    """What the public list shows: texts already resolved for the requested
    language. Deliberately has no id, flags, order or timestamps."""

    slug: str
    title: str
    summary: str
    url: str | None
    status: ItemStatus
    tags: list[str]


class PublicItemDetail(PublicItem):
    description: str
