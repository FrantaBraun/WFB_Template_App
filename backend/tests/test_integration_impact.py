# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the impact of a new version on integrations: which integrations
use a document (directly or through a collection), that the members of their
teams are told even though they never subscribed - but only when they may see
the document - with the names of THEIR OWN teams' integrations and nobody
else's (integrations are team-private), and where the API shows it (the
document's detail, the bell, an integration's document list).

socket.getfqdn is stubbed because building an e-mail calls it for the
Message-ID and costs about a second per message on the development machine."""

import socket
from email.utils import getaddresses

import pytest
from fastapi_mail import FastMail
from sqlalchemy import select

import app.security.jwt as jwt_module
import app.services.notifications as notifications_module
from app.config import Settings
from app.models.api_document import ApiDocument
from app.models.collection import Collection, CollectionDocument
from app.models.integration import Integration, IntegrationCollection, IntegrationDocument
from app.models.notification import Notification
from app.models.team import Team, TeamMembership
from app.services.email import _connection_config
from app.services.integration_usage import integrations_using_documents
from tests.version_support import make_document, make_user, pets_spec, record, request, token_for


@pytest.fixture(autouse=True)
def _quiet_environment(rsa_keypair, monkeypatch):
    _, public_pem = rsa_keypair
    monkeypatch.setattr(jwt_module, "_public_key", public_pem)
    monkeypatch.setattr(socket, "getfqdn", lambda *args, **kwargs: "localhost")


# --- builders -----------------------------------------------------------------------


async def make_team(db_session, name: str, members=()) -> Team:
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


def _breaking_spec(version: str) -> dict:
    return pets_spec(version, paths={})  # every operation gone: breaking


async def _publish_two_versions(db_session, doc, tmp_path):
    """v1, then a breaking v2 - returns (v2, the mails sent for v2)."""
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    mail = FastMail(_connection_config(Settings(mail_suppress_send=True, mail_server="smtp.example.com")))
    with mail.record_messages() as outbox:
        second = await record(db_session, doc, _breaking_spec("2.0.0"), tmp_path)
    return second, list(outbox)


def _mail_for(outbox, address: str):
    found = [m for m in outbox if address in [a for _, a in getaddresses([str(m["To"])])]]
    assert len(found) == 1, f"{address}: {[str(m['To']) for m in outbox]}"
    return str(found[0]["Subject"]), found[0].get_payload()[0].get_payload(decode=True).decode()


async def _notified(db_session, doc, version) -> set:
    rows = await db_session.execute(
        select(Notification.user_id).where(Notification.documentation_id == doc.id, Notification.version_id == version.id)
    )
    return set(rows.scalars().all())


# --- which integrations use a document ----------------------------------------------


async def test_finds_direct_and_collection_integrations_once_each_by_name(db_session):
    user = await make_user(db_session)
    team = await make_team(db_session, "T", members=(user,))
    doc = await make_document(db_session, members=(user,))
    other_doc = await make_document(db_session)
    collection = await make_collection(db_session, team, user, documents=(doc,))
    both = await make_integration(db_session, team, user, "Zeta", documents=(doc,), collections=(collection,))
    only_collection = await make_integration(db_session, team, user, "alpha", collections=(collection,))

    found = await integrations_using_documents(db_session, [doc.id, other_doc.id])

    assert [ref.name for ref in found[doc.id]] == ["alpha", "Zeta"]  # by name, case-insensitively, each once
    assert {ref.id for ref in found[doc.id]} == {both.id, only_collection.id}
    assert other_doc.id not in found  # nothing uses it


async def test_with_a_user_only_integrations_of_the_users_teams_are_returned(db_session):
    mine, stranger = await make_user(db_session), await make_user(db_session)
    my_team = await make_team(db_session, "Mine", members=(mine,))
    other_team = await make_team(db_session, "Other", members=(stranger,))
    doc = await make_document(db_session, is_public=True)
    await make_integration(db_session, my_team, mine, "My integration", documents=(doc,))
    await make_integration(db_session, other_team, stranger, "Their secret project", documents=(doc,))

    seen_by_me = await integrations_using_documents(db_session, [doc.id], user_id=mine.id)
    seen_by_nobody_relevant = await integrations_using_documents(db_session, [doc.id], user_id=(await make_user(db_session)).id)

    assert [ref.name for ref in seen_by_me[doc.id]] == ["My integration"]
    assert seen_by_nobody_relevant == {}


async def test_no_documents_means_no_query_and_an_empty_answer(db_session):
    assert await integrations_using_documents(db_session, []) == {}


# --- who is told, and what they read ------------------------------------------------


async def test_the_team_of_an_integration_using_a_public_document_is_told_with_its_integration_named(db_session, tmp_path):
    doc_member = await make_user(db_session, email="doc-member@example.com")
    integrator = await make_user(db_session, email="integrator@example.com")
    doc = await make_document(db_session, members=(doc_member,), is_public=True, title="Pets API")
    team = await make_team(db_session, "Integrators", members=(integrator,))
    await make_integration(db_session, team, integrator, "Billing sync", documents=(doc,))

    second, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    assert integrator.id in await _notified(db_session, doc, second)
    _, integrator_body = _mail_for(outbox, "integrator@example.com")
    assert "This affects your integration: Billing sync." in integrator_body
    subject, member_body = _mail_for(outbox, "doc-member@example.com")
    assert "Billing sync" not in member_body and "This affects" not in member_body
    assert subject == "New version of Pets API: 2.0.0 - 1 breaking change"


async def test_an_integration_through_a_collection_counts_too(db_session, tmp_path):
    integrator = await make_user(db_session, email="integrator@example.com")
    doc = await make_document(db_session, is_public=True)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    collection = await make_collection(db_session, team, integrator, documents=(doc,))
    await make_integration(db_session, team, integrator, "Via collection", collections=(collection,))

    second, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    assert integrator.id in await _notified(db_session, doc, second)
    assert "This affects your integration: Via collection." in _mail_for(outbox, "integrator@example.com")[1]


async def test_a_private_documents_versions_are_not_sent_to_another_teams_integration(db_session, tmp_path):
    """An integration can still reference a document that was made private
    after it was added; its team has lost the right to know about it."""
    doc_member = await make_user(db_session, email="doc-member@example.com")
    integrator = await make_user(db_session, email="integrator@example.com")
    doc = await make_document(db_session, members=(doc_member,), is_public=False)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    await make_integration(db_session, team, integrator, "Stale reference", documents=(doc,))

    second, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    assert integrator.id not in await _notified(db_session, doc, second)
    assert all("integrator@example.com" not in str(m["To"]) for m in outbox)


async def test_an_integration_of_the_documents_own_team_names_itself_even_when_private(db_session, tmp_path):
    member = await make_user(db_session, email="member@example.com")
    doc = await make_document(db_session, members=(member,), is_public=False)
    team = await db_session.get(Team, doc.team_id)
    await make_integration(db_session, team, member, "Internal", documents=(doc,))

    _, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    assert "This affects your integration: Internal." in _mail_for(outbox, "member@example.com")[1]


async def test_someone_in_both_teams_gets_one_notification_and_one_mail(db_session, tmp_path):
    both = await make_user(db_session, email="both@example.com")
    doc = await make_document(db_session, members=(both,), is_public=True)
    team = await make_team(db_session, "Integrators", members=(both,))
    await make_integration(db_session, team, both, "Mine", documents=(doc,))

    second, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    rows = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == both.id, Notification.version_id == second.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert "This affects your integration: Mine." in _mail_for(outbox, "both@example.com")[1]  # exactly one mail


async def test_several_integrations_of_one_team_are_named_together_and_other_teams_get_their_own_mail(db_session, tmp_path):
    first_user = await make_user(db_session, email="one@example.com")
    second_user = await make_user(db_session, email="two@example.com")
    doc = await make_document(db_session, is_public=True)
    team_one = await make_team(db_session, "One", members=(first_user,))
    team_two = await make_team(db_session, "Two", members=(second_user,))
    await make_integration(db_session, team_one, first_user, "Beta", documents=(doc,))
    await make_integration(db_session, team_one, first_user, "Alpha", documents=(doc,))
    await make_integration(db_session, team_two, second_user, "Gamma", documents=(doc,))

    _, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    one = _mail_for(outbox, "one@example.com")[1]
    two = _mail_for(outbox, "two@example.com")[1]
    assert "This affects your integrations: Alpha, Beta." in one and "Gamma" not in one
    assert "This affects your integration: Gamma." in two and "Alpha" not in two and "Beta" not in two


async def test_a_member_of_an_integration_team_without_an_address_still_gets_the_notification(db_session, tmp_path):
    integrator = await make_user(db_session, email=None)
    doc = await make_document(db_session, is_public=True)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    await make_integration(db_session, team, integrator, "Quiet", documents=(doc,))

    second, outbox = await _publish_two_versions(db_session, doc, tmp_path)

    assert integrator.id in await _notified(db_session, doc, second)
    assert all("Quiet" not in m.get_payload()[0].get_payload(decode=True).decode() for m in outbox)


async def test_a_mail_that_fails_does_not_stop_the_others(db_session, tmp_path, monkeypatch):
    first_user = await make_user(db_session, email="one@example.com")
    second_user = await make_user(db_session, email="two@example.com")
    doc = await make_document(db_session, members=(first_user,), is_public=True)
    team = await make_team(db_session, "Integrators", members=(second_user,))
    await make_integration(db_session, team, second_user, "Mine", documents=(doc,))
    await record(db_session, doc, pets_spec("1.0.0"), tmp_path)
    real_send = notifications_module.send_email
    attempts: list[list[str]] = []

    async def flaky(*, subject, recipients, body, settings):
        attempts.append(list(recipients))
        if len(attempts) == 1:
            raise ConnectionError("smtp down")
        return await real_send(subject=subject, recipients=recipients, body=body, settings=settings)

    monkeypatch.setattr(notifications_module, "send_email", flaky)

    second = await record(db_session, doc, _breaking_spec("2.0.0"), tmp_path)  # must not raise

    assert second.version == "2.0.0"
    assert len(attempts) == 2  # both groups were tried


# --- the API ------------------------------------------------------------------------


async def _scenario(db_session, tmp_path):
    """A public document used by another team's integration; returns the pieces."""
    doc_member = await make_user(db_session, email="doc-member@example.com")
    integrator = await make_user(db_session, email="integrator@example.com")
    doc = await make_document(db_session, members=(doc_member,), is_public=True)
    team = await make_team(db_session, "Integrators", members=(integrator,))
    integration = await make_integration(db_session, team, integrator, "Billing sync", documents=(doc,))
    second, _ = await _publish_two_versions(db_session, doc, tmp_path)
    return doc_member, integrator, doc, integration, second


