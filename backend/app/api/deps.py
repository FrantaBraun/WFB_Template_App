# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.team import TeamMembership
from app.models.user import User
from app.security.jwt import get_current_user_claims

# A second, auto_error=False instance - not app.security.jwt's shared
# bearer_scheme (which is auto_error=True and would reject an anonymous
# request before get_current_user_optional's body ever runs). Same pattern
# as app/modules/kontaktni_formular/router.py's _optional_bearer.
_optional_bearer = HTTPBearer(auto_error=False)


async def _resolve_current_user(claims: dict, db: AsyncSession) -> User:
    """Resolve the local User row for a verified JWT's claims, creating it on
    first sight, and keeping the cached email fresh from the claim if it has
    changed since the last login (see app/models/user.py for why email is
    cached at all). Shared by get_current_user and get_current_user_optional
    so both resolve a User identically once claims are verified - they only
    differ in how an unverifiable/missing token is handled.

    Uses INSERT ... ON CONFLICT DO NOTHING rather than a naive
    check-then-insert, since two near-simultaneous first requests from the
    same brand-new user (e.g. /me firing right after /login) can otherwise
    race the auth_sub uniqueness constraint.
    """
    auth_sub = UUID(claims["sub"])

    result = await db.execute(select(User).where(User.auth_sub == auth_sub))
    user = result.scalar_one_or_none()
    if user is None:
        await db.execute(
            pg_insert(User).values(auth_sub=auth_sub).on_conflict_do_nothing(index_elements=[User.auth_sub])
        )
        await db.commit()
        result = await db.execute(select(User).where(User.auth_sub == auth_sub))
        user = result.scalar_one()

    email = claims.get("email")
    if email != user.email:
        user.email = email
        await db.commit()
        # updated_at has onupdate=func.now(): once an ORM UPDATE touches it,
        # SQLAlchemy marks it expired rather than assuming a value, since the
        # server-computed result isn't known without a round-trip. Refresh
        # now so callers never hit a lazy-load (MissingGreenlet) trying to
        # read it later from a sync context, e.g. a Pydantic response model.
        await db.refresh(user)

    return user


async def get_current_user(
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the local User row for a verified JWT's sub claim - see
    _resolve_current_user for the resolve/create/email-refresh logic."""
    return await _resolve_current_user(claims, db)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user, but for endpoints that behave differently for
    anonymous vs. signed-in callers instead of rejecting anonymous ones
    outright - generalizes app/modules/kontaktni_formular/router.py's
    claims-level try/except HTTPException -> None pattern one step further,
    through to a resolved local User row. Returns None for no token, or a
    token that fails verification (malformed, expired, wrong key, ...) -
    never raises.
    """
    if credentials is None:
        return None

    try:
        claims = await get_current_user_claims(credentials)
    except HTTPException:
        return None

    return await _resolve_current_user(claims, db)


async def require_team_membership(db: AsyncSession, team_id: UUID, user: User) -> None:
    """A team the caller isn't a member of is indistinguishable from one
    that doesn't exist - 404, not 403 (same rule/pattern as
    app/api/teams/router.py's own _require_membership, which returns the
    TeamMembership row itself for callers that need it - this one is just
    the yes/no gate). Originally private to app/api/api_docs/router.py,
    moved here so app/api/collections/router.py (and a later
    integrations/router.py) can share the identical check instead of a
    third near-duplicate copy."""
    result = await db.execute(
        select(TeamMembership.id).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Team not found")


async def is_team_member(db: AsyncSession, team_id: UUID, user_id: UUID) -> bool:
    """Plain boolean membership check, for endpoints that behave differently
    for members vs. non-members rather than rejecting non-members outright
    (e.g. a visibility check that also lets a public resource through) - see
    require_team_membership above for the reject-outright case. Moved here
    alongside it, for the same reason."""
    result = await db.execute(
        select(TeamMembership.id).where(TeamMembership.team_id == team_id, TeamMembership.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None
