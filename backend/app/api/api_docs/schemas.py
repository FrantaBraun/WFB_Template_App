# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RecheckPeriod = Literal["manual", "daily", "weekly", "monthly"]


class ApiDocumentCreate(BaseModel):
    team_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    recheck_period: RecheckPeriod = "manual"
    notes: str | None = None


class ApiDocumentUpdate(BaseModel):
    """PATCH body - every field optional/partial. The router applies this via
    model_dump(exclude_unset=True) so an omitted field is left untouched,
    while an explicitly-sent null still clears a nullable field such as
    source_url (see api_docs/router.py's update_document)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    recheck_period: RecheckPeriod | None = None
    is_public: bool | None = None
    source_url: str | None = Field(default=None, max_length=2048)


class ApiDocumentSummary(BaseModel):
    """List-item shape shared by GET /api/api-docs and GET /api/public/api-docs.
    current_version is just the current row's version string (or null) -
    not the richer object ApiDocumentDetail nests below."""

    id: uuid.UUID
    title: str
    team_id: uuid.UUID
    is_public: bool
    recheck_period: str
    last_checked_at: datetime | None
    last_check_error: str | None
    current_version: str | None


class ApiDocumentCurrentVersion(BaseModel):
    """The current-version object nested in ApiDocumentDetail. Distinct from
    ApiDocumentVersionOut (the /versions list-item shape below): this one
    carries format instead of archived_at, since archived_at is always null
    here by definition (it's always the current row)."""

    id: uuid.UUID
    version: str
    spec_title: str | None
    format: str
    fetched_at: datetime
    source: str


class ApiDocumentDetail(BaseModel):
    """is_subscribed is null for an anonymous caller (no identity to check a
    Subscription row against) and true/false otherwise - see
    api_docs/router.py's _build_detail, which computes it from the same
    current_user already used for can_edit."""

    id: uuid.UUID
    team_id: uuid.UUID
    title: str
    notes: str | None
    source_url: str | None
    recheck_period: str
    is_public: bool
    last_checked_at: datetime | None
    last_check_error: str | None
    created_at: datetime
    current_version: ApiDocumentCurrentVersion | None
    can_edit: bool
    is_subscribed: bool | None


class ApiDocumentVersionOut(BaseModel):
    """GET /api/api-docs/{id}/versions list item - carries archived_at
    (unlike ApiDocumentCurrentVersion above) so the frontend can tell current
    from archived rows within the same list."""

    id: uuid.UUID
    version: str
    spec_title: str | None
    fetched_at: datetime
    archived_at: datetime | None
    source: str
