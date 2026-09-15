# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.api_docs.schemas import ApiDocumentSummary
from app.api.collections.schemas import KnowledgeBasePageOut


class IntegrationCreate(BaseModel):
    team_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class IntegrationUpdate(BaseModel):
    """PATCH body - every field optional/partial. The router applies this via
    model_dump(exclude_unset=True), same semantics as
    app/api/collections/schemas.py's CollectionUpdate - minus is_public,
    which Integration has no equivalent of (app/models/integration.py)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class IntegrationSummary(BaseModel):
    """List-item shape for GET /api/integrations. Both counts are plain
    join-table row counts (IntegrationCollection / IntegrationDocument) -
    document_count here is the DIRECT count only, not the merged/deduplicated
    view GET /{id}/documents computes; it stays unprefixed because, unlike
    IntegrationDetail below, this payload has no merged counterpart to
    disambiguate it from."""

    id: uuid.UUID
    name: str
    team_id: uuid.UUID
    collection_count: int
    document_count: int
    created_at: datetime


class IntegrationDetail(BaseModel):
    """Deliberately no can_edit field: every endpoint on this router already
    requires team membership to return anything at all (Integration has no
    public/anonymous-readable path, unlike ApiDocument/Collection), so
    can_edit would always be true and adds no information. direct_document_count
    is the same direct-only count as IntegrationSummary.document_count, named
    explicitly here since this response also implies the richer merged view
    a caller can get from GET /{id}/documents."""

    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    description: str | None
    collection_count: int
    direct_document_count: int
    created_at: datetime


class IntegrationDocumentSource(BaseModel):
    """One way a document is reachable from an Integration - either a direct
    IntegrationDocument link (collection_id/collection_name null) or via one
    specific member Collection (both set). GET /{id}/documents attaches one
    of these per distinct way a document is reachable - see
    integrations/router.py's _compute_document_sources."""

    type: Literal["direct", "collection"]
    collection_id: uuid.UUID | None = None
    collection_name: str | None = None


class IntegrationDocumentOut(ApiDocumentSummary):
    """GET /{id}/documents list item: the same summary fields as
    ApiDocumentSummary, plus the merged, de-duplicated sources list above -
    one entry per document, never repeated even when reachable multiple
    ways."""

    sources: list[IntegrationDocumentSource]


class IntegrationKBCollectionGroup(BaseModel):
    """One member Collection's own KB pages, as seen through an Integration's
    merged view (GET /{id}/kb) - see integrations/router.py's _compute_kb.
    Read-only from the integration's perspective: editing one of these pages
    only ever happens through the collection's own endpoints
    (app/api/collections/router.py's kb/pages routes), never through this
    router."""

    collection_id: uuid.UUID
    collection_name: str
    pages: list[KnowledgeBasePageOut]


class IntegrationKBOut(BaseModel):
    """GET /{id}/kb response. collection_pages is computed live at read time
    from every currently member Collection - never copied, so editing a
    collection's page through the collection's own endpoint is reflected
    here immediately with no extra step. own_pages is this integration's own
    KnowledgeBasePage rows (integration_id set, collection_id null) -
    created/edited only through this router's own kb/pages endpoints below,
    never touching any collection."""

    collection_pages: list[IntegrationKBCollectionGroup]
    own_pages: list[KnowledgeBasePageOut]
