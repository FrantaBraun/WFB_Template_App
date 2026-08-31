# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.api.validators import validate_slug


class ArticleOut(BaseModel):
    """Full article record - the public detail route and admin endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    full_text: str
    event_date: date
    display_from: date | None
    display_to: date | None
    pinned: bool
    status: Literal["draft", "published", "deleted"]
    created_at: datetime
    updated_at: datetime


class ArticleTeaser(BaseModel):
    """Lightweight shape for the dashboard endpoint - the spec itself
    distinguishes short_description-for-listing from full_text-for-reading,
    so a home page load shouldn't ship every teaser's full WYSIWYG HTML."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    event_date: date
    pinned: bool


class DashboardOut(BaseModel):
    upcoming: ArticleTeaser | None
    pinned: list[ArticleTeaser]
    recent_past: list[ArticleTeaser]


class ArticleCreate(BaseModel):
    title: str
    slug: str
    short_description: str = ""
    full_text: str = ""
    event_date: date
    display_from: date | None = None
    display_to: date | None = None
    pinned: bool = False
    status: Literal["draft", "published", "deleted"] = "draft"

    _check_slug = field_validator("slug")(validate_slug)


class ArticleUpdate(BaseModel):
    """All fields optional, applied via exclude_unset - same convention as
    PageUpdate/AccountUpdate. Sending display_from/display_to as null (as
    opposed to omitting them) is how an admin clears a previously-set bound
    back to open-ended; exclude_unset still treats that as "was provided"."""

    title: str | None = None
    slug: str | None = None
    short_description: str | None = None
    full_text: str | None = None
    event_date: date | None = None
    display_from: date | None = None
    display_to: date | None = None
    pinned: bool | None = None
    status: Literal["draft", "published", "deleted"] | None = None

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str | None) -> str | None:
        return validate_slug(value) if value is not None else value
