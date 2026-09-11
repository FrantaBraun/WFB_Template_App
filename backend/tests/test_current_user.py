# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.api.deps.get_current_user: resolving or creating the local
User row for a verified JWT sub (including the ON CONFLICT race it guards),
and keeping its cached email in sync with the claim."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import get_current_user
from app.models.user import User


async def test_creates_row_for_new_sub(db_session):
    sub = uuid.uuid4()

    user = await get_current_user(claims={"sub": str(sub)}, db=db_session)

    assert user.auth_sub == sub
    count = await db_session.scalar(select(func.count()).select_from(User).where(User.auth_sub == sub))
    assert count == 1


async def test_reuses_existing_row_for_same_sub(db_session):
    sub = uuid.uuid4()

    first = await get_current_user(claims={"sub": str(sub)}, db=db_session)
    second = await get_current_user(claims={"sub": str(sub)}, db=db_session)

    assert first.id == second.id
    count = await db_session.scalar(select(func.count()).select_from(User).where(User.auth_sub == sub))
    assert count == 1


async def test_conflicting_insert_does_not_raise(db_session):
    """Simulates the race get_current_user guards against: a row for this
    auth_sub already exists by the time the INSERT runs. ON CONFLICT DO
    NOTHING must swallow it rather than raise IntegrityError."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub))
    await db_session.flush()

    stmt = pg_insert(User).values(auth_sub=sub).on_conflict_do_nothing(index_elements=[User.auth_sub])
    await db_session.execute(stmt)  # must not raise

    count = await db_session.scalar(select(func.count()).select_from(User).where(User.auth_sub == sub))
    assert count == 1


async def test_email_set_on_first_creation_from_claim(db_session):
    sub = uuid.uuid4()

    user = await get_current_user(claims={"sub": str(sub), "email": "first@example.com"}, db=db_session)

    assert user.email == "first@example.com"


async def test_email_refreshed_when_claim_changes_on_later_login(db_session):
    sub = uuid.uuid4()
    first = await get_current_user(claims={"sub": str(sub), "email": "old@example.com"}, db=db_session)
    assert first.email == "old@example.com"

    second = await get_current_user(claims={"sub": str(sub), "email": "new@example.com"}, db=db_session)

    assert second.id == first.id
    assert second.email == "new@example.com"
