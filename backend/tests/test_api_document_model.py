# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the ApiDocument/ApiDocumentVersion models' own defaults and
constraints, independent of any API router (not built yet - see CLAUDE.md's
Phase 2 plan). The main thing under test is the partial unique index on
ApiDocumentVersion (at most one archived_at IS NULL row per
documentation_id) - autogenerate reliability for exactly this kind of
Postgres partial index was called out as worth double-checking."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.team import Team
from app.models.user import User


async def _make_user(db_session) -> User:
    user = User(auth_sub=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team(db_session, name: str = "Test Team") -> Team:
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    return team


async def _make_document(
    db_session,
    *,
    team: Team | None = None,
    user: User | None = None,
    title: str = "Some API",
    **overrides,
) -> ApiDocument:
    team = team or await _make_team(db_session)
    user = user or await _make_user(db_session)
    document = ApiDocument(
        team_id=team.id, title=title, created_by_user_id=user.id, **overrides
    )
    db_session.add(document)
    await db_session.flush()
    return document


def _make_version(
    document: ApiDocument,
    *,
    version: str = "1.0.0",
    format: str = "json",
    storage_path: str = "api_docs/doc/version.json",
    checksum: str = "0" * 64,
    source: str = "initial",
    archived_at: datetime | None = None,
) -> ApiDocumentVersion:
    return ApiDocumentVersion(
        documentation_id=document.id,
        version=version,
        format=format,
        storage_path=storage_path,
        checksum=checksum,
        source=source,
        archived_at=archived_at,
    )


async def test_document_create_sets_defaults(db_session):
    document = await _make_document(db_session)

    assert document.id is not None
    assert document.recheck_period == "manual"
    assert document.is_public is False
    assert document.source_url is None
    assert document.notes is None
    assert document.last_checked_at is None
    assert document.last_check_error is None
    assert document.created_at is not None
    assert document.updated_at is not None


async def test_version_defaults_to_current_and_sets_fetched_at(db_session):
    document = await _make_document(db_session)

    version = ApiDocumentVersion(
        documentation_id=document.id,
        version="1.0.0",
        format="json",
        storage_path="api_docs/doc/version.json",
        checksum="0" * 64,
        source="initial",
    )
    db_session.add(version)
    await db_session.flush()

    assert version.id is not None
    assert version.archived_at is None
    assert version.fetched_at is not None
    assert version.created_at is not None


async def test_two_archived_versions_for_same_document_coexist(db_session):
    document = await _make_document(db_session)
    now = datetime.now(timezone.utc)

    db_session.add(_make_version(document, version="1.0.0", archived_at=now))
    db_session.add(_make_version(document, version="2.0.0", archived_at=now))
    await db_session.flush()  # must not raise


async def test_two_current_versions_for_same_document_violates_constraint(db_session):
    document = await _make_document(db_session)

    db_session.add(_make_version(document, version="1.0.0", archived_at=None))
    await db_session.flush()

    db_session.add(_make_version(document, version="2.0.0", archived_at=None))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_current_version_for_two_different_documents_is_fine(db_session):
    team = await _make_team(db_session)
    user = await _make_user(db_session)
    document_a = await _make_document(db_session, team=team, user=user, title="Doc A")
    document_b = await _make_document(db_session, team=team, user=user, title="Doc B")

    db_session.add(_make_version(document_a, archived_at=None))
    db_session.add(_make_version(document_b, archived_at=None))
    await db_session.flush()  # must not raise
