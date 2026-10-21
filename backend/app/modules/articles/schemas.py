# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Status = Literal["draft", "published", "archived"]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Path segments the module's own routes use - an article with one of these
# slugs could never be opened (/articles/manage is the editor's list).
RESERVED_SLUGS = frozenset({"manage", "types", "search", "uploads"})


def _validate_slug(value: str) -> str:
    if not _SLUG_RE.match(value):
        raise ValueError("slug may contain only lowercase letters, digits and single hyphens")
    if value in RESERVED_SLUGS:
        raise ValueError(f"slug {value!r} is reserved")
    return value


def _validate_image_url(value: str | None) -> str | None:
    """Images come from this module's own upload endpoint (absolute URL) or
    are pasted by an editor - http(s) or site-relative only, never
    javascript:/data: and the like."""
    if value is None or value == "":
        return None
    if not (value.startswith(("https://", "http://")) or (value.startswith("/") and not value.startswith("//"))):
        raise ValueError("image_url must be an http(s) URL or a site-relative path")
    return value


# --- Types --------------------------------------------------------------------


class ArticleTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    border_light: str
    background_light: str
    border_dark: str
    background_dark: str


class ArticleTypeAdminOut(ArticleTypeOut):
    """For the type editor: how many articles use it (a type in use can only be deleted with a replacement)."""

    article_count: int


class ArticleTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    border_light: HexColor
    background_light: HexColor
    border_dark: HexColor
    background_dark: HexColor


class ArticleTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    border_light: HexColor | None = None
    background_light: HexColor | None = None
    border_dark: HexColor | None = None
    background_dark: HexColor | None = None


# --- Articles -----------------------------------------------------------------


class ArticleTeaser(BaseModel):
    """Listing shape - no content, so lists don't ship every article's HTML."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    title: str
    slug: str
    perex: str
    image_url: str | None
    pinned: bool
    status: Status
    created_at: datetime
    type: ArticleTypeOut | None = Field(default=None, validation_alias="article_type")


class ArticleOut(ArticleTeaser):
    """Public detail page."""

    content: str


class ArticleAdminListItem(ArticleTeaser):
    """The editor's list: teaser plus what an editor scans for."""

    display_from: date | None
    display_to: date | None
    updated_at: datetime


class ArticleAdminOut(ArticleOut):
    """Everything, for the editor's form."""

    type_id: uuid.UUID | None
    display_from: date | None
    display_to: date | None
    updated_at: datetime


class ArticlePage(BaseModel):
    items: list[ArticleTeaser]
    has_more: bool


class ArticleAdminPage(BaseModel):
    items: list[ArticleAdminListItem]
    has_more: bool


class _DisplayWindowCheck(BaseModel):
    @model_validator(mode="after")
    def _window_in_order(self):
        start, end = getattr(self, "display_from", None), getattr(self, "display_to", None)
        if start is not None and end is not None and start > end:
            raise ValueError("display_from must not be after display_to")
        return self


class ArticleCreate(_DisplayWindowCheck):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    perex: str = Field(default="", max_length=500)
    content: str = ""
    image_url: str | None = Field(default=None, max_length=500)
    type_id: uuid.UUID | None = None
    status: Status = "draft"
    display_from: date | None = None
    display_to: date | None = None
    pinned: bool = False

    _check_slug = field_validator("slug")(_validate_slug)
    _check_image = field_validator("image_url")(_validate_image_url)


class ArticleUpdate(_DisplayWindowCheck):
    """All optional, applied with exclude_unset. Sending display_from /
    display_to / image_url / type_id as null (not omitting them) clears them."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    perex: str | None = Field(default=None, max_length=500)
    content: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    type_id: uuid.UUID | None = None
    status: Status | None = None
    display_from: date | None = None
    display_to: date | None = None
    pinned: bool | None = None

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str | None) -> str | None:
        return _validate_slug(value) if value is not None else value

    _check_image = field_validator("image_url")(_validate_image_url)
