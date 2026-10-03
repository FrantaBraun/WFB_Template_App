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
    false for an anonymous visitor).

    mine is true only for the post's own author, looking at their own post -
    nobody can learn from it who wrote anyone else's - and only then is
    paid_cents (what they paid for it so far) filled in; for everyone else it
    is null."""

    id: uuid.UUID
    title: str
    body: str
    value: int
    resonance_count: int
    resonated_by_me: bool
    mine: bool
    paid_cents: int | None
    created_at: datetime


class PostPage(BaseModel):
    items: list[PostOut]
    has_more: bool


class MyPostOut(BaseModel):
    """One of the signed-in user's own posts, whatever its state - what the
    "my posts" page shows. moderation_reason is set for a blocked or removed
    post (a free text from an administrator, or the code "account_blocked").
    category_blocked says the post's category is blocked: the post is still
    "published", but nobody can see it until the category is restored (the
    reason for that is the category creator's business, not shown here)."""

    id: uuid.UUID
    category_slug: str
    category_title: str
    title: str
    body: str
    status: Literal["published", "blocked", "removed"]
    value: int
    resonance_count: int
    paid_cents: int
    category_blocked: bool
    moderation_reason: str | None
    created_at: datetime


class MyPostPage(BaseModel):
    items: list[MyPostOut]
    has_more: bool


class ReceiptOut(BaseModel):
    """One of the signed-in user's payment documents, in brief; the document
    itself is GET /me/receipts/{id}/document. `emailed` says whether the
    confirmation email went out."""

    id: uuid.UUID
    number: str
    issued_at: datetime
    amount: int
    currency: str
    post_title: str
    points: int
    emailed: bool


class AdminReceiptOut(ReceiptOut):
    """What an administrator sees of a document's delivery - including the
    address it was sent to and why a send failed."""

    payment_id: uuid.UUID
    email_to: str | None
    email_attempts: int
    email_error: str | None


class RetryOut(BaseModel):
    tried: int
    sent: int
    still_unsent: int


class PaymentsInfo(BaseModel):
    """Whether authors can pay to raise a post's value on this deployment,
    and within what limits. enabled is false until the payment gateway is
    switched on and configured, so the frontend can leave the option out
    rather than offer a button that fails."""

    enabled: bool
    currency: str
    min_amount_usd: int
    max_amount_usd: int
    points_per_usd: int


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
    category_blocked: bool
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


class BlockCategoryIn(BlockPostIn):
    """The reason for blocking a category - sent to the category's creator."""


class AdminCategoryOut(BaseModel):
    """A category as an administrator sees it, blocked or not: with its
    creator's id (shown nowhere else), its state and the reason it was
    blocked. post_count counts the published posts in it."""

    id: uuid.UUID
    title: str
    slug: str
    description: str
    status: Literal["published", "blocked"]
    post_count: int
    violation_score: int
    moderation_reason: str | None
    moderated_at: datetime | None
    created_by_id: uuid.UUID
    created_at: datetime


class AdminCategoryPage(BaseModel):
    items: list[AdminCategoryOut]
    has_more: bool


class BlockedUserOut(BaseModel):
    id: uuid.UUID
    blocked_at: datetime | None
    blocked_reason: str | None
