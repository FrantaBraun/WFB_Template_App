# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import asyncio
import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_docs.schemas import (
    ApiDocumentCheckResult,
    ApiDocumentCreate,
    ApiDocumentCurrentVersion,
    ApiDocumentDetail,
    ApiDocumentSummary,
    ApiDocumentUpdate,
    ApiDocumentVersionOut,
    ChangeSummaryOut,
    IntegrationRefOut,
    SpecChangeOut,
    VersionChangesOut,
    VersionRefOut,
)
from app.api.author_messages.contact import build_author_out, contact_author
from app.api.author_messages.schemas import ContactAuthorBody, ContactAuthorResult
from app.api.deps import get_current_user, get_current_user_optional, is_team_member, require_team_membership
from app.config import Settings, get_settings
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.notification import Subscription
from app.models.team import TeamMembership
from app.models.user import User
from app.services.api_document_versions import fetch_and_process, get_current_version, process_new_spec
from app.services.integration_usage import integrations_using_documents
from app.services.openapi_spec import SpecValidationError, parse_spec
from app.services.spec_diff import diff_specs
from app.services.spec_storage import delete_document_files, read_spec_file
from app.services.text_search import matches_all_terms

router = APIRouter()


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
    is_member = current_user is not None and await is_team_member(db, doc.team_id, current_user.id)
    if not doc.is_public and not is_member:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc, is_member


async def _require_member_document(db: AsyncSession, document_id: uuid.UUID, user: User) -> ApiDocument:
    doc = await _get_document_or_404(db, document_id)
    if not await is_team_member(db, doc.team_id, user.id):
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


async def _get_is_subscribed(db: AsyncSession, document_id: uuid.UUID, user: User | None) -> bool | None:
    """None for an anonymous caller (see ApiDocumentDetail.is_subscribed);
    otherwise whether a Subscription row exists for this exact user+document
    pair - not gated by team membership, per CLAUDE.md's domain model."""
    if user is None:
        return None
    result = await db.execute(
        select(Subscription.id).where(
            Subscription.user_id == user.id, Subscription.documentation_id == document_id
        )
    )
    return result.scalar_one_or_none() is not None


async def _build_detail(
    db: AsyncSession, doc: ApiDocument, can_edit: bool, current_user: User | None
) -> ApiDocumentDetail:
    current = await get_current_version(db, doc.id)
    current_out = (
        ApiDocumentCurrentVersion(
            id=current.id,
            version=current.version,
            spec_title=current.spec_title,
            format=current.format,
            fetched_at=current.fetched_at,
            source=current.source,
            content_changed=current.content_changed,
            change_summary=ChangeSummaryOut.from_stored(current.change_summary),
        )
        if current is not None
        else None
    )
    is_subscribed = await _get_is_subscribed(db, doc.id, current_user)
    author = await build_author_out(
        db, created_by_user_id=doc.created_by_user_id, team_id=doc.team_id, viewer=current_user
    )
    # Integrations are team-private: only the viewer's own teams' are named.
    used_by = (
        await integrations_using_documents(db, [doc.id], user_id=current_user.id) if current_user is not None else {}
    ).get(doc.id, [])
    return ApiDocumentDetail(
        id=doc.id,
        team_id=doc.team_id,
        title=doc.title,
        notes=doc.notes,
        source_url=doc.source_url,
        docs_url=doc.docs_url,
        recheck_period=doc.recheck_period,
        is_public=doc.is_public,
        detect_content_changes=doc.detect_content_changes,
        last_checked_at=doc.last_checked_at,
        last_check_error=doc.last_check_error,
        created_at=doc.created_at,
        current_version=current_out,
        can_edit=can_edit,
        is_subscribed=is_subscribed,
        author=author,
        integrations=[IntegrationRefOut(id=ref.id, name=ref.name) for ref in used_by],
    )


async def _fetch_and_process(
    doc: ApiDocument, source: str, db: AsyncSession, settings: Settings
) -> ApiDocumentVersion | None:
    """Thin HTTP-error-translation wrapper around the service-layer
    fetch_and_process (app/services/api_document_versions.py) - shared by
    create-by-URL and manual recheck. fetch_and_process itself has no
    FastAPI dependency and lets httpx.HTTPError/SpecValidationError
    propagate as plain exceptions (app/services/scheduler.py's automatic
    recheck reuses it and reacts to those directly); this layer is the one
    place that turns either into HTTPException(422)."""
    try:
        return await fetch_and_process(doc, source=source, db=db, settings=settings)
    except (httpx.HTTPError, SpecValidationError) as exc:
        # httpx timeouts stringify to "" - the type name is better than nothing.
        raise HTTPException(status_code=422, detail=str(exc) or type(exc).__name__) from exc


