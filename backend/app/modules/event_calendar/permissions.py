# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Who may create and edit events.

By default: a signed-in user whose auth-service role (the JWT's role_name
claim) is listed in event_calendar.json's editor_roles. An application with
its own notion of administrators replaces the check once at startup:

    from app.modules.event_calendar.permissions import set_editor_check

    async def is_admin(user, claims):
        return user.is_admin

    set_editor_check(is_admin)
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.event_calendar.config import get_config
from app.security.jwt import get_current_user_claims

EditorCheck = Callable[[User, dict], Awaitable[bool]]


async def _role_check(user: User, claims: dict) -> bool:
    return claims.get("role_name") in get_config().editor_roles


_editor_check: EditorCheck = _role_check


def set_editor_check(check: EditorCheck | None) -> None:
    """Replace the editor check; None restores the default role check."""
    global _editor_check
    _editor_check = check or _role_check


async def is_editor(user: User, claims: dict) -> bool:
    return await _editor_check(user, claims)


async def current_user_and_claims(
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, dict]:
    return await get_current_user(claims=claims, db=db), claims


async def require_editor(auth: tuple[User, dict] = Depends(current_user_and_claims)) -> User:
    user, claims = auth
    if not await is_editor(user, claims):
        raise HTTPException(status_code=403, detail="Editor access required")
    return user
