# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the User model's own defaults and constraints, independent of
the get_current_user resolution logic covered in test_current_user.py."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.user import User


async def test_create_user_sets_defaults(db_session):
    user = User(auth_sub=uuid.uuid4())
    db_session.add(user)
    await db_session.flush()

    assert user.id is not None
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.nickname is None
    assert user.is_admin is False


async def test_nickname_persists(db_session):
    user = User(auth_sub=uuid.uuid4(), nickname="Frantisek")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    assert user.nickname == "Frantisek"


async def test_auth_sub_must_be_unique(db_session):
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub))
    await db_session.flush()

    db_session.add(User(auth_sub=sub))
    with pytest.raises(IntegrityError):
        await db_session.flush()
