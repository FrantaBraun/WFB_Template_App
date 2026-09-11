# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.teams.schemas import (
    InvitationCreate,
    InvitationOut,
    TeamCreate,
    TeamDetail,
    TeamMemberOut,
    TeamSummary,
    TeamUpdate,
)
from app.config import Settings, get_settings
from app.database import get_db
from app.models.team import Team, TeamInvitation, TeamMembership
from app.models.user import User
from app.security.jwt import get_current_user_claims
from app.services.email import send_email

logger = logging.getLogger(__name__)

router = APIRouter()

INVITATION_VALIDITY = timedelta(days=7)


async def _require_membership(db: AsyncSession, team_id: uuid.UUID, user: User) -> TeamMembership:
    """A team the caller isn't a member of is indistinguishable from one that
    doesn't exist - 404, not 403, per this codebase's private-resource rule."""
    result = await db.execute(
        select(TeamMembership).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user.id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return membership


async def _get_team_or_404(db: AsyncSession, team_id: uuid.UUID) -> Team:
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def _member_count(db: AsyncSession, team_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count()).select_from(TeamMembership).where(TeamMembership.team_id == team_id)
    )
    return count or 0


def _team_summary(team: Team, role: str, member_count: int) -> TeamSummary:
    return TeamSummary(
        id=team.id, name=team.name, role=role, member_count=member_count, created_at=team.created_at
    )


@router.post("", status_code=201)
async def create_team(
    body: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamSummary:
    team = Team(name=body.name)
    db.add(team)
    await db.flush()
    db.add(TeamMembership(team_id=team.id, user_id=current_user.id, role="owner"))
    await db.commit()
    await db.refresh(team)
    return _team_summary(team, role="owner", member_count=1)


@router.get("")
async def list_teams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeamSummary]:
    member_counts = (
        select(TeamMembership.team_id, func.count(TeamMembership.id).label("member_count"))
        .group_by(TeamMembership.team_id)
        .subquery()
    )
    stmt = (
        select(Team, TeamMembership.role, member_counts.c.member_count)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .join(member_counts, member_counts.c.team_id == Team.id)
        .where(TeamMembership.user_id == current_user.id)
        .order_by(Team.name.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [_team_summary(team, role, count) for team, role, count in rows]


@router.get("/{team_id}")
async def get_team(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamDetail:
    await _require_membership(db, team_id, current_user)
    team = await _get_team_or_404(db, team_id)

    result = await db.execute(
        select(TeamMembership, User.email)
        .join(User, User.id == TeamMembership.user_id)
        .where(TeamMembership.team_id == team_id)
        .order_by(TeamMembership.created_at.asc())
    )
    members = [
        TeamMemberOut(user_id=membership.user_id, email=email, role=membership.role, joined_at=membership.created_at)
        for membership, email in result.all()
    ]
    return TeamDetail(id=team.id, name=team.name, members=members)


@router.patch("/{team_id}")
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamSummary:
    membership = await _require_membership(db, team_id, current_user)
    team = await _get_team_or_404(db, team_id)
    team.name = body.name
    await db.commit()
    await db.refresh(team)
    count = await _member_count(db, team_id)
    return _team_summary(team, membership.role, count)


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    caller_membership = await _require_membership(db, team_id, current_user)

    result = await db.execute(
        select(TeamMembership).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user_id)
    )
    target_membership = result.scalar_one_or_none()
    if target_membership is None:
        raise HTTPException(status_code=404, detail="Team member not found")

    is_self = target_membership.user_id == current_user.id
    if target_membership.role == "owner" and not is_self and caller_membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only an owner can remove another owner")

    # Checked in this order (total-members before owner-count) so a solo
    # owner removing themself gets the more general "last member" message
    # rather than "last owner" - both guards would otherwise fire at once.
    total_members = await _member_count(db, team_id)
    if total_members <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last member of a team")

    if target_membership.role == "owner":
        owner_count = await db.scalar(
            select(func.count())
            .select_from(TeamMembership)
            .where(TeamMembership.team_id == team_id, TeamMembership.role == "owner")
        )
        if owner_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner of a team")

    await db.delete(target_membership)
    await db.commit()


@router.post("/{team_id}/invitations", status_code=201)
async def create_invitation(
    team_id: uuid.UUID,
    body: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InvitationOut:
    await _require_membership(db, team_id, current_user)

    invitation = TeamInvitation(
        team_id=team_id,
        email=body.email,
        invited_by_user_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + INVITATION_VALIDITY,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    invite_link = f"{settings.frontend_url}/teams/invitations/{invitation.token}"
    try:
        await send_email(
            subject="You've been invited to join a team on API Hub",
            recipients=[invitation.email],
            body=f"You've been invited to join a team on API Hub. Accept your invitation: {invite_link}",
            settings=settings,
        )
    except Exception as exc:
        logger.exception("Failed to send team invitation email")
        raise HTTPException(status_code=502, detail="Failed to send invitation email") from exc

    return InvitationOut.model_validate(invitation)


@router.get("/{team_id}/invitations")
async def list_invitations(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationOut]:
    await _require_membership(db, team_id, current_user)
    result = await db.execute(
        select(TeamInvitation)
        .where(TeamInvitation.team_id == team_id, TeamInvitation.status == "pending")
        .order_by(TeamInvitation.created_at.desc())
    )
    return [InvitationOut.model_validate(invitation) for invitation in result.scalars().all()]


@router.post("/{team_id}/invitations/{invitation_id}/revoke")
async def revoke_invitation(
    team_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationOut:
    await _require_membership(db, team_id, current_user)
    result = await db.execute(
        select(TeamInvitation).where(TeamInvitation.id == invitation_id, TeamInvitation.team_id == team_id)
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")

    invitation.status = "revoked"
    await db.commit()
    await db.refresh(invitation)
    return InvitationOut.model_validate(invitation)


@router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str,
    claims: dict = Depends(get_current_user_claims),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamSummary:
    result = await db.execute(select(TeamInvitation).where(TeamInvitation.token == token))
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status == "accepted":
        raise HTTPException(status_code=410, detail="This invitation has already been accepted")
    if invitation.status == "revoked":
        raise HTTPException(status_code=410, detail="This invitation has been revoked")
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This invitation has expired")

    claim_email = (claims.get("email") or "").strip().lower()
    if claim_email != invitation.email.strip().lower():
        raise HTTPException(status_code=403, detail="This invitation was sent to a different email address")

    membership_result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == invitation.team_id, TeamMembership.user_id == current_user.id
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        # Normal case: no prior membership, so create one as a plain member -
        # invitations never grant "owner", only the team creator gets that.
        membership = TeamMembership(team_id=invitation.team_id, user_id=current_user.id, role="member")
        db.add(membership)
        role = "member"
    else:
        # Caller already belongs to this team (e.g. a second, still-pending
        # invitation to the same team/email). Don't insert a duplicate row -
        # team_id/user_id is unique - just accept this invitation and report
        # their real existing role instead.
        role = membership.role

    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_by_user_id = current_user.id
    await db.commit()

    team = await _get_team_or_404(db, invitation.team_id)
    count = await _member_count(db, invitation.team_id)
    return _team_summary(team, role, count)
