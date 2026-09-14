# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.collections.schemas import CollectionSummary
from app.api.deps import get_current_user, is_team_member, require_team_membership
from app.api.integrations.schemas import (
    IntegrationCreate,
    IntegrationDetail,
    IntegrationDocumentOut,
    IntegrationDocumentSource,
    IntegrationSummary,
    IntegrationUpdate,
)
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.collection import Collection, CollectionDocument
from app.models.integration import Integration, IntegrationCollection, IntegrationDocument
from app.models.team import TeamMembership
from app.models.user import User

router = APIRouter()

# Every endpoint below depends on get_current_user (auth required, never
# get_current_user_optional) and then, where a specific integration is
# involved, on _require_member_integration - there is no public/anonymous
# path for Integration at all (unlike ApiDocument/Collection). This means a
# truly anonymous request (no bearer token) never reaches an endpoint's own
# body: FastAPI's HTTPBearer (auto_error=True, app/security/jwt.py's
# bearer_scheme) rejects it with 401/403 first. Only a request carrying a
# valid token for a user who genuinely isn't a team member reaches the
# application-level 404 below - the "can't tell a private resource from one
# that doesn't exist" rule (CLAUDE.md) applies at that layer, and explicitly
# does NOT relax just because the integration has a public member collection
# or document - visibility of the integration itself never inherits from its
# members' own visibility.


