# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.api.deps.require_admin: the is_admin gate built on top of
get_current_user, exercised directly rather than through HTTP (same style as
test_current_user.py)."""

import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.models.user import User


async def test_admin_user_passes(db_session):
    user = User(auth_sub=uuid.uuid4(), is_admin=True)
    db_session.add(user)
    await db_session.flush()

    result = await require_admin(current_user=user)

    assert result is user


async def test_non_admin_user_raises_403(db_session):
    user = User(auth_sub=uuid.uuid4(), is_admin=False)
    db_session.add(user)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await require_admin(current_user=user)

    assert exc_info.value.status_code == 403
