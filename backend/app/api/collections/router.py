# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_docs.schemas import ApiDocumentSummary
from app.api.collections.schemas import (
    CollectionCreate,
    CollectionDetail,
    CollectionSummary,
    CollectionUpdate,
    KnowledgeBasePageCreate,
    KnowledgeBasePageOut,
    KnowledgeBasePageUpdate,
)
from app.api.deps import get_current_user, get_current_user_optional, is_team_member, require_team_membership
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.collection import Collection, CollectionDocument
from app.models.knowledge_base import KnowledgeBasePage
from app.models.notification import Subscription
from app.models.team import TeamMembership
from app.models.user import User

router = APIRouter()


async def _get_collection_or_404(db: AsyncSession, collection_id: uuid.UUID) -> Collection:
    collection = await db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


async def _require_visible_collection(
    db: AsyncSession, collection_id: uuid.UUID, current_user: User | None
) -> tuple[Collection, bool]:
    """Shared by every same-visibility-as-parent endpoint (GET /{id}, its
    /documents list, and subscribe): 200 if public or the caller is a team
    member, else 404 - never 403, so an unauthorized caller can't tell a
    private collection from one that doesn't exist. Mirrors
    app/api/api_docs/router.py's _require_visible_document exactly, one
    level up the domain model."""
    collection = await _get_collection_or_404(db, collection_id)
    is_member = current_user is not None and await is_team_member(db, collection.team_id, current_user.id)
    if not collection.is_public and not is_member:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection, is_member


