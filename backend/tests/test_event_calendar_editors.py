# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""This app replaces the event_calendar module's role-based editor check
with its own User.is_admin flag (app/main.py) - admins manage events
regardless of their auth-service role, nobody else does."""

import uuid

import app.main  # noqa: F401  (registers the editor check)
from app.models.user import User
from app.modules.event_calendar.permissions import is_editor


async def test_admin_is_editor_whatever_the_role():
    admin = User(auth_sub=uuid.uuid4(), is_admin=True)
    assert await is_editor(admin, {"role_name": "user"}) is True


async def test_non_admin_is_not_editor_even_with_admin_role():
    user = User(auth_sub=uuid.uuid4(), is_admin=False)
    assert await is_editor(user, {"role_name": "admin"}) is False
