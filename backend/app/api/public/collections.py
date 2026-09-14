# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.collections.schemas import CollectionSummary
from app.database import get_db
from app.models.collection import Collection, CollectionDocument

router = APIRouter()


@router.get("/collections")
async def list_public_collections(db: AsyncSession = Depends(get_db)) -> list[CollectionSummary]:
    """is_public=true collections only, no team scoping - same summary shape
    as GET /api/collections. Mirrors app/api/public/api_docs.py's pattern of
    no auth dependency at all (not even get_current_user_optional): this
    route behaves identically for every caller, signed in or not."""
    document_count_subq = (
        select(CollectionDocument.collection_id, func.count(CollectionDocument.id).label("document_count"))
        .group_by(CollectionDocument.collection_id)
        .subquery()
    )
    stmt = (
        select(Collection, func.coalesce(document_count_subq.c.document_count, 0))
        .outerjoin(document_count_subq, document_count_subq.c.collection_id == Collection.id)
        .where(Collection.is_public.is_(True))
        .order_by(Collection.name.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        CollectionSummary(
            id=collection.id,
            name=collection.name,
            team_id=collection.team_id,
            is_public=collection.is_public,
            document_count=count,
            created_at=collection.created_at,
        )
        for collection, count in rows
    ]
