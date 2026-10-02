# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.boards.models import (
    CATEGORY_DESCRIPTION_MAX,
    CATEGORY_TITLE_MAX,
    MODERATION_REASON_MAX,
    POST_BODY_MAX,
    POST_TITLE_MAX,
)
from app.modules.boards.moderation.text import fold

Level = Literal["ok", "warn", "risk", "blocked"]


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
    """`confirm_risk` is the author's explicit "publish anyway" for a
    category the checks rate "risk" (see router.enforce)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=CATEGORY_TITLE_MAX)
    description: str = Field(min_length=1, max_length=CATEGORY_DESCRIPTION_MAX)
    confirm_risk: bool = False

    _clean_title = field_validator("title", mode="before")(_single_line)
    _clean_description = field_validator("description", mode="before")(_multi_line)


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=POST_TITLE_MAX)
    body: str = Field(min_length=1, max_length=POST_BODY_MAX)
    confirm_risk: bool = False

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


# --- Moderation: what the author is shown ---------------------------------------


class FindingOut(BaseModel):
    code: str
    aspect: Literal["violation", "topic"]
    matches: list[str]


class ScoreOut(BaseModel):
    percent: int
    level: Level


class AssessmentOut(BaseModel):
    """The result of checking a post or a category before it is published:
    the overall level, the two scores (topic is null for a category or a
    category without machine rules) and the specific aspects behind them."""

    level: Level
    violation: ScoreOut
    topic: ScoreOut | None
    findings: list[FindingOut]


class MeOut(BaseModel):
    """The signed-in user's standing in this application."""

    is_admin: bool
    blocked: bool
    blocked_reason: str | None


# --- Moderation: machine rules ---------------------------------------------------


class RuleKeyword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=60)
    weight: float = Field(ge=0.1, le=10)

    _clean_term = field_validator("term", mode="before")(_single_line)


class MachineRules(BaseModel):
    """A category's machine rules as an administrator reads and edits them
    (moderation/topic.py). Keywords repeated under another case or spelling
    of the diacritics are merged, keeping the heavier weight."""

    model_config = ConfigDict(extra="forbid")

    keywords: list[RuleKeyword] = Field(max_length=100)
    notes: str = Field(default="", max_length=2000)

    _clean_notes = field_validator("notes", mode="before")(_multi_line)

    @model_validator(mode="after")
    def _merge_duplicates(self) -> "MachineRules":
        merged: dict[str, RuleKeyword] = {}
        for keyword in self.keywords:
            key = fold(keyword.term)
            if key not in merged or keyword.weight > merged[key].weight:
                merged[key] = keyword
        self.keywords = list(merged.values())
        return self


class RulesOut(BaseModel):
    rules: MachineRules
    source: str | None
    updated_at: datetime | None


# --- Moderation: administrators' views ------------------------------------------


class AdminPostOut(BaseModel):
    """A post as an administrator sees it: with its author's id (needed to
    follow up on repeat violations - the only place it is ever shown), its
    scores and findings, and its moderation state."""

    id: uuid.UUID
    category_slug: str
    category_title: str
    title: str
    body: str
    status: Literal["published", "blocked", "removed"]
    value: int
    resonance_count: int
    violation_score: int
    topic_mismatch_score: int
    findings: list[FindingOut]
    moderation_reason: str | None
    moderated_at: datetime | None
    author_id: uuid.UUID
    author_blocked: bool
    created_at: datetime


class AdminPostPage(BaseModel):
    items: list[AdminPostOut]
    has_more: bool


class BlockPostIn(BaseModel):
    """The administrator's reason - sent to the post's author as a
    notification, so write it for them."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=MODERATION_REASON_MAX)

    _clean_reason = field_validator("reason", mode="before")(_multi_line)


class BlockPostOut(BaseModel):
    post: AdminPostOut
    account_blocked: bool


class BlockedUserOut(BaseModel):
    id: uuid.UUID
    blocked_at: datetime | None
    blocked_reason: str | None
