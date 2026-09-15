# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the KnowledgeBasePage model's own defaults and constraints,
independent of any collections/integrations KB API endpoints (not built in
this slice - see CLAUDE.md's Phase 7 plan)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.collection import Collection
from app.models.integration import Integration
from app.models.knowledge_base import KnowledgeBasePage
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


async def _make_collection(db_session, team: Team, creator: User, **overrides) -> Collection:
    fields = dict(team_id=team.id, name="Some Collection", created_by_user_id=creator.id)
    fields.update(overrides)
    collection = Collection(**fields)
    db_session.add(collection)
    await db_session.flush()
    return collection


async def _make_integration(db_session, team: Team, creator: User, **overrides) -> Integration:
    fields = dict(team_id=team.id, name="Some Integration", created_by_user_id=creator.id)
    fields.update(overrides)
    integration = Integration(**fields)
    db_session.add(integration)
    await db_session.flush()
    return integration


async def test_collection_page_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection = await _make_collection(db_session, team, creator)

    page = KnowledgeBasePage(collection_id=collection.id, title="Getting started", created_by_user_id=creator.id)
    db_session.add(page)
    await db_session.flush()

    assert page.id is not None
    assert page.title == "Getting started"
    assert page.content == ""
    assert page.position == 0
    assert page.integration_id is None
    assert page.created_at is not None
    assert page.updated_at is not None


async def test_integration_page_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)

    page = KnowledgeBasePage(integration_id=integration.id, title="Overview", created_by_user_id=creator.id)
    db_session.add(page)
    await db_session.flush()

    assert page.id is not None
    assert page.content == ""
    assert page.position == 0
    assert page.collection_id is None


async def test_check_constraint_rejects_both_owners_set(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection = await _make_collection(db_session, team, creator)
    integration = await _make_integration(db_session, team, creator)

    db_session.add(
        KnowledgeBasePage(
            collection_id=collection.id,
            integration_id=integration.id,
            title="Both owners",
            created_by_user_id=creator.id,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_check_constraint_rejects_neither_owner_set(db_session):
    creator = await _make_user(db_session)

    db_session.add(KnowledgeBasePage(title="No owner", created_by_user_id=creator.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_collection_and_integration_owned_pages_persist_independently(db_session):
    """A collection-owned page and an integration-owned page coexist fine -
    the CheckConstraint only rejects a single row claiming both/neither
    owner, it says nothing about pages under different owners existing at
    the same time."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection = await _make_collection(db_session, team, creator)
    integration = await _make_integration(db_session, team, creator)

    db_session.add(
        KnowledgeBasePage(collection_id=collection.id, title="Collection page", created_by_user_id=creator.id)
    )
    db_session.add(
        KnowledgeBasePage(integration_id=integration.id, title="Integration page", created_by_user_id=creator.id)
    )
    await db_session.flush()  # must not raise


async def test_multiple_collection_pages_with_duplicate_and_gapped_positions_allowed(db_session):
    """No uniqueness constraint on position - duplicates and gaps are both
    fine, it's a plain manual-ordering hint only."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    collection = await _make_collection(db_session, team, creator)

    db_session.add(
        KnowledgeBasePage(
            collection_id=collection.id, title="First", position=0, created_by_user_id=creator.id
        )
    )
    db_session.add(
        KnowledgeBasePage(
            collection_id=collection.id, title="Also zero", position=0, created_by_user_id=creator.id
        )
    )
    db_session.add(
        KnowledgeBasePage(
            collection_id=collection.id, title="Skips ahead", position=10, created_by_user_id=creator.id
        )
    )
    await db_session.flush()  # must not raise


async def test_multiple_integration_pages_with_duplicate_and_gapped_positions_allowed(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)

    db_session.add(
        KnowledgeBasePage(
            integration_id=integration.id, title="First", position=0, created_by_user_id=creator.id
        )
    )
    db_session.add(
        KnowledgeBasePage(
            integration_id=integration.id, title="Also zero", position=0, created_by_user_id=creator.id
        )
    )
    db_session.add(
        KnowledgeBasePage(
            integration_id=integration.id, title="Skips ahead", position=10, created_by_user_id=creator.id
        )
    )
    await db_session.flush()  # must not raise
