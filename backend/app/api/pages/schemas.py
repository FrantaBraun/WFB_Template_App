# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.api.validators import validate_slug


class PageOut(BaseModel):
    """Full page record - used by both the public detail route and the admin
    endpoints, since neither needs to hide anything from the other here."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    heading: str
    slug: str
    content: str
    status: Literal["draft", "published"]
    show_in_nav: bool
    created_at: datetime
    updated_at: datetime


class PageCreate(BaseModel):
    heading: str
    slug: str
    content: str = ""
    status: Literal["draft", "published"] = "draft"
    show_in_nav: bool = False

    _check_slug = field_validator("slug")(validate_slug)


class PageUpdate(BaseModel):
    """All fields optional, applied via exclude_unset so omitted fields are
    left untouched rather than cleared - same convention as AccountUpdate."""

    heading: str | None = None
    slug: str | None = None
    content: str | None = None
    status: Literal["draft", "published"] | None = None
    show_in_nav: bool | None = None

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, value: str | None) -> str | None:
        return validate_slug(value) if value is not None else value
