# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.services.notifications import notify_new_version
from app.services.openapi_spec import ParsedSpec, SpecValidationError, fetch_spec_from_url, parse_spec
from app.services.spec_diff import diff_specs
from app.services.spec_storage import read_spec_file, save_spec_file

logger = logging.getLogger(__name__)


async def get_current_version(db: AsyncSession, documentation_id: uuid.UUID) -> ApiDocumentVersion | None:
    """The row with archived_at IS NULL for one document, if any - the
    partial unique index on ApiDocumentVersion (app/models/api_document.py)
    guarantees at most one. Shared by process_new_spec below and by
    app/api/api_docs/router.py, which renders this same row as the detail
    response's current_version field."""
    result = await db.execute(
        select(ApiDocumentVersion).where(
            ApiDocumentVersion.documentation_id == documentation_id,
            ApiDocumentVersion.archived_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def _content_differs(current: ApiDocumentVersion, raw: bytes, parsed: ParsedSpec, uploads_dir: str) -> bool:
    """Whether raw says something different from the stored current version,
    both having the same info.version. Identical bytes are the cheap answer
    (the usual case, no parsing); otherwise the stored file is parsed again
    and the two content hashes compared (ParsedSpec.content_hash), so a spec
    that was merely reformatted, reordered or served as YAML instead of JSON
    is not a change. Computed from the stored file rather than kept in a
    column so versions archived before this check existed compare the same
    way. A stored file that cannot be read or parsed (gone from disk) means
    there is nothing to compare with: logged, and not a change."""
    if hashlib.sha256(raw).hexdigest() == current.checksum:
        return False
    try:
        stored = parse_spec(read_spec_file(uploads_dir, current.storage_path))
    except (OSError, SpecValidationError):
        logger.warning(
            "Cannot compare the content of version %s (document %s) with the stored file %s",
            current.id,
            current.documentation_id,
            current.storage_path,
        )
        return False
    return stored.content_hash != parsed.content_hash


def _summarise_changes(current: ApiDocumentVersion, parsed: ParsedSpec, uploads_dir: str) -> dict[str, int] | None:
    """The structural changes from the version being replaced to the new
    spec, counted by severity (app/services/spec_diff.py), or None when they
    cannot be worked out. Never raises: a spec the diff cannot make sense of,
    or a stored file that is gone, must not turn a successful check into a
    failed one - the version is recorded without a summary and the changes
    page says it cannot compare."""
    try:
        previous = parse_spec(read_spec_file(uploads_dir, current.storage_path))
        return diff_specs(previous.document, parsed.document).summary()
    except Exception:
        logger.exception("Cannot compare version %s (document %s) with the new spec", current.id, current.documentation_id)
        return None


async def process_new_spec(
    doc: ApiDocument,
    raw: bytes,
    source: str,
    db: AsyncSession,
    uploads_dir: str,
    max_size_bytes: int,
) -> ApiDocumentVersion | None:
    """Turn newly-fetched-or-uploaded spec bytes into the document's version
    history: parse raw, compare info.version against the current row (if
    any). Same version and the same content -> no-op (only last_checked_at
    moves), returns None. Different version (or no current row yet) ->
    archive the old current row, persist the file, insert the new current
    row, returns it.

    Same version but different content (the vendor changed the spec without
    bumping info.version) is treated like a new version when
    doc.detect_content_changes is on: the old row is archived, the new one
    inserted with content_changed=True, so what the spec said before is not
    lost. "Different" means the parsed content, not the bytes - see
    _content_differs.

    Reused unchanged by create-by-URL/-upload, manual recheck, manual
    re-upload and (a later phase's) scheduled recheck - source is the only
    thing that varies between callers.

    On an actual new/changed version, notify_new_version
    (app/services/notifications.py) is called before returning - never on
    the no-op path above, and never on a failure path below, since those
    don't reach this point. notify_new_version never raises, so it can't
    turn this call's own success into a failure.

    On any failure (oversized content, parse_spec, or save_spec_file once a
    new version is actually needed) doc.last_check_error is set to a short
    description and committed before re-raising, so a failed check is still
    visible on the document even though the caller (a router) decides the
    HTTP status.
    """
    try:
        if len(raw) > max_size_bytes:
            raise SpecValidationError(
                f"Spec content is {len(raw)} bytes, which exceeds the {max_size_bytes} byte limit."
            )
        parsed = parse_spec(raw)

        current = await get_current_version(db, doc.id)
        now = datetime.now(timezone.utc)

        content_changed = False
        if current is not None and current.version == parsed.version:
            content_changed = doc.detect_content_changes and _content_differs(
                current, raw, parsed, uploads_dir
            )
            if not content_changed:
                doc.last_checked_at = now
                doc.last_check_error = None
                await db.commit()
                return None

        checksum = hashlib.sha256(raw).hexdigest()
        version_id = uuid.uuid4()
        # save_spec_file before touching any row, so a failure here (e.g. a
        # disk error) never leaves a committed partial state - the old
        # current row archived with no new one to replace it.
        storage_path = save_spec_file(uploads_dir, doc.id, version_id, parsed.format, raw)

        # Before the old row is archived: it is still the file being replaced.
        change_summary = _summarise_changes(current, parsed, uploads_dir) if current is not None else None

        if current is not None:
            current.archived_at = now

        new_version = ApiDocumentVersion(
            id=version_id,
            documentation_id=doc.id,
            version=parsed.version,
            spec_title=parsed.title,
            format=parsed.format,
            storage_path=storage_path,
            checksum=checksum,
            source=source,
            content_changed=content_changed,
            change_summary=change_summary,
            archived_at=None,
        )
        db.add(new_version)
        doc.last_checked_at = now
        doc.last_check_error = None
        await db.commit()
        await db.refresh(new_version)
        await notify_new_version(doc, new_version, db)
        return new_version
    except Exception as exc:
        doc.last_check_error = str(exc) or type(exc).__name__
        await db.commit()
        raise


async def fetch_and_process(
    doc: ApiDocument, source: str, db: AsyncSession, settings: Settings
) -> ApiDocumentVersion | None:
    """Fetch doc.source_url and hand the bytes to process_new_spec - the
    other half of what a URL-based check needs beyond process_new_spec
    itself, which only ever sees already-fetched bytes (raw: bytes, not a
    URL) so a fetch failure can't reach that function's own error handling.
    Recorded here the same way instead: set last_check_error, commit, then
    re-raise httpx.HTTPError as-is.

    No FastAPI dependency in this module, so httpx.HTTPError and
    SpecValidationError (raised by process_new_spec itself) both propagate
    as plain exceptions rather than HTTPException - callers decide how to
    react. Reused unchanged by app/api/api_docs/router.py's create-by-URL and
    manual recheck endpoints (which convert either exception to
    HTTPException(422, ...)) and by app/services/scheduler.py's scheduled
    recheck (which logs the failure and moves on to the next document
    instead).
    """
    try:
        raw = await fetch_spec_from_url(
            doc.source_url,
            settings.spec_fetch_timeout_seconds,
            max_bytes=settings.max_spec_file_size_bytes,
            allow_private=settings.outbound_allow_private_addresses,
        )
    except (httpx.HTTPError, SpecValidationError) as exc:
        # httpx timeouts stringify to "" - the type name is better than nothing.
        # A SpecValidationError here is the fetch refusing (an address that may
        # not be called, a body over the limit) - recorded like any failed check.
        doc.last_check_error = str(exc) or type(exc).__name__
        await db.commit()
        raise

    return await process_new_spec(
        doc,
        raw,
        source=source,
        db=db,
        uploads_dir=settings.uploads_dir,
        max_size_bytes=settings.max_spec_file_size_bytes,
    )


_RECHECK_INTERVALS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


async def find_docs_due_for_recheck(db: AsyncSession, now: datetime) -> list[ApiDocument]:
    """Documents whose recheck_period is due as of `now`, for
    app/services/scheduler.py's periodic scan. A cheap, selective SQL filter
    narrows the candidate set to documents that could ever be due (a
    source_url to check, recheck_period not 'manual'); the period-dependent
    comparison - never checked, or checked long enough ago for that
    document's own recheck_period - is then finished in plain Python rather
    than a SQL CASE expression. Simpler to read and test correctly, and cheap
    enough: this runs on a coarse interval
    (settings.recheck_scan_interval_minutes, default hourly) over what's
    expected to be a modest number of documents for this kind of internal
    tool.
    """
    candidates = (
        await db.execute(
            select(ApiDocument).where(
                ApiDocument.source_url.isnot(None), ApiDocument.recheck_period != "manual"
            )
        )
    ).scalars().all()
    return [
        doc
        for doc in candidates
        if doc.last_checked_at is None
        or doc.last_checked_at <= now - _RECHECK_INTERVALS[doc.recheck_period]
    ]
