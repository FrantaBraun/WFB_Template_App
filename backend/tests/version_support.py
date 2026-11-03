# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Helpers shared by the tests of what changed between two versions of a
document: small specs, documents with their versions recorded through the
real process_new_spec, and an ASGI request that goes through the real JWT and
DB dependencies."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings, get_settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.collection import Collection, CollectionDocument
from app.models.integration import Integration, IntegrationCollection, IntegrationDocument
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.services.api_document_versions import process_new_spec


def pets_spec(version: str = "1.0.0", paths: dict | None = None, **top) -> dict:
    """A small OpenAPI 3 spec: GET /pets answering a list of {id}."""
    default = {
        "/pets": {
            "get": {
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
                            }
                        },
                    }
                }
            }
        }
    }
    return {
        "openapi": "3.0.0",
        "info": {"title": "Pets", "version": version},
        "paths": default if paths is None else paths,
        **top,
    }


def spec_bytes(spec: dict) -> bytes:
    return json.dumps(spec).encode()


async def make_user(db_session, email: str | None = None) -> User:
    user = User(auth_sub=uuid.uuid4(), email=email)
    db_session.add(user)
    await db_session.flush()
    return user


async def make_document(db_session, *, members: tuple[User, ...] = (), **overrides) -> ApiDocument:
    """A document of its own team (created by a user who is a member too), plus `members`."""
    team = Team(name="Test Team")
    db_session.add(team)
    await db_session.flush()
    creator = await make_user(db_session)
    for member in (creator, *members):
        db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    fields = dict(team_id=team.id, title="Pets API", created_by_user_id=creator.id, source_url=None)
    fields.update(overrides)
    doc = ApiDocument(**fields)
    db_session.add(doc)
    await db_session.flush()
    return doc


async def record(db_session, doc: ApiDocument, spec: dict, uploads_dir, *, source: str = "manual_upload") -> ApiDocumentVersion:
    """Record a spec as the document's next version through process_new_spec."""
    version = await process_new_spec(
        doc, spec_bytes(spec), source=source, db=db_session, uploads_dir=str(uploads_dir), max_size_bytes=10_000_000
    )
    assert version is not None
    return version


async def record_history(db_session, doc: ApiDocument, specs: list[dict], uploads_dir) -> list[ApiDocumentVersion]:
    """Record several specs in order and give the rows distinct, ordered
    fetched_at values - inside one test transaction every row would
    otherwise share one now(), and "the version before this one" would be
    undefined."""
    versions = []
    start = datetime.now(timezone.utc) - timedelta(days=len(specs))
    for index, spec in enumerate(specs):
        version = await record(db_session, doc, spec, uploads_dir)
        version.fetched_at = start + timedelta(days=index)
        await db_session.flush()
        versions.append(version)
    return versions


def token_for(make_access_token, user: User) -> str:
    return make_access_token(sub=str(user.auth_sub), email=user.email, login=user.login)


def docs_settings(uploads_dir) -> Settings:
    return Settings(uploads_dir=str(uploads_dir), spec_fetch_timeout_seconds=5.0)


async def request(db_session, method: str, path: str, *, token: str | None = None, settings: Settings | None = None, **kwargs):
    from app.database import get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    if settings is not None:
        fastapi_app.dependency_overrides[get_settings] = lambda: settings
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, **kwargs)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        if settings is not None:
            fastapi_app.dependency_overrides.pop(get_settings, None)


async def make_team(db_session, name: str, members=()) -> Team:
    """A team with the given members (no document attached - see make_document)."""
    team = Team(name=name)
    db_session.add(team)
    await db_session.flush()
    for member in members:
        db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    await db_session.flush()
    return team


async def make_integration(db_session, team: Team, creator, name: str, *, documents=(), collections=()) -> Integration:
    integration = Integration(team_id=team.id, name=name, created_by_user_id=creator.id)
    db_session.add(integration)
    await db_session.flush()
    for doc in documents:
        db_session.add(IntegrationDocument(integration_id=integration.id, documentation_id=doc.id, added_by_user_id=creator.id))
    for collection in collections:
        db_session.add(IntegrationCollection(integration_id=integration.id, collection_id=collection.id, added_by_user_id=creator.id))
    await db_session.flush()
    return integration


async def make_collection(db_session, team: Team, creator, *, documents=()) -> Collection:
    collection = Collection(team_id=team.id, name="Some collection", created_by_user_id=creator.id)
    db_session.add(collection)
    await db_session.flush()
    for doc in documents:
        db_session.add(CollectionDocument(collection_id=collection.id, documentation_id=doc.id, added_by_user_id=creator.id))
    await db_session.flush()
    return collection
