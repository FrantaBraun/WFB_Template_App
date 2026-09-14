# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the Collection/CollectionDocument models' own defaults and
constraints, independent of a collections API router (not built in this
slice - see CLAUDE.md's Phase 5 plan)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.api_document import ApiDocument
from app.models.collection import Collection, CollectionDocument
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


async def _make_document(db_session, team: Team, creator: User, **overrides) -> ApiDocument:
    fields = dict(team_id=team.id, title="Some API", created_by_user_id=creator.id)
    fields.update(overrides)
    document = ApiDocument(**fields)
    db_session.add(document)
    await db_session.flush()
    return document


async def _make_collection(db_session, team: Team, creator: User, **overrides) -> Collection:
    fields = dict(team_id=team.id, name="Some Collection", created_by_user_id=creator.id)
    fields.update(overrides)
    collection = Collection(**fields)
    db_session.add(collection)
    await db_session.flush()
    return collection


async def test_collection_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)

    collection = await _make_collection(db_session, team, creator)

    assert collection.id is not None
    assert collection.is_public is False
    assert collection.created_at is not None
    assert collection.updated_at is not None


async def test_collection_document_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection = await _make_collection(db_session, team, creator)
    doc = await _make_document(db_session, team, creator)

    link = CollectionDocument(
        collection_id=collection.id, documentation_id=doc.id, added_by_user_id=creator.id
    )
    db_session.add(link)
    await db_session.flush()

    assert link.id is not None
    assert link.created_at is not None


async def test_collection_document_pair_must_be_unique(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection = await _make_collection(db_session, team, creator)
    doc = await _make_document(db_session, team, creator)
    db_session.add(
        CollectionDocument(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    await db_session.flush()

    db_session.add(
        CollectionDocument(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_collection_document_same_document_in_two_collections_does_not_raise(db_session):
    """The unique constraint is on the (collection_id, documentation_id)
    pair, not on documentation_id alone - a document belonging to several
    collections is the normal case."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection_a = await _make_collection(db_session, team, creator, name="Collection A")
    collection_b = await _make_collection(db_session, team, creator, name="Collection B")
    doc = await _make_document(db_session, team, creator)

    db_session.add(
        CollectionDocument(collection_id=collection_a.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    db_session.add(
        CollectionDocument(collection_id=collection_b.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    await db_session.flush()  # must not raise