async def _require_member_collection(db: AsyncSession, collection_id: uuid.UUID, user: User) -> Collection:
    collection = await _get_collection_or_404(db, collection_id)
    if not await is_team_member(db, collection.team_id, user.id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


async def _document_count(db: AsyncSession, collection_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(CollectionDocument)
        .where(CollectionDocument.collection_id == collection_id)
    )
    return count or 0


def _to_summary(collection: Collection, document_count: int) -> CollectionSummary:
    return CollectionSummary(
        id=collection.id,
        name=collection.name,
        team_id=collection.team_id,
        is_public=collection.is_public,
        document_count=document_count,
        created_at=collection.created_at,
    )


async def _get_is_subscribed(db: AsyncSession, collection_id: uuid.UUID, user: User | None) -> bool | None:
    """None for an anonymous caller (see CollectionDetail.is_subscribed);
    otherwise whether a Subscription row exists for this exact
    user+collection pair - not gated by team membership, per CLAUDE.md's
    domain model. Mirrors app/api/api_docs/router.py's _get_is_subscribed."""
    if user is None:
        return None
    result = await db.execute(
        select(Subscription.id).where(
            Subscription.user_id == user.id, Subscription.collection_id == collection_id
        )
    )
    return result.scalar_one_or_none() is not None


async def _build_detail(
    db: AsyncSession, collection: Collection, can_edit: bool, current_user: User | None
) -> CollectionDetail:
    document_count = await _document_count(db, collection.id)
    is_subscribed = await _get_is_subscribed(db, collection.id, current_user)
    return CollectionDetail(
        id=collection.id,
        team_id=collection.team_id,
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        document_count=document_count,
        created_at=collection.created_at,
        can_edit=can_edit,
        is_subscribed=is_subscribed,
    )


@router.post("", status_code=201)
async def create_collection(
    body: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionDetail:
    await require_team_membership(db, body.team_id, current_user)

    collection = Collection(
        team_id=body.team_id,
        name=body.name,
        description=body.description,
        created_by_user_id=current_user.id,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    return await _build_detail(db, collection, can_edit=True, current_user=current_user)


@router.get("")
async def list_collections(
    team_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollectionSummary]:
    document_count_subq = (
        select(CollectionDocument.collection_id, func.count(CollectionDocument.id).label("document_count"))
        .group_by(CollectionDocument.collection_id)
        .subquery()
    )
    stmt = (
        select(Collection, func.coalesce(document_count_subq.c.document_count, 0))
        .join(TeamMembership, TeamMembership.team_id == Collection.team_id)
        .outerjoin(document_count_subq, document_count_subq.c.collection_id == Collection.id)
        .where(TeamMembership.user_id == current_user.id)
        .order_by(Collection.name.asc())
    )
    if team_id is not None:
        stmt = stmt.where(Collection.team_id == team_id)

    rows = (await db.execute(stmt)).all()
    return [_to_summary(collection, count) for collection, count in rows]


@router.get("/{collection_id}")
async def get_collection(
    collection_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CollectionDetail:
    collection, is_member = await _require_visible_collection(db, collection_id, current_user)
    return await _build_detail(db, collection, can_edit=is_member, current_user=current_user)


@router.patch("/{collection_id}")
async def update_collection(
    collection_id: uuid.UUID,
    body: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionDetail:
    collection = await _require_member_collection(db, collection_id, current_user)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(collection, field, value)
    await db.commit()
    await db.refresh(collection)

    return await _build_detail(db, collection, can_edit=True, current_user=current_user)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """CollectionDocument, IntegrationCollection, Subscription
    (collection_id) and KnowledgeBasePage (collection_id) all have
    ondelete="CASCADE" on their FK to collections.id, so db.delete here is
    enough to clean up all of those rows too. Unlike ApiDocument, a
    Collection has no on-disk files of its own, so no storage cleanup step is
    needed here (see api_docs/router.py's delete_document)."""
    collection = await _require_member_collection(db, collection_id, current_user)
    await db.delete(collection)
    await db.commit()


@router.get("/{collection_id}/documents")
async def list_collection_documents(
    collection_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[ApiDocumentSummary]:
    collection, _ = await _require_visible_collection(db, collection_id, current_user)

    current_version_subq = (
        select(ApiDocumentVersion.documentation_id, ApiDocumentVersion.version)
        .where(ApiDocumentVersion.archived_at.is_(None))
        .subquery()
    )
    stmt = (
        select(ApiDocument, current_version_subq.c.version)
        .join(CollectionDocument, CollectionDocument.documentation_id == ApiDocument.id)
        .outerjoin(current_version_subq, current_version_subq.c.documentation_id == ApiDocument.id)
        .where(CollectionDocument.collection_id == collection.id)
        .order_by(ApiDocument.title.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        ApiDocumentSummary(
            id=doc.id,
            title=doc.title,
            team_id=doc.team_id,
            is_public=doc.is_public,
            recheck_period=doc.recheck_period,
            last_checked_at=doc.last_checked_at,
            last_check_error=doc.last_check_error,
            current_version=version,
        )
        for doc, version in rows
    ]


@router.post("/{collection_id}/documents/{documentation_id}", status_code=204)
async def add_document_to_collection(
    collection_id: uuid.UUID,
    documentation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Member-only of the collection's own team. The target document must be
    visible to that team - either it's already owned by the same team, or
    it's public (cross-team aggregation is allowed when the target is
    public, per the plan's locked-in assumption) - 404 otherwise, same
    can't-tell-private-from-nonexistent rule as everywhere else in this
    codebase. Idempotent via ON CONFLICT DO NOTHING against
    CollectionDocument's (collection_id, documentation_id) unique
    constraint - a plain (non-partial) UniqueConstraint, so index_elements
    alone is a sufficient arbiter here (unlike Subscription's partial
    indexes elsewhere in this router/api_docs's own subscribe endpoint)."""
    collection = await _require_member_collection(db, collection_id, current_user)

    doc = await db.get(ApiDocument, documentation_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.team_id != collection.team_id and not doc.is_public:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.execute(
        pg_insert(CollectionDocument)
        .values(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=current_user.id)
        .on_conflict_do_nothing(
            index_elements=[CollectionDocument.collection_id, CollectionDocument.documentation_id]
        )
    )
    await db.commit()


@router.delete("/{collection_id}/documents/{documentation_id}", status_code=204)
async def remove_document_from_collection(
    collection_id: uuid.UUID,
    documentation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Member-only of the collection's team; unlike add, no visibility
    re-check against the document itself - removing a row that's there is
    always fine regardless of whether the document would still qualify to be
    re-added today. Idempotent: removing zero matching rows is a success,
    not an error."""
    collection = await _require_member_collection(db, collection_id, current_user)

    result = await db.execute(
        select(CollectionDocument).where(
            CollectionDocument.collection_id == collection.id,
            CollectionDocument.documentation_id == documentation_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()


@router.post("/{collection_id}/subscribe", status_code=204)
async def subscribe_to_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Any logged-in user may subscribe to any collection they can currently
    see - public, or their own team's - mirrors
    app/api/api_docs/router.py's subscribe_to_document exactly, one level up
    the domain model. Idempotent via ON CONFLICT DO NOTHING against
    Subscription's (user_id, collection_id) partial unique index -
    index_where must match the index's own predicate for Postgres to infer
    it as the arbiter, same reasoning as subscribe_to_document's
    index_where=documentation_id.isnot(None)."""
    collection, _ = await _require_visible_collection(db, collection_id, current_user)
    await db.execute(
        pg_insert(Subscription)
        .values(user_id=current_user.id, collection_id=collection.id)
        .on_conflict_do_nothing(
            index_elements=[Subscription.user_id, Subscription.collection_id],
            index_where=Subscription.collection_id.isnot(None),
        )
    )
    await db.commit()


@router.delete("/{collection_id}/subscribe", status_code=204)
async def unsubscribe_from_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deliberately not gated on collection visibility - a caller who already
    subscribed can always remove their own subscription even if the
    collection's visibility changed since. Idempotent: removing zero
    matching rows is a success, not an error. Mirrors
    app/api/api_docs/router.py's unsubscribe_from_document."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id, Subscription.collection_id == collection_id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is not None:
        await db.delete(subscription)
        await db.commit()


async def _get_kb_page_or_404(db: AsyncSession, collection_id: uuid.UUID, page_id: uuid.UUID) -> KnowledgeBasePage:
    """404s if page_id doesn't belong to this exact collection_id - this is
    what guarantees editing one collection's KB can never touch a page
    belonging to a different collection or to an integration (an
    integration-owned page always has collection_id NULL, so it can never
    match here either)."""
    result = await db.execute(
        select(KnowledgeBasePage).where(
            KnowledgeBasePage.id == page_id, KnowledgeBasePage.collection_id == collection_id
        )
    )
    page = result.scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Knowledge base page not found")
    return page


def _to_kb_page_out(page: KnowledgeBasePage) -> KnowledgeBasePageOut:
    return KnowledgeBasePageOut(
        id=page.id,
        title=page.title,
        content=page.content,
        position=page.position,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


@router.post("/{collection_id}/kb/pages", status_code=201)
async def create_kb_page(
    collection_id: uuid.UUID,
    body: KnowledgeBasePageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBasePageOut:
    collection = await _require_member_collection(db, collection_id, current_user)

    page = KnowledgeBasePage(
        collection_id=collection.id,
        title=body.title,
        content=body.content,
        position=body.position,
        created_by_user_id=current_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)

    return _to_kb_page_out(page)


@router.get("/{collection_id}/kb/pages")
async def list_kb_pages(
    collection_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBasePageOut]:
    """Same visibility as the collection itself - a public collection's KB is
    publicly readable, only editing is member-gated (CLAUDE.md's KB
    section)."""
    collection, _ = await _require_visible_collection(db, collection_id, current_user)

    rows = (
        (
            await db.execute(
                select(KnowledgeBasePage)
                .where(KnowledgeBasePage.collection_id == collection.id)
                .order_by(KnowledgeBasePage.position.asc(), KnowledgeBasePage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_kb_page_out(page) for page in rows]


@router.patch("/{collection_id}/kb/pages/{page_id}")
async def update_kb_page(
    collection_id: uuid.UUID,
    page_id: uuid.UUID,
    body: KnowledgeBasePageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBasePageOut:
    await _require_member_collection(db, collection_id, current_user)
    page = await _get_kb_page_or_404(db, collection_id, page_id)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(page, field, value)
    await db.commit()
    await db.refresh(page)

    return _to_kb_page_out(page)


@router.delete("/{collection_id}/kb/pages/{page_id}", status_code=204)
async def delete_kb_page(
    collection_id: uuid.UUID,
    page_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_member_collection(db, collection_id, current_user)
    page = await _get_kb_page_or_404(db, collection_id, page_id)
    await db.delete(page)
    await db.commit()
