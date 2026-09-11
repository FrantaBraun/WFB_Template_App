# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.api.deps.get_current_user_optional: the get_current_user
variant that returns None for a missing/invalid token instead of raising -
for endpoints that behave differently for anonymous vs. signed-in callers
(e.g. Phase 2's GET /api/api-docs/{id})."""

import time
import uuid

from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select

import app.security.jwt as jwt_module
from app.api.deps import get_current_user_optional
from app.models.user import User


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def test_no_credentials_returns_none(db_session):
    user = await get_current_user_optional(credentials=None, db=db_session)

    assert user is None


async def test_malformed_token_returns_none_not_raises(db_session, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)

    user = await get_current_user_optional(credentials=_credentials("not-a-jwt"), db=db_session)

    assert user is None


async def test_expired_token_returns_none_not_raises(db_session, make_access_token, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    token = make_access_token(exp=int(time.time()) - 10)

    user = await get_current_user_optional(credentials=_credentials(token), db=db_session)

    assert user is None


async def test_valid_token_resolves_and_creates_db_row(
    db_session, make_access_token, rsa_keypair, monkeypatch
):
    """Mirrors test_current_user.py's test_creates_row_for_new_sub: a valid
    token must actually create the local User row, not just return an
    in-memory stand-in."""
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    sub = uuid.uuid4()
    token = make_access_token(sub=str(sub), email="optional@example.com")

    user = await get_current_user_optional(credentials=_credentials(token), db=db_session)

    assert isinstance(user, User)
    assert user.auth_sub == sub
    assert user.email == "optional@example.com"
    count = await db_session.scalar(select(func.count()).select_from(User).where(User.auth_sub == sub))
    assert count == 1


async def test_valid_token_reuses_existing_row(db_session, make_access_token, rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    sub = uuid.uuid4()
    token = make_access_token(sub=str(sub))

    first = await get_current_user_optional(credentials=_credentials(token), db=db_session)
    second = await get_current_user_optional(credentials=_credentials(token), db=db_session)

    assert first.id == second.id
    count = await db_session.scalar(select(func.count()).select_from(User).where(User.auth_sub == sub))
    assert count == 1
