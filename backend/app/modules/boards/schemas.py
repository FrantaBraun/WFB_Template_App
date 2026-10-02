# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import unicodedata
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.boards.models import (
    CATEGORY_DESCRIPTION_MAX,
    CATEGORY_TITLE_MAX,
    POST_BODY_MAX,
    POST_TITLE_MAX,
)


def _clean(value, *, multiline: bool):
    """Normalizes line endings and trims, and refuses characters that are
    never text: control characters (a NUL would make Postgres reject the
    row) and lone surrogates. A single-line field refuses line breaks and
    tabs too. Runs before the length checks so those count what is stored.
    Lengths are in characters (code points), so an emoji counts once."""
    if not isinstance(value, str):
        return value  # the type check reports it
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    for char in value:
        category = unicodedata.category(char)
        if category == "Cs" or (category == "Cc" and not (multiline and char in "\n\t")):
            raise ValueError("must be plain text" + (" on a single line" if not multiline else ""))
    return value.strip()


def _single_line(value):
    return _clean(value, multiline=False)


def _multi_line(value):
    return _clean(value, multiline=True)


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=CATEGORY_TITLE_MAX)
    description: str = Field(min_length=1, max_length=CATEGORY_DESCRIPTION_MAX)

    _clean_title = field_validator("title", mode="before")(_single_line)
    _clean_description = field_validator("description", mode="before")(_multi_line)


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=POST_TITLE_MAX)
    body: str = Field(min_length=1, max_length=POST_BODY_MAX)

    _clean_title = field_validator("title", mode="before")(_single_line)
    _clean_body = field_validator("body", mode="before")(_multi_line)


class CategoryOut(BaseModel):
    """No creator - boards never show who made what."""

    id: uuid.UUID
    title: str
    slug: str
    description: str
    post_count: int
    created_at: datetime


class CategoryPage(BaseModel):
    items: list[CategoryOut]
    has_more: bool


class PostOut(BaseModel):
    """What a visitor sees of a post: text, current value and how many
    resonated - never the author, never who resonated, nor how the value is
    made up. resonated_by_me is the viewer's own resonance only (always
    false for an anonymous visitor)."""

    id: uuid.UUID
    title: str
    body: str
    value: int
    resonance_count: int
    resonated_by_me: bool
    created_at: datetime


class PostPage(BaseModel):
    items: list[PostOut]
    has_more: bool
