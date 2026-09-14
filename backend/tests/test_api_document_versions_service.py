# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.api_document_versions.process_new_spec: first
version creation, the same-version no-op path, archive-on-change for a
different version, and the parse-failure error-handling contract
(last_check_error set, no version row created, exception re-raised)."""

import json
import uuid

import httpx
import pytest
import respx
from sqlalchemy import select

from app.config import Settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.team import Team
from app.models.user import User
from app.services.api_document_versions import fetch_and_process, process_new_spec
from app.services.openapi_spec import SpecValidationError
from app.services.spec_storage import read_spec_file


def _spec_bytes(version: str, title: str = "Example API") -> bytes:
    return json.dumps({"openapi": "3.0.0", "info": {"title": title, "version": version}}).encode()


async def _make_document(db_session, **overrides) -> ApiDocument:
    team = Team(name="Test Team")
    db_session.add(team)
    await db_session.flush()
    user = User(auth_sub=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    fields = dict(team_id=team.id, title="Some API", created_by_user_id=user.id)
    fields.update(overrides)
    document = ApiDocument(**fields)
    db_session.add(document)
    await db_session.flush()
    return document


async def _current_version_row(db_session, documentation_id) -> ApiDocumentVersion | None:
    result = await db_session.execute(
        select(ApiDocumentVersion).where(
            ApiDocumentVersion.documentation_id == documentation_id,
            ApiDocumentVersion.archived_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def test_first_version_creates_current_row(db_session, tmp_path):
    doc = await _make_document(db_session)

    result = await process_new_spec(
        doc, _spec_bytes("1.0.0"), source="initial", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )

    assert result is not None
    assert result.version == "1.0.0"
    assert result.spec_title == "Example API"
    assert result.format == "json"
    assert result.source == "initial"
    assert result.archived_at is None
    assert result.checksum

    await db_session.refresh(doc)
    assert doc.last_checked_at is not None
    assert doc.last_check_error is None
    assert read_spec_file(str(tmp_path), result.storage_path) == _spec_bytes("1.0.0")


async def test_same_version_is_a_noop(db_session, tmp_path):
    doc = await _make_document(db_session)
    first = await process_new_spec(
        doc, _spec_bytes("1.0.0"), source="initial", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )
    first_checked_at = doc.last_checked_at

    result = await process_new_spec(
        doc, _spec_bytes("1.0.0"), source="manual_recheck", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )

    assert result is None
    await db_session.refresh(doc)
    assert doc.last_checked_at is not None
    assert doc.last_checked_at >= first_checked_at
    assert doc.last_check_error is None

    current = await _current_version_row(db_session, doc.id)
    assert current is not None
    assert current.id == first.id  # still the same row - nothing archived, nothing inserted

    all_versions = (
        await db_session.execute(
            select(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id == doc.id)
        )
    ).scalars().all()
    assert len(all_versions) == 1


async def test_different_version_archives_old_and_creates_new(db_session, tmp_path):
    doc = await _make_document(db_session)
    first = await process_new_spec(
        doc, _spec_bytes("1.0.0"), source="initial", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )

    second = await process_new_spec(
        doc, _spec_bytes("2.0.0"), source="manual_recheck", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )

    assert second is not None
    assert second.version == "2.0.0"
    assert second.source == "manual_recheck"
    assert second.archived_at is None

    await db_session.refresh(first)
    assert first.archived_at is not None
    assert first.version == "1.0.0"  # untouched otherwise

    current = await _current_version_row(db_session, doc.id)
    assert current is not None
    assert current.id == second.id

    all_versions = (
        await db_session.execute(
            select(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id == doc.id)
        )
    ).scalars().all()
    assert len(all_versions) == 2


async def test_parse_failure_sets_last_check_error_and_raises_without_creating_version(db_session, tmp_path):
    doc = await _make_document(db_session)

    with pytest.raises(SpecValidationError):
        await process_new_spec(
            doc, b"\xff\xff\xff\xff", source="initial", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
        )

    await db_session.refresh(doc)
    assert doc.last_check_error is not None
    assert doc.last_checked_at is None

    current = await _current_version_row(db_session, doc.id)
    assert current is None
    all_versions = (
        await db_session.execute(
            select(ApiDocumentVersion).where(ApiDocumentVersion.documentation_id == doc.id)
        )
    ).scalars().all()
    assert len(all_versions) == 0


async def test_oversized_spec_is_rejected_without_creating_a_version(db_session, tmp_path):
    doc = await _make_document(db_session)

    with pytest.raises(SpecValidationError):
        await process_new_spec(
            doc,
            _spec_bytes("1.0.0"),
            source="initial",
            db=db_session,
            uploads_dir=str(tmp_path),
            max_size_bytes=5,
        )

    await db_session.refresh(doc)
    assert doc.last_check_error is not None
    assert await _current_version_row(db_session, doc.id) is None


async def test_parse_failure_after_existing_version_does_not_archive_it(db_session, tmp_path):
    """A failed recheck must never disturb the existing current version -
    only a *successful* parse of a genuinely different version may archive
    it (see test_different_version_archives_old_and_creates_new)."""
    doc = await _make_document(db_session)
    first = await process_new_spec(
        doc, _spec_bytes("1.0.0"), source="initial", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
    )

    with pytest.raises(SpecValidationError):
        await process_new_spec(
            doc, b"\xff\xff\xff\xff", source="manual_recheck", db=db_session, uploads_dir=str(tmp_path), max_size_bytes=10_000_000
        )

    await db_session.refresh(doc)
    assert doc.last_check_error is not None

    await db_session.refresh(first)
    assert first.archived_at is None

    current = await _current_version_row(db_session, doc.id)
    assert current is not None
    assert current.id == first.id


# --- fetch_and_process (fetch + process_new_spec, no FastAPI dependency) ------------


@respx.mock
async def test_fetch_and_process_success_returns_new_version(db_session, tmp_path):
    doc = await _make_document(db_session, source_url="https://example.com/openapi.json")
    respx.get("https://example.com/openapi.json").mock(
        return_value=httpx.Response(200, content=_spec_bytes("1.0.0"))
    )
    settings = Settings(uploads_dir=str(tmp_path))

    result = await fetch_and_process(doc, source="auto_recheck", db=db_session, settings=settings)

    assert result is not None
    assert result.version == "1.0.0"
    assert result.source == "auto_recheck"


@respx.mock
async def test_fetch_and_process_propagates_http_error_not_http_exception(db_session, tmp_path):
    """fetch_and_process has no FastAPI dependency (app.services.* never
    imports fastapi) - a fetch failure must propagate as httpx's own
    exception, not HTTPException. Converting it to HTTPException(422) is
    app/api/api_docs/router.py's job, one layer up; app/services/scheduler.py
    reuses this same function and reacts to the plain exception directly."""
    doc = await _make_document(db_session, source_url="https://example.com/openapi.json")
    respx.get("https://example.com/openapi.json").mock(return_value=httpx.Response(500))
    settings = Settings(uploads_dir=str(tmp_path))

    with pytest.raises(httpx.HTTPError):
        await fetch_and_process(doc, source="auto_recheck", db=db_session, settings=settings)

    await db_session.refresh(doc)
    assert doc.last_check_error is not None


@respx.mock
async def test_fetch_and_process_propagates_spec_validation_error_not_http_exception(db_session, tmp_path):
    doc = await _make_document(db_session, source_url="https://example.com/openapi.json")
    respx.get("https://example.com/openapi.json").mock(
        return_value=httpx.Response(200, content=b"\xff\xff\xff\xff")
    )
    settings = Settings(uploads_dir=str(tmp_path))

    with pytest.raises(SpecValidationError):
        await fetch_and_process(doc, source="auto_recheck", db=db_session, settings=settings)

    await db_session.refresh(doc)
    assert doc.last_check_error is not None