async def _get_integration_or_404(db: AsyncSession, integration_id: uuid.UUID) -> Integration:
    integration = await db.get(Integration, integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


async def _require_member_integration(db: AsyncSession, integration_id: uuid.UUID, user: User) -> Integration:
    integration = await _get_integration_or_404(db, integration_id)
    if not await is_team_member(db, integration.team_id, user.id):
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


async def _collection_count(db: AsyncSession, integration_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(IntegrationCollection)
        .where(IntegrationCollection.integration_id == integration_id)
    )
    return count or 0


async def _direct_document_count(db: AsyncSession, integration_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(IntegrationDocument)
        .where(IntegrationDocument.integration_id == integration_id)
    )
    return count or 0


def _to_summary(integration: Integration, collection_count: int, document_count: int) -> IntegrationSummary:
    return IntegrationSummary(
        id=integration.id,
        name=integration.name,
        team_id=integration.team_id,
        collection_count=collection_count,
        document_count=document_count,
        created_at=integration.created_at,
    )


async def _build_detail(db: AsyncSession, integration: Integration) -> IntegrationDetail:
    collection_count = await _collection_count(db, integration.id)
    direct_document_count = await _direct_document_count(db, integration.id)
    return IntegrationDetail(
        id=integration.id,
        team_id=integration.team_id,
        name=integration.name,
        description=integration.description,
        collection_count=collection_count,
        direct_document_count=direct_document_count,
        created_at=integration.created_at,
    )


@router.post("", status_code=201)
async def create_integration(
    body: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationDetail:
    await require_team_membership(db, body.team_id, current_user)

    integration = Integration(
        team_id=body.team_id,
        name=body.name,
        description=body.description,
        created_by_user_id=current_user.id,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    return await _build_detail(db, integration)


@router.get("")
async def list_integrations(
    team_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationSummary]:
    collection_count_subq = (
        select(
            IntegrationCollection.integration_id,
            func.count(IntegrationCollection.id).label("collection_count"),
        )
        .group_by(IntegrationCollection.integration_id)
        .subquery()
    )
    document_count_subq = (
        select(
            IntegrationDocument.integration_id,
            func.count(IntegrationDocument.id).label("document_count"),
        )
        .group_by(IntegrationDocument.integration_id)
        .subquery()
    )
    stmt = (
        select(
            Integration,
            func.coalesce(collection_count_subq.c.collection_count, 0),
            func.coalesce(document_count_subq.c.document_count, 0),
        )
        .join(TeamMembership, TeamMembership.team_id == Integration.team_id)
        .outerjoin(collection_count_subq, collection_count_subq.c.integration_id == Integration.id)
        .outerjoin(document_count_subq, document_count_subq.c.integration_id == Integration.id)
        .where(TeamMembership.user_id == current_user.id)
        .order_by(Integration.name.asc())
    )
    if team_id is not None:
        stmt = stmt.where(Integration.team_id == team_id)

    rows = (await db.execute(stmt)).all()
    return [
        _to_summary(integration, collection_count, document_count)
        for integration, collection_count, document_count in rows
    ]


@router.get("/{integration_id}")
async def get_integration(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationDetail:
    integration = await _require_member_integration(db, integration_id, current_user)
    return await _build_detail(db, integration)


@router.patch("/{integration_id}")
async def update_integration(
    integration_id: uuid.UUID,
    body: IntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationDetail:
    integration = await _require_member_integration(db, integration_id, current_user)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(integration, field, value)
    await db.commit()
    await db.refresh(integration)

    return await _build_detail(db, integration)


@router.get("/{integration_id}/collections")
async def list_integration_collections(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollectionSummary]:
    integration = await _require_member_integration(db, integration_id, current_user)

    document_count_subq = (
        select(CollectionDocument.collection_id, func.count(CollectionDocument.id).label("document_count"))
        .group_by(CollectionDocument.collection_id)
        .subquery()
    )
    stmt = (
        select(Collection, func.coalesce(document_count_subq.c.document_count, 0))
        .join(IntegrationCollection, IntegrationCollection.collection_id == Collection.id)
        .outerjoin(document_count_subq, document_count_subq.c.collection_id == Collection.id)
        .where(IntegrationCollection.integration_id == integration.id)
        .order_by(Collection.name.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        CollectionSummary(
            id=collection.id,
            name=collection.name,
            team_id=collection.team_id,
            is_public=collection.is_public,
            document_count=document_count,
            created_at=collection.created_at,
        )
        for collection, document_count in rows
    ]


@router.post("/{integration_id}/collections/{collection_id}", status_code=204)
async def add_collection_to_integration(
    integration_id: uuid.UUID,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Member-only of the integration's own team. The target collection must
    be visible to that team - own-team or public (cross-team aggregation is
    allowed when the target is public, same locked-in assumption as
    collections/router.py's add_document_to_collection) - 404 otherwise.
    Idempotent via ON CONFLICT DO NOTHING against IntegrationCollection's
    plain (non-partial) UniqueConstraint - index_elements alone is a
    sufficient arbiter here, same reasoning as CollectionDocument's own add
    endpoint."""
    integration = await _require_member_integration(db, integration_id, current_user)

    collection = await db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    if collection.team_id != integration.team_id and not collection.is_public:
        raise HTTPException(status_code=404, detail="Collection not found")

    await db.execute(
        pg_insert(IntegrationCollection)
        .values(integration_id=integration.id, collection_id=collection.id, added_by_user_id=current_user.id)
        .on_conflict_do_nothing(
            index_elements=[IntegrationCollection.integration_id, IntegrationCollection.collection_id]
        )
    )
    await db.commit()


@router.delete("/{integration_id}/collections/{collection_id}", status_code=204)
async def remove_collection_from_integration(
    integration_id: uuid.UUID,
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Member-only of the integration's team; unlike add, no re-check of the
    collection's own visibility - removing a link that's there is always
    fine. Idempotent: removing zero matching rows is a success, not an
    error."""
    integration = await _require_member_integration(db, integration_id, current_user)

    result = await db.execute(
        select(IntegrationCollection).where(
            IntegrationCollection.integration_id == integration.id,
            IntegrationCollection.collection_id == collection_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()


async def _compute_document_sources(
    db: AsyncSession, integration_id: uuid.UUID
) -> dict[uuid.UUID, list[IntegrationDocumentSource]]:
    """Merges direct IntegrationDocument members with every member
    Collection's own CollectionDocument members, keyed by documentation_id -
    the shared assembly step behind list_integration_documents below. A
    document reachable multiple ways (direct and/or through more than one
    member collection) collects one source entry per distinct way; the
    document itself is never duplicated by this step, only its sources list
    grows."""
    sources: dict[uuid.UUID, list[IntegrationDocumentSource]] = {}

    direct_ids = (
        (
            await db.execute(
                select(IntegrationDocument.documentation_id).where(
                    IntegrationDocument.integration_id == integration_id
                )
            )
        )
        .scalars()
        .all()
    )
    for documentation_id in direct_ids:
        sources.setdefault(documentation_id, []).append(IntegrationDocumentSource(type="direct"))

    collection_rows = (
        await db.execute(
            select(CollectionDocument.documentation_id, Collection.id, Collection.name)
            .select_from(IntegrationCollection)
            .join(Collection, Collection.id == IntegrationCollection.collection_id)
            .join(CollectionDocument, CollectionDocument.collection_id == Collection.id)
            .where(IntegrationCollection.integration_id == integration_id)
        )
    ).all()
    for documentation_id, collection_id, collection_name in collection_rows:
        sources.setdefault(documentation_id, []).append(
            IntegrationDocumentSource(type="collection", collection_id=collection_id, collection_name=collection_name)
        )

    return sources


@router.get("/{integration_id}/documents")
async def list_integration_documents(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationDocumentOut]:
    """The merged, de-duplicated, source-tagged effective document list:
    direct IntegrationDocument members plus every document belonging to a
    member Collection, unioned by documentation_id. Each ApiDocument row
    (+ its current version, same current_version_subq pattern as
    api_docs/collections routers) is fetched only once per distinct id via a
    single IN query against the id set _compute_document_sources already
    resolved."""
    integration = await _require_member_integration(db, integration_id, current_user)

    sources_by_document = await _compute_document_sources(db, integration.id)
    if not sources_by_document:
        return []

    current_version_subq = (
        select(ApiDocumentVersion.documentation_id, ApiDocumentVersion.version)
        .where(ApiDocumentVersion.archived_at.is_(None))
        .subquery()
    )
    stmt = (
        select(ApiDocument, current_version_subq.c.version)
        .outerjoin(current_version_subq, current_version_subq.c.documentation_id == ApiDocument.id)
        .where(ApiDocument.id.in_(sources_by_document.keys()))
        .order_by(ApiDocument.title.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        IntegrationDocumentOut(
            id=doc.id,
            title=doc.title,
            team_id=doc.team_id,
            is_public=doc.is_public,
            recheck_period=doc.recheck_period,
            last_checked_at=doc.last_checked_at,
            last_check_error=doc.last_check_error,
            current_version=version,
            sources=sources_by_document[doc.id],
        )
        for doc, version in rows
    ]


@router.post("/{integration_id}/documents/{documentation_id}", status_code=204)
async def add_document_to_integration(
    integration_id: uuid.UUID,
    documentation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Member-only of the integration's own team. Adds a DIRECT link only -
    never touches any collection. The target document must be visible to
    that team - own-team or public - 404 otherwise, same rule as
    add_collection_to_integration above. Idempotent via ON CONFLICT DO
    NOTHING against IntegrationDocument's plain UniqueConstraint."""
    integration = await _require_member_integration(db, integration_id, current_user)

    doc = await db.get(ApiDocument, documentation_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.team_id != integration.team_id and not doc.is_public:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.execute(
        pg_insert(IntegrationDocument)
        .values(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=current_user.id)
        .on_conflict_do_nothing(
            index_elements=[IntegrationDocument.integration_id, IntegrationDocument.documentation_id]
        )
    )
    await db.commit()


@router.delete("/{integration_id}/documents/{documentation_id}", status_code=204)
async def remove_document_from_integration(
    integration_id: uuid.UUID,
    documentation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Member-only of the integration's team. Removes only the DIRECT link if
    present - a document still reachable via a member collection stays
    reachable through GET /{integration_id}/documents; this never touches
    CollectionDocument. Idempotent: removing zero matching rows is a
    success, not an error."""
    integration = await _require_member_integration(db, integration_id, current_user)

    result = await db.execute(
        select(IntegrationDocument).where(
            IntegrationDocument.integration_id == integration.id,
            IntegrationDocument.documentation_id == documentation_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()
