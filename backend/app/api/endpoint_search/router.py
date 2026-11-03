# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.api.endpoint_search.schemas import EndpointHitOut, EndpointSearchOut
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentEndpoint, ApiDocumentVersion
from app.models.team import TeamMembership
from app.models.user import User
from app.services.text_search import matches_all_terms

router = APIRouter()

MAX_PAGE_SIZE = 100
_DESCRIPTION_PREVIEW = 300


def _preview(text: str | None) -> str | None:
    if text is None or len(text) <= _DESCRIPTION_PREVIEW:
        return text
    return text[: _DESCRIPTION_PREVIEW - 1].rstrip() + "…"


@router.get("")
async def search_endpoints(
    q: str | None = Query(default=None, max_length=200),
    method: str | None = Query(default=None, max_length=20),
    document_id: uuid.UUID | None = None,
    spec_type: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> EndpointSearchOut:
    """Search the endpoints of the CURRENT version of every document the caller
    may see - the public ones, and for a signed-in user also those of their
    teams (anonymous callers get the public ones only; a document that is not
    visible is not mentioned at all). app/services/endpoint_index.py keeps the
    index; what an endpoint is for each kind of document is
    app/services/spec_outline.py's.

    q: every word must appear (case and diacritics ignored, see
    app/services/text_search.py) in the endpoint's method, path, name,
    description, tags or operation id, or in the document's title. A match in
    the path ranks first, then one in the name or operation id, then the rest;
    equal ranks are ordered by document title, path and method. Without q every
    visible endpoint is listed in that order. method: exact (case-insensitive),
    e.g. "post" or "QUERY"; spec_type: openapi / asyncapi / postman / graphql."""
    visible = ApiDocument.is_public.is_(True)
    if current_user is not None:
        visible = or_(
            visible,
            ApiDocument.team_id.in_(select(TeamMembership.team_id).where(TeamMembership.user_id == current_user.id)),
        )

    conditions = [visible]
    search = matches_all_terms(q, ApiDocumentEndpoint.search_text, ApiDocument.title)
    if search is not None:
        conditions.append(search)
    if method:
        conditions.append(ApiDocumentEndpoint.method == method.strip().upper())
    if document_id is not None:
        conditions.append(ApiDocumentEndpoint.documentation_id == document_id)
    if spec_type:
        conditions.append(ApiDocumentVersion.spec_type == spec_type.strip().lower())

    base = (
        select(ApiDocumentEndpoint, ApiDocument, ApiDocumentVersion)
        .join(ApiDocument, ApiDocument.id == ApiDocumentEndpoint.documentation_id)
        .join(ApiDocumentVersion, ApiDocumentVersion.id == ApiDocumentEndpoint.version_id)
        .where(*conditions)
    )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    path_hit = matches_all_terms(q, ApiDocumentEndpoint.path)
    name_hit = matches_all_terms(q, ApiDocumentEndpoint.name, ApiDocumentEndpoint.operation_id)
    ordering = [ApiDocument.title.asc(), ApiDocumentEndpoint.path.asc(), ApiDocumentEndpoint.method.asc()]
    if path_hit is not None and name_hit is not None:
        ordering.insert(0, case((path_hit, 0), (name_hit, 1), else_=2))

    rows = (await db.execute(base.order_by(*ordering).limit(page_size).offset((page - 1) * page_size))).all()
    return EndpointSearchOut(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            EndpointHitOut(
                document_id=doc.id,
                document_title=doc.title,
                team_id=doc.team_id,
                is_public=doc.is_public,
                version_id=version.id,
                version=version.version,
                spec_type=version.spec_type,
                method=endpoint.method,
                path=endpoint.path,
                name=endpoint.name,
                description=_preview(endpoint.description),
                tags=list(endpoint.tags or []),
                deprecated=endpoint.deprecated,
            )
            for endpoint, doc, version in rows
        ],
    )