async def test_the_detail_names_only_the_viewers_own_teams_integrations(db_session, make_access_token, tmp_path):
    doc_member, integrator, doc, integration, _ = await _scenario(db_session, tmp_path)
    path = f"/api/api-docs/{doc.id}"

    as_integrator = await request(db_session, "GET", path, token=token_for(make_access_token, integrator))
    as_doc_member = await request(db_session, "GET", path, token=token_for(make_access_token, doc_member))
    anonymous = await request(db_session, "GET", path)

    assert as_integrator.json()["integrations"] == [{"id": str(integration.id), "name": "Billing sync"}]
    assert as_doc_member.json()["integrations"] == []
    assert anonymous.json()["integrations"] == []
    assert "Billing sync" not in as_doc_member.text and "Billing sync" not in anonymous.text


async def test_the_bell_says_which_of_my_integrations_a_version_affects(db_session, make_access_token, tmp_path):
    doc_member, integrator, doc, integration, _ = await _scenario(db_session, tmp_path)

    mine = await request(db_session, "GET", "/api/notifications", token=token_for(make_access_token, integrator))
    theirs = await request(db_session, "GET", "/api/notifications", token=token_for(make_access_token, doc_member))

    assert {i["version"]: i["integrations"] for i in mine.json()["items"]}["2.0.0"] == [
        {"id": str(integration.id), "name": "Billing sync"}
    ]
    assert all(i["integrations"] == [] for i in theirs.json()["items"])
    assert "Billing sync" not in theirs.text


async def test_an_integrations_documents_carry_what_their_current_version_changed(db_session, make_access_token, tmp_path):
    doc_member, integrator, doc, integration, second = await _scenario(db_session, tmp_path)
    fresh = await make_document(db_session, is_public=True, title="Only one version")
    await record(db_session, fresh, pets_spec("1.0.0"), tmp_path)
    db_session.add(IntegrationDocument(integration_id=integration.id, documentation_id=fresh.id, added_by_user_id=integrator.id))
    await db_session.flush()

    resp = await request(
        db_session, "GET", f"/api/integrations/{integration.id}/documents", token=token_for(make_access_token, integrator)
    )

    assert resp.status_code == 200
    by_title = {row["title"]: row for row in resp.json()}
    changed = by_title["Pets API"]["latest_change"]
    assert changed["version_id"] == str(second.id) and changed["version"] == "2.0.0"
    assert changed["summary"] == {"breaking": 1, "warning": 0, "info": 0}
    assert changed["content_changed"] is False and changed["fetched_at"]
    assert by_title["Only one version"]["latest_change"] is None  # nothing before it
