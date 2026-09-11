# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for /api/teams/*: team CRUD, membership removal guards (last-owner,
last-member, only-owner-removes-owner), and the full email-invitation
lifecycle (create/list/revoke/accept incl. expired/revoked/mismatched-email).

Uses the same ASGITransport + dependency_overrides[get_db] + db_session +
make_access_token() pattern as test_auth_router.py/test_account_router.py -
every route here needs both a real verified JWT and the DB in the same
request, which the sync `client`/TestClient fixture can't do (see CLAUDE.md).
Team/membership/invitation setup is done via direct model inserts (mirrors
test_team_model.py), then the endpoint under test is driven over HTTP."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi_mail import FastMail
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import app.security.jwt as jwt_module
from app.config import get_settings
from app.models.team import Team, TeamInvitation, TeamMembership
from app.models.user import User
from app.services.email import _connection_config


@pytest.fixture(autouse=True)
def _signed_in(rsa_keypair, monkeypatch):
    """Every route in this file requires a verified JWT - seed the cached
    public key once per test instead of repeating this in every test."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)


async def _request(db_session, method: str, path: str, *, token: str | None = None, settings=None, **kwargs):
    from app.database import get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    if settings is not None:
        fastapi_app.dependency_overrides[get_settings] = lambda: settings
    headers = kwargs.pop("headers", {}) or {}
    if token is not None:
        headers = {**headers, "Authorization": f"Bearer {token}"}
    try:
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, **kwargs)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        if settings is not None:
            fastapi_app.dependency_overrides.pop(get_settings, None)


def _email_body(message) -> str:
    return message.get_payload()[0].get_payload(decode=True).decode()


async def _make_user(db_session, email: str | None = "user@example.com") -> User:
    user = User(auth_sub=uuid.uuid4(), email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team_with_owner(db_session, owner: User, name: str = "Test Team") -> Team:
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    db_session.add(TeamMembership(team_id=team.id, user_id=owner.id, role="owner"))
    await db_session.flush()
    return team


async def _add_member(db_session, team: Team, user: User, role: str = "member") -> TeamMembership:
    membership = TeamMembership(team_id=team.id, user_id=user.id, role=role)
    db_session.add(membership)
    await db_session.flush()
    return membership


async def _make_invitation(db_session, team: Team, inviter: User, email: str, **overrides) -> TeamInvitation:
    fields = dict(
        team_id=team.id,
        email=email,
        invited_by_user_id=inviter.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    fields.update(overrides)
    invitation = TeamInvitation(**fields)
    db_session.add(invitation)
    await db_session.flush()
    return invitation


# --- create / list / get / patch -------------------------------------------------


async def test_create_team_creates_owner_membership(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()), email="owner@example.com")

    resp = await _request(db_session, "POST", "/api/teams", token=token, json={"name": "Acme"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Acme"
    assert body["role"] == "owner"
    assert body["member_count"] == 1
    assert "id" in body and "created_at" in body

    result = await db_session.execute(
        select(TeamMembership).where(TeamMembership.team_id == uuid.UUID(body["id"]))
    )
    memberships = result.scalars().all()
    assert len(memberships) == 1
    assert memberships[0].role == "owner"


def test_create_team_requires_bearer(client):
    resp = client.post("/api/teams", json={"name": "Acme"})
    assert resp.status_code in (401, 403)


async def test_list_teams_returns_only_callers_teams(db_session, make_access_token):
    owner_a = await _make_user(db_session, email="a@example.com")
    owner_b = await _make_user(db_session, email="b@example.com")
    team_a = await _make_team_with_owner(db_session, owner_a, name="Team A")
    await _make_team_with_owner(db_session, owner_b, name="Team B")
    token_a = make_access_token(sub=str(owner_a.auth_sub), email="a@example.com")

    resp = await _request(db_session, "GET", "/api/teams", token=token_a)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == str(team_a.id)
    assert body[0]["role"] == "owner"
    assert body[0]["member_count"] == 1


async def test_get_team_returns_members(db_session, make_access_token):
    owner = await _make_user(db_session, email="owner@example.com")
    member = await _make_user(db_session, email="member@example.com")
    team = await _make_team_with_owner(db_session, owner, name="Team A")
    await _add_member(db_session, team, member, role="member")
    token = make_access_token(sub=str(owner.auth_sub), email="owner@example.com")

    resp = await _request(db_session, "GET", f"/api/teams/{team.id}", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(team.id)
    assert body["name"] == "Team A"
    assert len(body["members"]) == 2
    roles_by_user = {m["user_id"]: m["role"] for m in body["members"]}
    assert roles_by_user[str(owner.id)] == "owner"
    assert roles_by_user[str(member.id)] == "member"
    assert {m["email"] for m in body["members"]} == {"owner@example.com", "member@example.com"}


async def test_get_team_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "GET", f"/api/teams/{team.id}", token=outsider_token)

    assert resp.status_code == 404


async def test_patch_team_renames(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "PATCH", f"/api/teams/{team.id}", token=token, json={"name": "Renamed"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["role"] == "owner"

    await db_session.refresh(team)
    assert team.name == "Renamed"


async def test_patch_team_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "PATCH", f"/api/teams/{team.id}", token=outsider_token, json={"name": "Hack"})

    assert resp.status_code == 404


# --- member removal ---------------------------------------------------------------


async def test_remove_member_self_leave_allowed(db_session, make_access_token):
    owner = await _make_user(db_session)
    member = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    await _add_member(db_session, team, member)
    token = make_access_token(sub=str(member.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/teams/{team.id}/members/{member.id}", token=token)

    assert resp.status_code == 204
    count = await db_session.scalar(
        select(func.count()).select_from(TeamMembership).where(TeamMembership.team_id == team.id)
    )
    assert count == 1


async def test_remove_member_last_owner_cannot_be_removed(db_session, make_access_token):
    """Owner removing themself when a co-member exists: the team would keep
    a member but lose its only owner - rejected even though it's self-removal
    and even though the team wouldn't hit zero members."""
    owner = await _make_user(db_session)
    member = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    await _add_member(db_session, team, member)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/teams/{team.id}/members/{owner.id}", token=token)

    assert resp.status_code == 400


