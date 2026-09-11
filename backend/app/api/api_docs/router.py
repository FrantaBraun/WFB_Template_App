# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_docs.schemas import (
    ApiDocumentCreate,
    ApiDocumentCurrentVersion,
    ApiDocumentDetail,
    ApiDocumentSummary,
    ApiDocumentUpdate,
    ApiDocumentVersionOut,
)
from app.api.deps import get_current_user, get_current_user_optional
from app.config import Settings, get_settings
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.team import TeamMembership
from app.models.user import User
from app.services.api_document_versions import get_current_version, process_new_spec
from app.services.openapi_spec import SpecValidationError, fetch_spec_from_url
from app.services.spec_storage import read_spec_file

router = APIRouter()


async def _require_team_membership(db: AsyncSession, team_id: uuid.UUID, user: User) -> None:
    """A team the caller isn't a member of is indistinguishable from one
    that doesn't exist - 404, not 403 (same rule/pattern as
    app/api/teams/router.py's _require_membership)."""
    result = await db.execute(
        select(TeamMembership.id).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Team not found")


async def _is_team_member(db: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(TeamMembership.id).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


async def _get_document_or_404(db: AsyncSession, document_id: uuid.UUID) -> ApiDocument:
    doc = await db.get(ApiDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def _require_visible_document(
    db: AsyncSession, document_id: uuid.UUID, current_user: User | None
) -> tuple[ApiDocument, bool]:
    """Shared by every same-visibility-as-parent endpoint (GET /{id}, its
    /versions list, and the raw spec download): 200 if public or the caller
    is a team member, else 404 - never 403, so an unauthorized caller can't
    tell a private document from one that doesn't exist."""
    doc = await _get_document_or_404(db, document_id)
    is_member = current_user is not None and await _is_team_member(db, doc.team_id, current_user.id)
    if not doc.is_public and not is_member:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc, is_member


async def _require_member_document(db: AsyncSession, document_id: uuid.UUID, user: User) -> ApiDocument:
    doc = await _get_document_or_404(db, document_id)
    if not await _is_team_member(db, doc.team_id, user.id):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _validate_recheck_period(recheck_period: str, source_url: str | None) -> None:
    if recheck_period != "manual" and not source_url:
        raise HTTPException(
            status_code=422, detail="recheck_period other than 'manual' requires a source_url"
        )


def _to_summary(doc: ApiDocument, current_version: str | None) -> ApiDocumentSummary:
    return ApiDocumentSummary(
        id=doc.id,
        title=doc.title,
        team_id=doc.team_id,
        is_public=doc.is_public,
        recheck_period=doc.recheck_period,
        last_checked_at=doc.last_checked_at,
        last_check_error=doc.last_check_error,
        current_version=current_version,
    )


async def _build_detail(db: AsyncSession, doc: ApiDocument, can_edit: bool) -> ApiDocumentDetail:
    current = await get_current_version(db, doc.id)
    current_out = (
        ApiDocumentCurrentVersion(
            id=current.id,
            version=current.version,
            spec_title=current.spec_title,
            format=current.format,
            fetched_at=current.fetched_at,
            source=current.source,
        )
        if current is not None
        else None
    )
    return ApiDocumentDetail(
        id=doc.id,
        team_id=doc.team_id,
        title=doc.title,
        notes=doc.notes,
        source_url=doc.source_url,
        recheck_period=doc.recheck_period,
        is_public=doc.is_public,
        last_checked_at=doc.last_checked_at,
        last_check_error=doc.last_check_error,
        created_at=doc.created_at,
        current_version=current_out,
        can_edit=can_edit,
    )


async def _fetch_and_process(
    doc: ApiDocument, source: str, db: AsyncSession, settings: Settings
) -> ApiDocumentVersion | None:
    """Shared by create-by-URL and recheck. process_new_spec only ever sees
    already-fetched bytes (it takes raw: bytes, not a URL) so a fetch
    failure can't reach its own error handling - handled the same way here
    instead: set last_check_error, commit, surface as 422."""
    try:
        raw = await fetch_spec_from_url(doc.source_url, settings.spec_fetch_timeout_seconds)
    except httpx.HTTPError as exc:
        doc.last_check_error = str(exc)
        await db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return await process_new_spec(
            doc,
            raw,
            source=source,
            db=db,
            uploads_dir=settings.uploads_dir,
            max_size_bytes=settings.max_spec_file_size_bytes,
        )
    except SpecValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", status_code=201)
async def create_document(
    body: ApiDocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentDetail:
    await _require_team_membership(db, body.team_id, current_user)

    if not body.source_url:
        raise HTTPException(
            status_code=422,
            detail=(
                "source_url is required to create a document this way - "
                "use POST /api/api-docs/upload to create one from a file instead."
            ),
        )
    _validate_recheck_period(body.recheck_period, body.source_url)

    doc = ApiDocument(
        team_id=body.team_id,
        title=body.title,
        notes=body.notes,
        source_url=body.source_url,
        recheck_period=body.recheck_period,
        created_by_user_id=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Fetch/parse failure keeps this row (see _fetch_and_process) rather
    # than rolling it back - the caller can fix the URL and retry via
    # POST /{id}/recheck once that's available.
    await _fetch_and_process(doc, source="initial", db=db, settings=settings)

    return await _build_detail(db, doc, can_edit=True)


@router.post("/upload", status_code=201)
async def upload_document(
    team_id: uuid.UUID = Form(...),
    title: str = Form(...),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentDetail:
    await _require_team_membership(db, team_id, current_user)

    raw = await file.read()

    doc = ApiDocument(
        team_id=team_id,
        title=title,
        notes=notes,
        source_url=None,
        recheck_period="manual",
        created_by_user_id=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        await process_new_spec(
            doc,
            raw,
            source="initial",
            db=db,
            uploads_dir=settings.uploads_dir,
            max_size_bytes=settings.max_spec_file_size_bytes,
        )
    except SpecValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await _build_detail(db, doc, can_edit=True)


@router.get("")
async def list_documents(
    team_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiDocumentSummary]:
    current_version_subq = (
        select(ApiDocumentVersion.documentation_id, ApiDocumentVersion.version)
        .where(ApiDocumentVersion.archived_at.is_(None))
        .subquery()
    )
    stmt = (
        select(ApiDocument, current_version_subq.c.version)
        .join(TeamMembership, TeamMembership.team_id == ApiDocument.team_id)
        .outerjoin(current_version_subq, current_version_subq.c.documentation_id == ApiDocument.id)
        .where(TeamMembership.user_id == current_user.id)
        .order_by(ApiDocument.title.asc())
    )
    if team_id is not None:
        stmt = stmt.where(ApiDocument.team_id == team_id)

    rows = (await db.execute(stmt)).all()
    return [_to_summary(doc, version) for doc, version in rows]


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ApiDocumentDetail:
    doc, is_member = await _require_visible_document(db, document_id, current_user)
    return await _build_detail(db, doc, can_edit=is_member)


@router.patch("/{document_id}")
async def update_document(
    document_id: uuid.UUID,
    body: ApiDocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiDocumentDetail:
    doc = await _require_member_document(db, document_id, current_user)

    updates = body.model_dump(exclude_unset=True)
    resulting_recheck_period = updates.get("recheck_period", doc.recheck_period)
    resulting_source_url = updates.get("source_url", doc.source_url)
    _validate_recheck_period(resulting_recheck_period, resulting_source_url)

    for field, value in updates.items():
        setattr(doc, field, value)
    await db.commit()
    await db.refresh(doc)

    return await _build_detail(db, doc, can_edit=True)


@router.post("/{document_id}/recheck")
async def recheck_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentDetail:
    doc = await _require_member_document(db, document_id, current_user)
    if not doc.source_url:
        raise HTTPException(status_code=400, detail="This document has no source_url to recheck")

    await _fetch_and_process(doc, source="manual_recheck", db=db, settings=settings)

    return await _build_detail(db, doc, can_edit=True)


@router.post("/{document_id}/upload-version")
async def upload_document_version(
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentDetail:
    doc = await _require_member_document(db, document_id, current_user)
    raw = await file.read()

    try:
        await process_new_spec(
            doc,
            raw,
            source="manual_upload",
            db=db,
            uploads_dir=settings.uploads_dir,
            max_size_bytes=settings.max_spec_file_size_bytes,
        )
    except SpecValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await _build_detail(db, doc, can_edit=True)


@router.get("/{document_id}/versions")
async def list_document_versions(
    document_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[ApiDocumentVersionOut]:
    doc, _ = await _require_visible_document(db, document_id, current_user)

    result = await db.execute(
        select(ApiDocumentVersion)
        .where(ApiDocumentVersion.documentation_id == doc.id)
        .order_by(ApiDocumentVersion.fetched_at.desc())
    )
    return [
        ApiDocumentVersionOut(
            id=v.id,
            version=v.version,
            spec_title=v.spec_title,
            fetched_at=v.fetched_at,
            archived_at=v.archived_at,
            source=v.source,
        )
        for v in result.scalars().all()
    ]


@router.get("/{document_id}/versions/{version_id}/spec")
async def get_document_version_spec(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    doc, _ = await _require_visible_document(db, document_id, current_user)

    result = await db.execute(
        select(ApiDocumentVersion).where(
            ApiDocumentVersion.id == version_id,
            ApiDocumentVersion.documentation_id == doc.id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    content = read_spec_file(settings.uploads_dir, version.storage_path)
    media_type = "application/json" if version.format == "json" else "application/yaml"
    return Response(content=content, media_type=media_type)
