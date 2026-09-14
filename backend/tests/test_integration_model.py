# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the Integration/IntegrationCollection/IntegrationDocument
models' own defaults and constraints, independent of an integrations API
router (not built in this slice - see CLAUDE.md's Phase 6 plan)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.api_document import ApiDocument
from app.models.collection import Collection, CollectionDocument
from app.models.integration import Integration, IntegrationCollection, IntegrationDocument
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


async def _make_integration(db_session, team: Team, creator: User, **overrides) -> Integration:
    fields = dict(team_id=team.id, name="Some Integration", created_by_user_id=creator.id)
    fields.update(overrides)
    integration = Integration(**fields)
    db_session.add(integration)
    await db_session.flush()
    return integration


async def test_integration_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)

    integration = await _make_integration(db_session, team, creator)

    assert integration.id is not None
    assert integration.name == "Some Integration"
    assert integration.created_at is not None
    assert integration.updated_at is not None


async def test_integration_has_no_is_public_column():
    """Deliberate, per the plan's locked-in assumption: unlike ApiDocument
    and Collection, Integration is always team-gated - never public, never
    subscribable. Constructing one without is_public must work (it would
    raise TypeError if the column were required), and the attribute must
    genuinely not exist on the model at all, not just default to a falsy
    value."""
    integration = Integration(
        team_id=uuid.uuid4(), name="No Public Flag", created_by_user_id=uuid.uuid4()
    )
    assert hasattr(integration, "is_public") is False
    assert "is_public" not in Integration.__table__.columns


async def test_integration_collection_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)
    collection = await _make_collection(db_session, team, creator)

    link = IntegrationCollection(
        integration_id=integration.id, collection_id=collection.id, added_by_user_id=creator.id
    )
    db_session.add(link)
    await db_session.flush()

    assert link.id is not None
    assert link.created_at is not None


async def test_integration_collection_pair_must_be_unique(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)
    collection = await _make_collection(db_session, team, creator)
    db_session.add(
        IntegrationCollection(
            integration_id=integration.id, collection_id=collection.id, added_by_user_id=creator.id
        )
    )
    await db_session.flush()

    db_session.add(
        IntegrationCollection(
            integration_id=integration.id, collection_id=collection.id, added_by_user_id=creator.id
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_integration_collection_same_collection_in_two_integrations_does_not_raise(db_session):
    """The unique constraint is on the (integration_id, collection_id) pair,
    not on collection_id alone - a collection belonging to several
    integrations is the normal case."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration_a = await _make_integration(db_session, team, creator, name="Integration A")
    integration_b = await _make_integration(db_session, team, creator, name="Integration B")
    collection = await _make_collection(db_session, team, creator)

    db_session.add(
        IntegrationCollection(
            integration_id=integration_a.id, collection_id=collection.id, added_by_user_id=creator.id
        )
    )
    db_session.add(
        IntegrationCollection(
            integration_id=integration_b.id, collection_id=collection.id, added_by_user_id=creator.id
        )
    )
    await db_session.flush()  # must not raise


async def test_integration_document_create_sets_defaults(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)
    doc = await _make_document(db_session, team, creator)

    link = IntegrationDocument(
        integration_id=integration.id, documentation_id=doc.id, added_by_user_id=creator.id
    )
    db_session.add(link)
    await db_session.flush()

    assert link.id is not None
    assert link.created_at is not None


async def test_integration_document_pair_must_be_unique(db_session):
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)
    doc = await _make_document(db_session, team, creator)
    db_session.add(
        IntegrationDocument(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    await db_session.flush()

    db_session.add(
        IntegrationDocument(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_integration_document_same_document_in_two_integrations_does_not_raise(db_session):
    """The unique constraint is on the (integration_id, documentation_id)
    pair, not on documentation_id alone - a document being a direct member
    of several integrations is the normal case."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration_a = await _make_integration(db_session, team, creator, name="Integration A")
    integration_b = await _make_integration(db_session, team, creator, name="Integration B")
    doc = await _make_document(db_session, team, creator)

    db_session.add(
        IntegrationDocument(integration_id=integration_a.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    db_session.add(
        IntegrationDocument(integration_id=integration_b.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    await db_session.flush()  # must not raise


async def test_document_can_be_both_direct_and_collection_member_of_same_integration(db_session):
    """A document reachable through a member Collection (via
    CollectionDocument) may also be a direct IntegrationDocument member of
    that same Integration - nothing at the schema level prevents this
    overlap. This is model/DB-level plumbing only; de-duplicating the two in
    a merged documents list is the integrations router's job (a later
    phase), not enforced here."""
    team = await _make_team(db_session)
    creator = await _make_user(db_session)
    integration = await _make_integration(db_session, team, creator)
    collection = await _make_collection(db_session, team, creator)
    doc = await _make_document(db_session, team, creator)

    db_session.add(
        IntegrationCollection(
            integration_id=integration.id, collection_id=collection.id, added_by_user_id=creator.id
        )
    )
    db_session.add(
        CollectionDocument(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    db_session.add(
        IntegrationDocument(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=creator.id)
    )
    await db_session.flush()  # must not raise - overlap is representable
