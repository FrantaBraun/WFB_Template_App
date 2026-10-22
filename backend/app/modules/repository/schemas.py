# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.modules.repository import logic

# Surrounding whitespace never matters in a name or a description.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=logic.MAX_NAME_LENGTH)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=logic.MAX_DESCRIPTION_LENGTH)]
AttributeDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
# Checked by the service (so the error has the {"errors": {"slug": ...}} shape), only bounded here.
SlugInput = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None

# Kept in step with logic.COLOR_SCHEMES (a test compares them).
ColorScheme = Literal["blue", "teal", "green", "amber", "orange", "red", "pink", "violet"]
ViewType = Literal["table", "grid"]
AttributeType = Literal["text", "number", "boolean", "date", "datetime", "image", "reference", "list", "map"]

MAX_ATTRIBUTES_IN_REQUEST = 200


# --- Repositories ---------------------------------------------------------------


class RepositoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Description = ""
    slug: SlugInput = None
    color_scheme: ColorScheme = logic.DEFAULT_COLOR_SCHEME


class RepositoryUpdate(BaseModel):
    """Partial update: only the fields sent change."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    description: Description | None = None
    slug: SlugInput = None
    color_scheme: ColorScheme | None = None


class TableSummary(BaseModel):
    """A table as the side menu and the repository page list it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str
    view_type: ViewType
    position: int
    record_count: int = 0


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    slug: str
    color_scheme: str
    created_at: datetime
    updated_at: datetime
    table_count: int = 0
    # Records that are not deleted, over all the repository's tables.
    record_count: int = 0


class RepositoryDetail(RepositoryOut):
    tables: list[TableSummary]


# --- Tables and attributes ------------------------------------------------------


class TableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Description = ""
    slug: SlugInput = None
    view_type: ViewType = "table"


class TableUpdate(BaseModel):
    """Partial update: only the fields sent change."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    description: Description | None = None
    slug: SlugInput = None
    view_type: ViewType | None = None


class TableOrder(BaseModel):
    """Every table of the repository, in the order they should appear."""

    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID]


class AttributeIn(BaseModel):
    """One attribute in the list that replaces a table's attributes. `id` is
    chosen by the client (a new attribute needs one before it is saved);
    `config` is what the type needs (see logic.canonical_config)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: Name
    description: AttributeDescription = ""
    type: AttributeType
    required: bool = False
    show_in_list: bool = False
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self):
        try:
            self.config = logic.canonical_config(self.type, self.config)
        except ValueError as exc:
            raise ValueError(f"config: {exc}") from exc
        if self.required and self.type == "boolean":
            raise ValueError("a boolean attribute cannot be required (false is a value)")
        return self


class AttributesReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attributes: list[AttributeIn] = Field(max_length=MAX_ATTRIBUTES_IN_REQUEST)

    @field_validator("attributes")
    @classmethod
    def _unique(cls, attributes: list[AttributeIn]) -> list[AttributeIn]:
        if len({attribute.id for attribute in attributes}) != len(attributes):
            raise ValueError("attribute ids must be unique")
        if len({attribute.name.casefold() for attribute in attributes}) != len(attributes):
            raise ValueError("attribute names must be unique in the table")
        return attributes


class AttributeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    type: AttributeType
    required: bool
    show_in_list: bool
    config: dict[str, Any]
    position: int


class TableOut(TableSummary):
    attributes: list[AttributeOut]


# --- Slugs ----------------------------------------------------------------------


class SlugCheck(BaseModel):
    """Whether a slug can be used, for the live check beside a slug field.
    `suggestion` is the nearest free slug when it is taken."""

    slug: str
    available: bool
    reason: Literal["invalid", "reserved", "taken"] | None = None
    suggestion: str | None = None
