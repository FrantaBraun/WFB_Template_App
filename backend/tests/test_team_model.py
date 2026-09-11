# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the Team/TeamMembership/TeamInvitation models' own defaults and
constraints, independent of the teams API router (not built yet - see
CLAUDE.md's Phase 1 plan)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.team import Team, TeamInvitation, TeamMembership
from app.models.user import User


def _expires_in_7_days() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=7)


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


async def test_team_create_sets_defaults(db_session):
    team = await _make_team(db_session)

    assert team.id is not None
    assert team.created_at is not None
    assert team.updated_at is not None


async def test_membership_role_defaults_to_member(db_session):
    team = await _make_team(db_session)
    user = await _make_user(db_session)

    membership = TeamMembership(team_id=team.id, user_id=user.id)
    db_session.add(membership)
    await db_session.flush()

    assert membership.id is not None
    assert membership.role == "member"
    assert membership.created_at is not None


async def test_membership_team_user_pair_must_be_unique(db_session):
    team = await _make_team(db_session)
    user = await _make_user(db_session)
    db_session.add(TeamMembership(team_id=team.id, user_id=user.id))
    await db_session.flush()

    db_session.add(TeamMembership(team_id=team.id, user_id=user.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_membership_same_user_can_join_different_teams(db_session):
    """The unique constraint is on the (team_id, user_id) pair, not on
    user_id alone - a user belonging to several teams is the normal case."""
    team_a = await _make_team(db_session, "Team A")
    team_b = await _make_team(db_session, "Team B")
    user = await _make_user(db_session)

    db_session.add(TeamMembership(team_id=team_a.id, user_id=user.id))
    db_session.add(TeamMembership(team_id=team_b.id, user_id=user.id))
    await db_session.flush()  # must not raise


async def test_invitation_defaults_status_pending_and_generates_token(db_session):
    team = await _make_team(db_session)
    inviter = await _make_user(db_session)

    invitation = TeamInvitation(
        team_id=team.id,
        email="invitee@example.com",
        invited_by_user_id=inviter.id,
        expires_at=_expires_in_7_days(),
    )
    db_session.add(invitation)
    await db_session.flush()

    assert invitation.id is not None
    assert invitation.status == "pending"
    assert invitation.token
    assert len(invitation.token) > 20
    assert invitation.accepted_at is None
    assert invitation.accepted_by_user_id is None


async def test_invitation_generates_distinct_tokens(db_session):
    team = await _make_team(db_session)
    inviter = await _make_user(db_session)

    first = TeamInvitation(
        team_id=team.id,
        email="a@example.com",
        invited_by_user_id=inviter.id,
        expires_at=_expires_in_7_days(),
    )
    second = TeamInvitation(
        team_id=team.id,
        email="b@example.com",
        invited_by_user_id=inviter.id,
        expires_at=_expires_in_7_days(),
    )
    db_session.add_all([first, second])
    await db_session.flush()

    assert first.token != second.token


async def test_invitation_token_must_be_unique(db_session):
    team = await _make_team(db_session)
    inviter = await _make_user(db_session)
    shared_token = "shared-token-value"

    db_session.add(
        TeamInvitation(
            team_id=team.id,
            email="a@example.com",
            invited_by_user_id=inviter.id,
            expires_at=_expires_in_7_days(),
            token=shared_token,
        )
    )
    await db_session.flush()

    db_session.add(
        TeamInvitation(
            team_id=team.id,
            email="b@example.com",
            invited_by_user_id=inviter.id,
            expires_at=_expires_in_7_days(),
            token=shared_token,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
