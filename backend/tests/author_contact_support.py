# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Helpers shared by the tests of contacting the author of a document or
collection (app/services/author_contact.py): rows for the two ends, the
target, and the settings the tests run with."""

import uuid

from app.config import Settings
from app.models.api_document import ApiDocument
from app.models.collection import Collection
from app.models.team import Team, TeamMembership
from app.models.user import User


def author_settings(**overrides) -> Settings:
    """Mail built but never sent, a frontend address to link to."""
    values = {
        "frontend_url": "http://app.test",
        "mail_from": "noreply@example.com",
        "mail_suppress_send": True,
        "mail_username": "smtp-user",
        "mail_password": "smtp-pass",
        "mail_server": "smtp.example.com",
    }
    values.update(overrides)
    return Settings(**values)


async def make_user(db_session, email: str | None = None, **fields) -> User:
    user = User(auth_sub=uuid.uuid4(), email=email, **fields)
    db_session.add(user)
    await db_session.flush()
    return user


async def make_team(db_session, name: str = "Platform Team", members: tuple[User, ...] = ()) -> Team:
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    for member in members:
        db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    await db_session.flush()
    return team


async def make_document(db_session, team: Team, author: User, **overrides) -> ApiDocument:
    fields = dict(team_id=team.id, title="Payments API", created_by_user_id=author.id, is_public=True)
    fields.update(overrides)
    doc = ApiDocument(**fields)
    db_session.add(doc)
    await db_session.flush()
    return doc


async def make_collection(db_session, team: Team, author: User, **overrides) -> Collection:
    fields = dict(team_id=team.id, name="Billing APIs", created_by_user_id=author.id, is_public=True)
    fields.update(overrides)
    collection = Collection(**fields)
    db_session.add(collection)
    await db_session.flush()
    return collection
