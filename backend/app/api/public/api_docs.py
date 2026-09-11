# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_docs.schemas import ApiDocumentSummary
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentVersion

router = APIRouter()


@router.get("/api-docs")
async def list_public_documents(db: AsyncSession = Depends(get_db)) -> list[ApiDocumentSummary]:
    """is_public=true documents only, no team scoping - same summary shape
    as GET /api/api-docs. Mirrors app/api/public/version.py's pattern of no
    auth dependency at all (not even get_current_user_optional): this route
    behaves identically for every caller, signed in or not."""
    current_version_subq = (
        select(ApiDocumentVersion.documentation_id, ApiDocumentVersion.version)
        .where(ApiDocumentVersion.archived_at.is_(None))
        .subquery()
    )
    stmt = (
        select(ApiDocument, current_version_subq.c.version)
        .outerjoin(current_version_subq, current_version_subq.c.documentation_id == ApiDocument.id)
        .where(ApiDocument.is_public.is_(True))
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