async def _build_check_result(
    db: AsyncSession,
    doc: ApiDocument,
    current_user: User,
    previous_version: str | None,
    new_version: ApiDocumentVersion | None,
) -> ApiDocumentCheckResult:
    detail = await _build_detail(db, doc, can_edit=True, current_user=current_user)
    content_changed = new_version is not None and new_version.content_changed
    return ApiDocumentCheckResult(
        **detail.model_dump(),
        new_version_found=new_version is not None and not content_changed,
        content_changed=content_changed,
        previous_version=previous_version,
    )


@router.post("", status_code=201)
async def create_document(
    body: ApiDocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentDetail:
    await require_team_membership(db, body.team_id, current_user)

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
        docs_url=body.docs_url,
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

    return await _build_detail(db, doc, can_edit=True, current_user=current_user)


@router.post("/upload", status_code=201)
async def upload_document(
    team_id: uuid.UUID = Form(...),
    title: str = Form(...),
    notes: str | None = Form(None),
    docs_url: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentDetail:
    await require_team_membership(db, team_id, current_user)

    raw = await file.read()

    doc = ApiDocument(
        team_id=team_id,
        title=title,
        notes=notes,
        source_url=None,
        docs_url=docs_url,
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

    return await _build_detail(db, doc, can_edit=True, current_user=current_user)


@router.get("")
async def list_documents(
    team_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiDocumentSummary]:
    """q: free-text search over title and notes - see app/services/text_search.py."""
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
    search = matches_all_terms(q, ApiDocument.title, ApiDocument.notes)
    if search is not None:
        stmt = stmt.where(search)

    rows = (await db.execute(stmt)).all()
    return [_to_summary(doc, version) for doc, version in rows]


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ApiDocumentDetail:
    doc, is_member = await _require_visible_document(db, document_id, current_user)
    return await _build_detail(db, doc, can_edit=is_member, current_user=current_user)


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

    return await _build_detail(db, doc, can_edit=True, current_user=current_user)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Every other table referencing this document (ApiDocumentVersion,
    CollectionDocument, IntegrationDocument, Subscription, Notification) has
    ondelete="CASCADE" on its FK to api_documents.id, so db.delete here is
    enough to clean up all of those rows too - no manual cleanup needed.
    On-disk spec files aren't covered by that cascade, so they're removed
    first via delete_document_files (best-effort - see its own docstring)."""
    doc = await _require_member_document(db, document_id, current_user)

    delete_document_files(settings.uploads_dir, doc.id)
    await db.delete(doc)
    await db.commit()


@router.post("/{document_id}/recheck")
async def recheck_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentCheckResult:
    doc = await _require_member_document(db, document_id, current_user)
    if not doc.source_url:
        raise HTTPException(status_code=400, detail="This document has no source_url to recheck")

    # Read as a plain string up front: processing archives (and expires) the row.
    current = await get_current_version(db, doc.id)
    previous_version = current.version if current is not None else None
    new_version = await _fetch_and_process(doc, source="manual_recheck", db=db, settings=settings)

    return await _build_check_result(db, doc, current_user, previous_version, new_version)


@router.post("/{document_id}/upload-version")
async def upload_document_version(
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ApiDocumentCheckResult:
    doc = await _require_member_document(db, document_id, current_user)
    raw = await file.read()

    current = await get_current_version(db, doc.id)
    previous_version = current.version if current is not None else None
    try:
        new_version = await process_new_spec(
            doc,
            raw,
            source="manual_upload",
            db=db,
            uploads_dir=settings.uploads_dir,
            max_size_bytes=settings.max_spec_file_size_bytes,
        )
    except SpecValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await _build_check_result(db, doc, current_user, previous_version, new_version)


@router.post("/{document_id}/subscribe", status_code=204)
async def subscribe_to_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Any logged-in user may subscribe to any document they can currently
    see - public, or their own team's - not gated by membership beyond that
    (see CLAUDE.md's domain model). Idempotent via ON CONFLICT DO NOTHING
    against Subscription's (user_id, documentation_id) partial unique index
    (app/models/notification.py - Phase 5 replaced the plain unique
    constraint with two partial ones, one per subscription target), rather
    than a naive check-then-insert, for the same near-simultaneous-request
    race reason as app/api/deps.py's _resolve_current_user. Postgres only
    infers a partial index as the ON CONFLICT arbiter when the inference
    clause's own index_where matches the index's predicate - index_elements
    alone (sufficient back when this was a plain unique constraint) silently
    stops matching anything once the index becomes partial."""
    doc, _ = await _require_visible_document(db, document_id, current_user)
    await db.execute(
        pg_insert(Subscription)
        .values(user_id=current_user.id, documentation_id=doc.id)
        .on_conflict_do_nothing(
            index_elements=[Subscription.user_id, Subscription.documentation_id],
            index_where=Subscription.documentation_id.isnot(None),
        )
    )
    await db.commit()


@router.delete("/{document_id}/subscribe", status_code=204)
async def unsubscribe_from_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deliberately not gated on document visibility - a caller who already
    subscribed can always remove their own subscription even if the
    document's visibility changed since. Idempotent: removing zero matching
    rows is a success, not an error."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id, Subscription.documentation_id == document_id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is not None:
        await db.delete(subscription)
        await db.commit()


@router.post("/{document_id}/contact-author", status_code=201)
async def contact_document_author(
    document_id: uuid.UUID,
    body: ContactAuthorBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ContactAuthorResult:
    """Any signed-in user who can currently see the document - public, or
    their own team's - may write to the person who created it: an in-app
    notification plus an e-mail (Reply-To is the sender's address). 404 for a
    document the caller cannot see, 422 for the author themselves, 403 when
    the author has switched messages off, 429 past the hourly limit
    (app/services/author_contact.py)."""
    doc, _ = await _require_visible_document(db, document_id, current_user)
    return await contact_author(db, settings, sender=current_user, message=body.message, document=doc)


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
            content_changed=v.content_changed,
            change_summary=ChangeSummaryOut.from_stored(v.change_summary),
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


def _diff_files(old_raw: bytes, new_raw: bytes):
    """Parse and compare two stored spec files - CPU work that can take a
    moment on a big spec, so the caller runs it off the event loop."""
    return diff_specs(parse_spec(old_raw).document, parse_spec(new_raw).document)


@router.get("/{document_id}/versions/{version_id}/changes")
async def get_document_version_changes(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    against: uuid.UUID | None = None,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VersionChangesOut:
    """What changed from another version of this document to this one
    (app/services/spec_diff.py): `against` if given, else the version just
    before this one in the history. Same visibility as the version list. 404
    for a version that is not this document's, for the oldest version when
    no `against` is given (nothing earlier to compare with), and when a
    stored spec file is gone; 422 when a stored file no longer parses."""
    doc, _ = await _require_visible_document(db, document_id, current_user)

    versions = (
        (
            await db.execute(
                select(ApiDocumentVersion)
                .where(ApiDocumentVersion.documentation_id == doc.id)
                .order_by(ApiDocumentVersion.fetched_at.desc(), ApiDocumentVersion.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    by_id = {v.id: v for v in versions}
    target = by_id.get(version_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if against is not None:
        base = by_id.get(against)
        if base is None:
            raise HTTPException(status_code=404, detail="Version to compare against not found")
    else:
        older = versions[versions.index(target) + 1 :]
        if not older:
            raise HTTPException(status_code=404, detail="There is no earlier version to compare with")
        base = older[0]

    try:
        old_raw = read_spec_file(settings.uploads_dir, base.storage_path)
        new_raw = read_spec_file(settings.uploads_dir, target.storage_path)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="A specification file of these versions is no longer available") from exc
    try:
        diff = await asyncio.to_thread(_diff_files, old_raw, new_raw)
    except SpecValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def ref(version: ApiDocumentVersion) -> VersionRefOut:
        return VersionRefOut(
            id=version.id, version=version.version, fetched_at=version.fetched_at, content_changed=version.content_changed
        )

    return VersionChangesOut(
        base=ref(base),
        target=ref(target),
        summary=ChangeSummaryOut(**diff.summary()),
        changes=[
            SpecChangeOut(
                kind=c.kind,
                severity=c.severity,
                method=c.method,
                path=c.path,
                scope=c.scope,
                status=c.status,
                media_type=c.media_type,
                location=c.location,
                detail=c.detail,
            )
            for c in diff.changes
        ],
        truncated=diff.truncated,
    )
