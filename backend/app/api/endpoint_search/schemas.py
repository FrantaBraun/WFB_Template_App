# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from pydantic import BaseModel


class EndpointHitOut(BaseModel):
    """One endpoint found by the search, with the document it belongs to and
    the current version it was found in. method / path are as in
    app/services/spec_outline.py: an HTTP method and path, an AsyncAPI
    direction and channel, or a GraphQL operation type and field name."""

    document_id: uuid.UUID
    document_title: str
    team_id: uuid.UUID
    is_public: bool
    version_id: uuid.UUID
    version: str
    spec_type: str
    method: str
    path: str
    name: str | None
    description: str | None
    tags: list[str]
    deprecated: bool


class EndpointSearchOut(BaseModel):
    """GET /api/endpoint-search: one page of hits, best match first, and the
    total number of hits over all pages."""

    total: int
    page: int
    page_size: int
    items: list[EndpointHitOut]
