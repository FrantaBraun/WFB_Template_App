# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.event_booking.slots import local_now
from app.security.jwt import get_current_user_claims

# auto_error=False: a visitor with no token reaches the route as None instead
# of being turned away with a 401 before it runs.
_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """The signed-in user, or None for a visitor with no (or an unusable)
    token. The core's get_current_user is untouched and still requires one.

    A token that fails verification (expired, say) is treated as no token: a
    public registration still works for that visitor, and one that needs a
    login answers 401 itself, which is what makes the client refresh its token
    and retry."""
    if credentials is None:
        return None
    try:
        claims = await get_current_user_claims(credentials)
    except HTTPException:
        return None
    return await get_current_user(claims=claims, db=db)


def get_now() -> datetime:
    """"Now" in the local (Europe/Prague) time - a dependency so a test can set the clock."""
    return local_now()