async def test_remove_member_last_member_cannot_be_removed(db_session, make_access_token):
    """A solo owner (team's only member) removing themself hits the more
    general zero-members guard rather than the owner-specific one."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/teams/{team.id}/members/{owner.id}", token=token)

    assert resp.status_code == 400


async def test_remove_member_only_owner_can_remove_owner(db_session, make_access_token):
    owner = await _make_user(db_session)
    member = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    await _add_member(db_session, team, member)
    member_token = make_access_token(sub=str(member.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/teams/{team.id}/members/{owner.id}", token=member_token)

    assert resp.status_code == 403


async def test_remove_member_target_not_in_team_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    stranger = await _make_user(db_session)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "DELETE", f"/api/teams/{team.id}/members/{stranger.id}", token=token)

    assert resp.status_code == 404


async def test_remove_member_non_member_caller_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(db_session, "DELETE", f"/api/teams/{team.id}/members/{owner.id}", token=outsider_token)

    assert resp.status_code == 404


# --- invitations: create / list / revoke -------------------------------------------


async def test_create_invitation_sends_email_and_excludes_token(db_session, make_access_token, mail_test_settings):
    owner = await _make_user(db_session, email="owner@example.com")
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub), email="owner@example.com")

    mail = FastMail(_connection_config(mail_test_settings))
    with mail.record_messages() as outbox:
        resp = await _request(
            db_session,
            "POST",
            f"/api/teams/{team.id}/invitations",
            token=token,
            settings=mail_test_settings,
            json={"email": "invitee@example.com"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "invitee@example.com"
    assert body["status"] == "pending"
    assert body["team_id"] == str(team.id)
    assert "token" not in body

    result = await db_session.execute(select(TeamInvitation).where(TeamInvitation.id == uuid.UUID(body["id"])))
    invitation = result.scalar_one()
    assert invitation.token

    assert len(outbox) == 1
    assert "invitee@example.com" in str(outbox[0]["To"])
    assert invitation.token in _email_body(outbox[0])
    assert f"/teams/invitations/{invitation.token}" in _email_body(outbox[0])


async def test_create_invitation_non_member_returns_404(db_session, make_access_token, mail_test_settings):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session,
        "POST",
        f"/api/teams/{team.id}/invitations",
        token=outsider_token,
        settings=mail_test_settings,
        json={"email": "invitee@example.com"},
    )

    assert resp.status_code == 404


async def test_list_invitations_returns_pending_only(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    pending = await _make_invitation(db_session, team, owner, "pending@example.com")
    await _make_invitation(db_session, team, owner, "revoked@example.com", status="revoked")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(db_session, "GET", f"/api/teams/{team.id}/invitations", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == str(pending.id)
    assert body[0]["status"] == "pending"


async def test_revoke_invitation_sets_status(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(db_session, team, owner, "invitee@example.com")
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/teams/{team.id}/invitations/{invitation.id}/revoke", token=token
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"
    await db_session.refresh(invitation)
    assert invitation.status == "revoked"


async def test_revoke_invitation_not_found_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    token = make_access_token(sub=str(owner.auth_sub))

    resp = await _request(
        db_session, "POST", f"/api/teams/{team.id}/invitations/{uuid.uuid4()}/revoke", token=token
    )

    assert resp.status_code == 404


async def test_revoke_invitation_non_member_returns_404(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(db_session, team, owner, "invitee@example.com")
    outsider_token = make_access_token(sub=str(uuid.uuid4()))

    resp = await _request(
        db_session, "POST", f"/api/teams/{team.id}/invitations/{invitation.id}/revoke", token=outsider_token
    )

    assert resp.status_code == 404


# --- invitations: accept ----------------------------------------------------------


async def test_accept_invitation_matching_email_case_insensitive(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(db_session, team, owner, "Invitee@Example.com")
    invitee_sub = uuid.uuid4()
    token = make_access_token(sub=str(invitee_sub), email="invitee@example.com")

    resp = await _request(db_session, "POST", f"/api/teams/invitations/{invitation.token}/accept", token=token)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(team.id)
    assert body["role"] == "member"
    assert body["member_count"] == 2

    await db_session.refresh(invitation)
    assert invitation.status == "accepted"
    assert invitation.accepted_at is not None

    result = await db_session.execute(
        select(TeamMembership).join(User, User.id == TeamMembership.user_id).where(User.auth_sub == invitee_sub)
    )
    membership = result.scalar_one()
    assert membership.team_id == team.id
    assert membership.role == "member"


async def test_accept_invitation_mismatched_email_returns_403(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(db_session, team, owner, "invitee@example.com")
    token = make_access_token(sub=str(uuid.uuid4()), email="someoneelse@example.com")

    resp = await _request(db_session, "POST", f"/api/teams/invitations/{invitation.token}/accept", token=token)

    assert resp.status_code == 403
    await db_session.refresh(invitation)
    assert invitation.status == "pending"


async def test_accept_invitation_expired_returns_410(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(
        db_session,
        team,
        owner,
        "invitee@example.com",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    token = make_access_token(sub=str(uuid.uuid4()), email="invitee@example.com")

    resp = await _request(db_session, "POST", f"/api/teams/invitations/{invitation.token}/accept", token=token)

    assert resp.status_code == 410


async def test_accept_invitation_revoked_returns_410(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(db_session, team, owner, "invitee@example.com", status="revoked")
    token = make_access_token(sub=str(uuid.uuid4()), email="invitee@example.com")

    resp = await _request(db_session, "POST", f"/api/teams/invitations/{invitation.token}/accept", token=token)

    assert resp.status_code == 410


async def test_accept_invitation_already_accepted_returns_410(db_session, make_access_token):
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    invitation = await _make_invitation(db_session, team, owner, "invitee@example.com")
    token = make_access_token(sub=str(uuid.uuid4()), email="invitee@example.com")

    first = await _request(db_session, "POST", f"/api/teams/invitations/{invitation.token}/accept", token=token)
    assert first.status_code == 200

    second = await _request(db_session, "POST", f"/api/teams/invitations/{invitation.token}/accept", token=token)
    assert second.status_code == 410


async def test_accept_invitation_unknown_token_returns_404(db_session, make_access_token):
    token = make_access_token(sub=str(uuid.uuid4()), email="invitee@example.com")

    resp = await _request(db_session, "POST", "/api/teams/invitations/does-not-exist/accept", token=token)

    assert resp.status_code == 404


async def test_accept_invitation_existing_member_does_not_duplicate(db_session, make_access_token):
    """Two separate pending invitations to the same team/email: accepting
    both must not violate team_memberships' (team_id, user_id) uniqueness."""
    owner = await _make_user(db_session)
    team = await _make_team_with_owner(db_session, owner)
    first_invitation = await _make_invitation(db_session, team, owner, "invitee@example.com")
    second_invitation = await _make_invitation(db_session, team, owner, "invitee@example.com")
    invitee_sub = uuid.uuid4()
    token = make_access_token(sub=str(invitee_sub), email="invitee@example.com")

    first = await _request(
        db_session, "POST", f"/api/teams/invitations/{first_invitation.token}/accept", token=token
    )
    second = await _request(
        db_session, "POST", f"/api/teams/invitations/{second_invitation.token}/accept", token=token
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["member_count"] == 2

    result = await db_session.execute(
        select(func.count())
        .select_from(TeamMembership)
        .join(User, User.id == TeamMembership.user_id)
        .where(User.auth_sub == invitee_sub, TeamMembership.team_id == team.id)
    )
    assert result.scalar_one() == 1
