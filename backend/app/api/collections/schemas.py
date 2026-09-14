# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    team_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CollectionUpdate(BaseModel):
    """PATCH body - every field optional/partial. The router applies this via
    model_dump(exclude_unset=True), same semantics as
    app/api/api_docs/schemas.py's ApiDocumentUpdate."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_public: bool | None = None


class CollectionSummary(BaseModel):
    """List-item shape shared by GET /api/collections and
    GET /api/public/collections. document_count is computed (a count of
    CollectionDocument rows), not a stored column."""

    id: uuid.UUID
    name: str
    team_id: uuid.UUID
    is_public: bool
    document_count: int
    created_at: datetime


class CollectionDetail(BaseModel):
    """is_subscribed is null for an anonymous caller (no identity to check a
    Subscription row against) and true/false otherwise - see
    collections/router.py's _build_detail, which computes it from the same
    current_user already used for can_edit. Mirrors
    app/api/api_docs/schemas.py's ApiDocumentDetail one level up the domain
    model."""

    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    description: str | None
    is_public: bool
    document_count: int
    created_at: datetime
    can_edit: bool
    is_subscribed: bool | None
