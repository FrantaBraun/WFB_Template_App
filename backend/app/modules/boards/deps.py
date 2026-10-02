# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.security.jwt import get_current_user_claims

_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """The signed-in user, or None for an anonymous visitor - and also for a
    token that no longer verifies. The listings are public, and the
    frontend sends the stored token with every request: answering a stale
    token with 401 would make its client log the visitor out of a page that
    never needed a login."""
    if credentials is None:
        return None
    try:
        claims = await get_current_user_claims(credentials)
    except HTTPException:
        return None
    return await get_current_user(claims=claims, db=db)


async def get_active_user(user: User = Depends(get_current_user)) -> User:
    """The signed-in user, unless this application has blocked their account
    - then 403 with {"code": "account_blocked", "reason"}, so the frontend
    can say why. For everything that writes: posting, creating a category,
    resonating, checking a draft."""
    if user.is_blocked:
        raise HTTPException(
            status_code=403, detail={"code": "account_blocked", "reason": user.blocked_reason}
        )
    return user
