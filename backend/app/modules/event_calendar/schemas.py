# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Status = Literal["draft", "published", "deleted"]

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Path segments the module's own routes use - an event with one of these
# slugs could never be opened (/events/manage is the editor's list).
RESERVED_SLUGS = frozenset({"manage", "uploads", "archive", "month", "dashboard", "search"})


def _validate_slug(value: str) -> str:
    if not _SLUG_RE.match(value):
        raise ValueError("slug may contain only lowercase letters, digits and single hyphens")
    if value in RESERVED_SLUGS:
        raise ValueError(f"slug {value!r} is reserved")
    return value


def _validate_image_url(value: str | None) -> str | None:
    """Thumbnails come from this module's own upload endpoint (absolute
    URL) or are pasted by an editor - http(s) or site-relative only, never
    javascript:/data: and the like."""
    if value is None or value == "":
        return None
    if not (value.startswith(("https://", "http://")) or (value.startswith("/") and not value.startswith("//"))):
        raise ValueError("image_url must be an http(s) URL or a site-relative path")
    return value


class EventTeaser(BaseModel):
    """Listing shape - no full_text, so lists don't ship every event's HTML."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    image_url: str | None
    event_date: date
    pinned: bool


class EventOut(EventTeaser):
    """Public detail page."""

    full_text: str


class EventAdminOut(EventOut):
    """Everything, for the editor's list and form."""

    display_from: date | None
    display_to: date | None
    status: Status
    created_at: datetime
    updated_at: datetime


class EventPage(BaseModel):
    items: list[EventTeaser]
    has_more: bool


class ArchiveMonth(BaseModel):
    month: int
    count: int


class ArchiveYear(BaseModel):
    year: int
    months: list[ArchiveMonth]


class DashboardOut(BaseModel):
    upcoming: EventTeaser | None
    pinned: list[EventTeaser]
    recent_past: list[EventTeaser]


class EditorStatus(BaseModel):
    is_editor: bool


class _DisplayWindowCheck(BaseModel):
    @model_validator(mode="after")
    def _window_in_order(self):
        start, end = getattr(self, "display_from", None), getattr(self, "display_to", None)
        if start is not None and end is not None and start > end:
            raise ValueError("display_from must not be after display_to")
        return self


class EventCreate(_DisplayWindowCheck):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    short_description: str = Field(default="", max_length=500)
    full_text: str = ""
    image_url: str | None = Field(default=None, max_length=500)
    event_date: date
    display_from: date | None = None
    display_to: date | None = None
    pinned: bool = False
    status: Status = "draft"

    _check_slug = field_validator("slug")(_validate_slug)
    _check_image = field_validator("image_url")(_validate_image_url)


class EventUpdate(_DisplayWindowCheck):
    """All optional, applied with exclude_unset. Sending display_from /
    display_to / image_url as null (not omitting them) clears them."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    short_description: str | None = Field(default=None, max_length=500)
    full_text: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    event_date: date | None = None
    display_from: date | None = None
    display_to: date | None = None
    pinned: bool | None = None
    status: Status | None = None

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str | None) -> str | None:
        return _validate_slug(value) if value is not None else value

    _check_image = field_validator("image_url")(_validate_image_url)
