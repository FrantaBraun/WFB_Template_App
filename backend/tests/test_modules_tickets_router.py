# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the tickets module's administrator endpoints (the gate itself:
test_modules_tickets_access.py).

Mounts just this module's router on a throwaway FastAPI app instead of
conftest.py's `client` - whether the module is mounted on the real app
depends on the branch's backend/modules.json. ASGITransport keeps the JWT
dependency chain and db_session on one event loop; every test starts from
empty tickets tables inside its own rolled-back transaction."""

import socket
import uuid
from email.header import decode_header, make_header

import pytest
from fastapi import FastAPI
from fastapi_mail import FastMail
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.modules.crm.models import Partner
from app.modules.tickets import mailbox, service, storage
from app.modules.tickets.models import Ticket, TicketAttachment, TicketEntry
from app.modules.tickets.router import router as tickets_router
from app.services.email import _connection_config
from tests.tickets_support import PDF, PNG, make_mail, tickets_settings

BASE = "/api/modules/tickets"
M = f"{BASE}/manage"

_app = FastAPI()
_app.include_router(tickets_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    await db_session.execute(delete(Ticket))
    await db_session.execute(delete(Partner))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    monkeypatch.setattr(service, "crm_enabled", lambda: False)
    monkeypatch.setattr(socket, "getfqdn", lambda name="": "localhost")  # ~1 s per mail on some machines
    mailbox.status.__init__()
    settings = tickets_settings(tmp_path)
    _app.dependency_overrides[get_db] = lambda: db_session
    _app.dependency_overrides[get_settings] = lambda: settings
    yield
    _app.dependency_overrides.clear()


@pytest.fixture()
def settings(tmp_path):
    return _app.dependency_overrides[get_settings]()


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    """An administrator of this application (local User.is_admin) - with a
    plain auth-service role, since that role must not matter."""
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user', email='boss@example.com')}"}


@pytest.fixture()
def crm_on(monkeypatch):
    monkeypatch.setattr(service, "crm_enabled", lambda: True)


async def _ticket(client, admin, **fields) -> dict:
    resp = await client.post(M, json={"subject": "Nefunguje tisk", **fields}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _entry(client, admin, number, **fields) -> dict:
    resp = await client.post(f"{M}/{number}/entries", json={"kind": "note", "content_html": "<p>Poznámka</p>", **fields}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _partner(db, **fields) -> Partner:
    partner = Partner(name=fields.pop("name", "Jana Nováková"), **fields)
    db.add(partner)
    await db.flush()
    return partner


def _png_upload(name="obrazek.png", data=PNG, content_type="image/png"):
    return {"file": (name, data, content_type)}


# --- Creating -----------------------------------------------------------------


async def test_a_ticket_defaults_to_the_general_type_and_open(client, admin):
    ticket = await _ticket(client, admin)

    assert ticket["number"] >= 100001
    assert (ticket["type"], ticket["status"], ticket["source"]) == ("general", "open", "manual")
    assert (ticket["requester_name"], ticket["requester_email"], ticket["partner"]) == (None, None, None)
    assert ticket["total_minutes"] == 0 and ticket["entries"] == []


async def test_the_description_becomes_the_first_note_sanitized_and_signed(client, admin):
    ticket = await _ticket(
        client,
        admin,
        type="issue",
        requester_name="Jana",
        requester_email="jana@example.com",
        description_html='<p>Tiskárna <b>nejede</b></p><script>alert(1)</script>',
    )

    [entry] = ticket["entries"]
    assert ticket["type"] == "issue"
    assert (ticket["requester_name"], ticket["requester_email"]) == ("Jana", "jana@example.com")
    assert (entry["kind"], entry["minutes"], entry["author_label"]) == ("note", 0, "boss@example.com")
    assert "<script>" not in entry["content_html"] and "Tiskárna" in entry["content_html"]


async def test_an_empty_description_makes_no_entry(client, admin):
    assert (await _ticket(client, admin, description_html="<p></p>"))["entries"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"subject": ""},
        {"subject": "x" * 201},
        {"subject": "x", "type": "urgent"},
        {"subject": "x", "requester_email": "not-an-address"},
    ],
)
async def test_invalid_tickets_are_refused(client, admin, body):
    resp = await client.post(M, json=body, headers=admin)

    assert resp.status_code == 422


async def test_a_partner_can_be_linked_when_the_crm_is_on_and_fills_in_the_requester(client, admin, db_session, crm_on):
    partner = await _partner(db_session, name="Firma s.r.o.", company="Firma", email="info@firma.cz")

    ticket = await _ticket(client, admin, partner_id=str(partner.id))

    assert ticket["partner"] == {"id": str(partner.id), "name": "Firma s.r.o.", "company": "Firma", "archived": False}
    assert (ticket["requester_name"], ticket["requester_email"]) == ("Firma s.r.o.", "info@firma.cz")


async def test_an_explicit_requester_beats_the_partners_details(client, admin, db_session, crm_on):
    partner = await _partner(db_session, email="info@firma.cz")

    ticket = await _ticket(client, admin, partner_id=str(partner.id), requester_name="Petr", requester_email="petr@firma.cz")

    assert (ticket["requester_name"], ticket["requester_email"]) == ("Petr", "petr@firma.cz")


async def test_a_manual_ticket_is_not_linked_to_a_partner_unasked(client, admin, db_session, crm_on):
    await _partner(db_session, email="jana@example.com")

    ticket = await _ticket(client, admin, requester_email="jana@example.com")

    assert ticket["partner"] is None


async def test_linking_a_partner_is_refused_when_the_crm_is_off_or_the_partner_is_unknown(client, admin, db_session, monkeypatch):
    partner = await _partner(db_session)

    off = await client.post(M, json={"subject": "x", "partner_id": str(partner.id)}, headers=admin)
    monkeypatch.setattr(service, "crm_enabled", lambda: True)
    unknown = await client.post(M, json={"subject": "x", "partner_id": str(uuid.uuid4())}, headers=admin)

    assert (off.status_code, off.json()["detail"]) == (422, "crm_disabled")
    assert (unknown.status_code, unknown.json()["detail"]) == (422, "partner_not_found")


# --- Reading ------------------------------------------------------------------


async def test_a_ticket_is_fetched_by_its_number_with_its_thread_in_order_and_total_time(client, admin):
    ticket = await _ticket(client, admin, description_html="<p>Popis</p>")
    number = ticket["number"]
    await _entry(client, admin, number, content_html="<p>Druhý</p>", minutes=30)
    await _entry(client, admin, number, content_html="<p>Třetí</p>", minutes=45)

    detail = (await client.get(f"{M}/{number}", headers=admin)).json()

    assert [e["content_html"] for e in detail["entries"]] == ["<p>Popis</p>", "<p>Druhý</p>", "<p>Třetí</p>"]
    assert detail["total_minutes"] == 75
    assert detail["number"] == number


async def test_an_unknown_ticket_is_404(client, admin):
    resp = await client.get(f"{M}/999999999", headers=admin)

    assert (resp.status_code, resp.json()["detail"]) == (404, "ticket_not_found")


async def test_the_list_is_newest_activity_first_with_totals_and_partner(client, admin, db_session, crm_on):
    partner = await _partner(db_session, name="Firma")
    first = await _ticket(client, admin, subject="První")
    second = await _ticket(client, admin, subject="Druhý", partner_id=str(partner.id))
    await _entry(client, admin, first["number"], minutes=20)
    await _entry(client, admin, first["number"], minutes=10)

    page = (await client.get(M, headers=admin)).json()

    assert page["total"] == 2 and (page["page"], page["page_size"]) == (1, 25)
    assert [t["subject"] for t in page["items"]] == ["První", "Druhý"]
    by_subject = {t["subject"]: t for t in page["items"]}
    assert (by_subject["První"]["total_minutes"], by_subject["První"]["entry_count"]) == (30, 2)
    assert (by_subject["Druhý"]["total_minutes"], by_subject["Druhý"]["entry_count"]) == (0, 0)
    assert by_subject["Druhý"]["partner"]["name"] == "Firma"
    assert second["number"] != first["number"]


async def test_the_list_is_paged(client, admin):
    for i in range(5):
        await _ticket(client, admin, subject=f"T{i}")

    page = (await client.get(M, params={"page": 2, "page_size": 2}, headers=admin)).json()

    assert page["total"] == 5 and len(page["items"]) == 2 and page["page"] == 2
    assert (await client.get(M, params={"page_size": 101}, headers=admin)).status_code == 422
    assert (await client.get(M, params={"page": 0}, headers=admin)).status_code == 422


async def test_the_list_filters_by_status_type_source_and_partner(client, admin, db_session, crm_on):
    partner = await _partner(db_session)
    await _ticket(client, admin, subject="Chyba", type="issue", partner_id=str(partner.id))
    closed = await _ticket(client, admin, subject="Hotovo", type="order")
    await client.patch(f"{M}/{closed['number']}", json={"status": "closed"}, headers=admin)

    async def subjects(**params):
        return [t["subject"] for t in (await client.get(M, params=params, headers=admin)).json()["items"]]

    assert await subjects(status="open") == ["Chyba"]
    assert await subjects(status="closed") == ["Hotovo"]
    assert await subjects(type="order") == ["Hotovo"]
    assert await subjects(source="email") == []
    assert sorted(await subjects(source="manual")) == ["Chyba", "Hotovo"]
    assert await subjects(partner_id=str(partner.id)) == ["Chyba"]


async def test_the_search_matches_subject_requester_and_the_number_in_any_form(client, admin):
    ticket = await _ticket(client, admin, subject="Faktura za říjen", requester_name="Petr Svoboda", requester_email="petr@firma.cz")
    await _ticket(client, admin, subject="Něco jiného")
    number = ticket["number"]

    async def found(q):
        return [t["subject"] for t in (await client.get(M, params={"q": q}, headers=admin)).json()["items"]]

    for q in ("faktura", "SVOBODA", "firma.cz", str(number), f"#{number}", f"Ticket#{number}", f"[Ticket#{number}]".strip("[]")):
        assert await found(q) == ["Faktura za říjen"], q
    assert await found("nic takového") == []
    assert await found("100%") == [] and await found("a_b") == []


# --- Changing and deleting ---------------------------------------------------


async def test_the_header_fields_can_be_changed(client, admin):
    ticket = await _ticket(client, admin, requester_email="a@example.com")

    resp = await client.patch(
        f"{M}/{ticket['number']}",
        json={"subject": "Nový název", "type": "order", "status": "closed", "requester_name": "Karel", "requester_email": None},
        headers=admin,
    )

    body = resp.json()
    assert resp.status_code == 200
    assert (body["subject"], body["type"], body["status"]) == ("Nový název", "order", "closed")
    assert (body["requester_name"], body["requester_email"]) == ("Karel", None)


async def test_a_field_that_is_not_sent_stays_and_a_null_type_changes_nothing(client, admin):
    ticket = await _ticket(client, admin, type="issue", requester_email="a@example.com")

    body = (await client.patch(f"{M}/{ticket['number']}", json={"type": None, "subject": None}, headers=admin)).json()

    assert (body["type"], body["subject"], body["requester_email"]) == ("issue", "Nefunguje tisk", "a@example.com")


async def test_a_partner_can_be_linked_and_unlinked_later(client, admin, db_session, crm_on):
    partner = await _partner(db_session, name="Firma")
    ticket = await _ticket(client, admin)

    linked = (await client.patch(f"{M}/{ticket['number']}", json={"partner_id": str(partner.id)}, headers=admin)).json()
    unlinked = (await client.patch(f"{M}/{ticket['number']}", json={"partner_id": None}, headers=admin)).json()
    refused = await client.patch(f"{M}/{ticket['number']}", json={"partner_id": str(uuid.uuid4())}, headers=admin)

    assert linked["partner"]["name"] == "Firma" and unlinked["partner"] is None
    assert refused.status_code == 422


async def test_deleting_a_ticket_removes_its_thread_and_files(client, admin, db_session, settings):
    ticket = await _ticket(client, admin)
    number = ticket["number"]
    await _entry(client, admin, number)
    image = (await client.post(f"{M}/{number}/images", files=_png_upload(), headers=admin)).json()
    attachment = (await client.post(f"{M}/{number}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()
    stored = [a.stored_name for a in (await db_session.scalars(select(TicketAttachment))).all()]
    assert len(stored) == 2 and all(storage.stored_path(settings, n).exists() for n in stored)

    resp = await client.delete(f"{M}/{number}", headers=admin)

    assert resp.status_code == 204
    assert (await client.get(f"{M}/{number}", headers=admin)).status_code == 404
    assert await db_session.scalar(select(func.count(TicketEntry.id))) == 0
    assert await db_session.scalar(select(func.count(TicketAttachment.id))) == 0
    assert not any(storage.stored_path(settings, n).exists() for n in stored)
    assert image["url"] and attachment["id"]


async def test_deleting_a_partner_only_unlinks_its_tickets(client, admin, db_session, crm_on):
    partner = await _partner(db_session)
    ticket = await _ticket(client, admin, partner_id=str(partner.id))

    await db_session.execute(delete(Partner))
    await db_session.commit()

    assert (await client.get(f"{M}/{ticket['number']}", headers=admin)).json()["partner"] is None


# --- Entries ------------------------------------------------------------------


async def test_a_note_carries_its_time_and_author_and_is_sanitized(client, admin):
    ticket = await _ticket(client, admin)

    entry = await _entry(
        client, admin, ticket["number"], content_html='<p onclick="x()">Zjištěno</p><iframe src="http://evil.example"></iframe>', minutes=90
    )

    assert (entry["kind"], entry["minutes"], entry["author_label"]) == ("note", 90, "boss@example.com")
    assert entry["content_html"] == "<p>Zjištěno</p>"
    assert (entry["to_address"], entry["email_subject"]) == (None, None)


async def test_a_note_may_be_only_time(client, admin):
    ticket = await _ticket(client, admin)

    entry = await _entry(client, admin, ticket["number"], content_html="", minutes=15)

    assert entry["minutes"] == 15


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "note", "content_html": "<p></p>"},
        {"kind": "note", "content_html": ""},
        {"kind": "outgoing", "content_html": "<p></p>", "minutes": 10},
    ],
)
async def test_an_entry_with_nothing_in_it_is_refused(client, admin, body):
    ticket = await _ticket(client, admin, requester_email="a@example.com")

    resp = await client.post(f"{M}/{ticket['number']}/entries", json=body, headers=admin)

    assert (resp.status_code, resp.json()["detail"]) == (422, "empty_entry")


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "note", "content_html": "x", "minutes": -1},
        {"kind": "note", "content_html": "x", "minutes": 7 * 24 * 60 + 1},
        {"kind": "incoming", "content_html": "x"},
        {"kind": "note", "content_html": "x" * 200_001},
        {"kind": "note", "content_html": "x", "attachment_ids": [str(uuid.uuid4())] * 11},
    ],
)
async def test_invalid_entries_are_refused_by_the_schema(client, admin, body):
    ticket = await _ticket(client, admin)

    assert (await client.post(f"{M}/{ticket['number']}/entries", json=body, headers=admin)).status_code == 422


async def test_a_mail_to_the_requester_is_sent_tagged_and_recorded(client, admin, settings):
    ticket = await _ticket(client, admin, subject="Dotaz na cenu", requester_name="Jana", requester_email="jana@example.com")
    attachment = (await client.post(f"{M}/{ticket['number']}/attachments", files={"file": ("nabídka.pdf", PDF, "application/pdf")}, headers=admin)).json()

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        resp = await client.post(
            f"{M}/{ticket['number']}/entries",
            json={"kind": "outgoing", "content_html": "<p>Dobrý den, <b>cena</b> je 100 Kč.</p>", "minutes": 20, "attachment_ids": [attachment["id"]]},
            headers=admin,
        )

    entry = resp.json()
    assert resp.status_code == 201
    assert (entry["kind"], entry["minutes"], entry["to_address"]) == ("outgoing", 20, "jana@example.com")
    assert entry["email_subject"] == f"[Ticket#{ticket['number']}] - Dotaz na cenu"
    assert [a["original_filename"] for a in entry["attachments"]] == ["nabídka.pdf"]
    [message] = outbox
    assert str(make_header(decode_header(message["Subject"]))) == entry["email_subject"]
    assert "jana@example.com" in str(message["To"]) and "tickets@example.com" in str(message["Reply-To"])
    assert any(p.get_content_type() == "application/pdf" for p in message.walk())
    detail = (await client.get(f"{M}/{ticket['number']}", headers=admin)).json()
    assert [a["original_filename"] for a in detail["entries"][-1]["attachments"]] == ["nabídka.pdf"]


async def test_a_mail_cannot_be_sent_to_a_ticket_without_an_address(client, admin):
    ticket = await _ticket(client, admin)

    resp = await client.post(f"{M}/{ticket['number']}/entries", json={"kind": "outgoing", "content_html": "<p>x</p>"}, headers=admin)

    assert (resp.status_code, resp.json()["detail"]) == (422, "no_requester_email")


async def test_a_mail_that_cannot_be_sent_saves_nothing_and_keeps_the_file_for_another_try(client, admin, db_session, monkeypatch):
    ticket = await _ticket(client, admin, requester_email="jana@example.com")
    attachment = (await client.post(f"{M}/{ticket['number']}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()

    async def broken(*args, **kwargs):
        raise ConnectionError("smtp down")

    monkeypatch.setattr(service, "send_email", broken)

    resp = await client.post(
        f"{M}/{ticket['number']}/entries",
        json={"kind": "outgoing", "content_html": "<p>x</p>", "minutes": 5, "attachment_ids": [attachment["id"]]},
        headers=admin,
    )

    assert (resp.status_code, resp.json()["detail"]) == (502, "email_failed")
    detail = (await client.get(f"{M}/{ticket['number']}", headers=admin)).json()
    assert detail["entries"] == [] and detail["total_minutes"] == 0
    row = await db_session.get(TicketAttachment, uuid.UUID(attachment["id"]))
    assert row is not None and row.entry_id is None


async def test_files_must_belong_to_the_ticket_and_be_unused(client, admin):
    first = await _ticket(client, admin)
    second = await _ticket(client, admin)
    mine = (await client.post(f"{M}/{first['number']}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()

    foreign = await client.post(f"{M}/{second['number']}/entries", json={"kind": "note", "content_html": "x", "attachment_ids": [mine["id"]]}, headers=admin)
    unknown = await client.post(f"{M}/{first['number']}/entries", json={"kind": "note", "content_html": "x", "attachment_ids": [str(uuid.uuid4())]}, headers=admin)
    used = await client.post(f"{M}/{first['number']}/entries", json={"kind": "note", "content_html": "x", "attachment_ids": [mine["id"]]}, headers=admin)
    again = await client.post(f"{M}/{first['number']}/entries", json={"kind": "note", "content_html": "y", "attachment_ids": [mine["id"]]}, headers=admin)

    assert [r.status_code for r in (foreign, unknown, used, again)] == [422, 422, 201, 422]
    assert foreign.json()["detail"] == "attachment_invalid"


async def test_a_file_only_note_is_enough(client, admin):
    ticket = await _ticket(client, admin)
    item = (await client.post(f"{M}/{ticket['number']}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()

    entry = await _entry(client, admin, ticket["number"], content_html="", attachment_ids=[item["id"]])

    assert [a["id"] for a in entry["attachments"]] == [item["id"]]


async def test_a_note_can_be_corrected_and_its_time_changed(client, admin):
    ticket = await _ticket(client, admin)
    entry = await _entry(client, admin, ticket["number"], minutes=10)

    resp = await client.patch(
        f"{M}/{ticket['number']}/entries/{entry['id']}",
        json={"content_html": "<p>Opraveno <script>x</script></p>", "minutes": 25},
        headers=admin,
    )

    assert resp.status_code == 200
    assert (resp.json()["content_html"], resp.json()["minutes"]) == ("<p>Opraveno </p>", 25)
    assert (await client.get(f"{M}/{ticket['number']}", headers=admin)).json()["total_minutes"] == 25


async def test_a_mail_keeps_its_text_but_its_time_can_be_changed(client, admin, db_session):
    ticket = await _ticket(client, admin, requester_email="a@example.com")
    entry = await client.post(f"{M}/{ticket['number']}/entries", json={"kind": "outgoing", "content_html": "<p>x</p>"}, headers=admin)
    entry_id = entry.json()["id"]

    text = await client.patch(f"{M}/{ticket['number']}/entries/{entry_id}", json={"content_html": "<p>jiné</p>"}, headers=admin)
    time = await client.patch(f"{M}/{ticket['number']}/entries/{entry_id}", json={"minutes": 7}, headers=admin)

    assert (text.status_code, text.json()["detail"]) == (422, "entry_not_editable")
    assert (time.status_code, time.json()["minutes"], time.json()["content_html"]) == (200, 7, "<p>x</p>")


async def test_an_entry_of_another_ticket_is_404(client, admin):
    first = await _ticket(client, admin)
    second = await _ticket(client, admin)
    entry = await _entry(client, admin, first["number"])

    patch = await client.patch(f"{M}/{second['number']}/entries/{entry['id']}", json={"minutes": 1}, headers=admin)
    delete_ = await client.delete(f"{M}/{second['number']}/entries/{entry['id']}", headers=admin)
    unknown = await client.patch(f"{M}/{first['number']}/entries/{uuid.uuid4()}", json={"minutes": 1}, headers=admin)

    assert [r.status_code for r in (patch, delete_, unknown)] == [404, 404, 404]


async def test_a_note_can_be_deleted_with_its_files_but_a_mail_cannot(client, admin, db_session, settings):
    ticket = await _ticket(client, admin, requester_email="a@example.com")
    number = ticket["number"]
    item = (await client.post(f"{M}/{number}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()
    note = await _entry(client, admin, number, attachment_ids=[item["id"]])
    mail = (await client.post(f"{M}/{number}/entries", json={"kind": "outgoing", "content_html": "<p>x</p>"}, headers=admin)).json()
    stored = (await db_session.scalar(select(TicketAttachment.stored_name)))

    refused = await client.delete(f"{M}/{number}/entries/{mail['id']}", headers=admin)
    deleted = await client.delete(f"{M}/{number}/entries/{note['id']}", headers=admin)

    assert (refused.status_code, refused.json()["detail"]) == (422, "entry_not_editable")
    assert deleted.status_code == 204
    assert [e["id"] for e in (await client.get(f"{M}/{number}", headers=admin)).json()["entries"]] == [mail["id"]]
    assert not storage.stored_path(settings, stored).exists()


# --- Files --------------------------------------------------------------------


async def test_a_picture_is_stored_and_answered_with_a_public_address(client, admin, db_session, settings):
    ticket = await _ticket(client, admin)

    resp = await client.post(f"{M}/{ticket['number']}/images", files=_png_upload(), headers=admin)

    url = resp.json()["url"]
    name = url.rsplit("/", 1)[1]
    assert resp.status_code == 201
    assert url == f"http://app.test/api/modules/tickets/files/{name}"
    assert name.endswith(".png") and len(name) == 36
    [row] = (await db_session.scalars(select(TicketAttachment))).all()
    assert (row.is_inline, row.entry_id, row.stored_name, row.content_type) == (True, None, name, "image/png")
    assert storage.stored_path(settings, name).read_bytes() == PNG


@pytest.mark.parametrize(
    "files, status",
    [
        ({"file": ("a.svg", b"<svg/>", "image/svg+xml")}, 415),
        ({"file": ("a.png", b"GIF89a....", "image/png")}, 415),
        ({"file": ("a.png", b"", "image/png")}, 422),
    ],
)
async def test_only_real_pictures_are_accepted_as_pictures(client, admin, files, status):
    ticket = await _ticket(client, admin)

    assert (await client.post(f"{M}/{ticket['number']}/images", files=files, headers=admin)).status_code == status


async def test_an_oversized_picture_or_file_is_refused(client, admin, monkeypatch):
    ticket = await _ticket(client, admin)
    monkeypatch.setattr(storage, "MAX_IMAGE_BYTES", 10)
    monkeypatch.setattr(storage, "MAX_ATTACHMENT_BYTES", 10)

    image = await client.post(f"{M}/{ticket['number']}/images", files=_png_upload(), headers=admin)
    file = await client.post(f"{M}/{ticket['number']}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)

    assert (image.status_code, file.status_code) == (413, 413)


async def test_a_file_is_private_and_comes_back_only_as_a_download(client, admin, settings):
    ticket = await _ticket(client, admin)
    resp = await client.post(
        f"{M}/{ticket['number']}/attachments", files={"file": ("../../etc/Faktura č.1.pdf", PDF, "application/pdf")}, headers=admin
    )
    item = resp.json()

    download = await client.get(f"{M}/attachments/{item['id']}/file", headers=admin)

    assert resp.status_code == 201
    assert (item["original_filename"], item["content_type"], item["size_bytes"], item["is_inline"]) == ("Faktura č.1.pdf", "application/pdf", len(PDF), False)
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"].startswith("attachment")
    assert download.headers["x-content-type-options"] == "nosniff" and "no-store" in download.headers["cache-control"]
    assert (await client.get(f"{M}/attachments/{uuid.uuid4()}/file", headers=admin)).status_code == 404


async def test_a_file_that_vanished_from_disk_is_404(client, admin, settings, db_session):
    ticket = await _ticket(client, admin)
    item = (await client.post(f"{M}/{ticket['number']}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()
    stored = await db_session.scalar(select(TicketAttachment.stored_name))
    storage.stored_path(settings, stored).unlink()

    resp = await client.get(f"{M}/attachments/{item['id']}/file", headers=admin)

    assert (resp.status_code, resp.json()["detail"]) == (404, "attachment_missing")


async def test_an_unused_file_can_be_taken_back_but_a_used_one_cannot(client, admin, settings, db_session):
    ticket = await _ticket(client, admin)
    number = ticket["number"]
    spare = (await client.post(f"{M}/{number}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()
    used = (await client.post(f"{M}/{number}/attachments", files={"file": ("b.pdf", PDF, "application/pdf")}, headers=admin)).json()
    await _entry(client, admin, number, attachment_ids=[used["id"]])
    image = (await client.post(f"{M}/{number}/images", files=_png_upload(), headers=admin)).json()
    spare_stored = await db_session.scalar(select(TicketAttachment.stored_name).where(TicketAttachment.id == uuid.UUID(spare["id"])))
    image_id = await db_session.scalar(select(TicketAttachment.id).where(TicketAttachment.is_inline.is_(True)))

    taken = await client.delete(f"{M}/{number}/attachments/{spare['id']}", headers=admin)
    in_use = await client.delete(f"{M}/{number}/attachments/{used['id']}", headers=admin)
    picture = await client.delete(f"{M}/{number}/attachments/{image_id}", headers=admin)
    gone = await client.delete(f"{M}/{number}/attachments/{spare['id']}", headers=admin)

    assert [r.status_code for r in (taken, in_use, picture, gone)] == [204, 409, 409, 404]
    assert not storage.stored_path(settings, spare_stored).exists()
    assert image["url"]


async def test_files_of_a_missing_ticket_are_refused(client, admin):
    assert (await client.post(f"{M}/999999999/images", files=_png_upload(), headers=admin)).status_code == 404
    assert (await client.post(f"{M}/999999999/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).status_code == 404


# --- The public picture address ---------------------------------------------------


async def test_a_picture_is_served_without_signing_in(client, admin):
    ticket = await _ticket(client, admin)
    name = (await client.post(f"{M}/{ticket['number']}/images", files=_png_upload(), headers=admin)).json()["url"].rsplit("/", 1)[1]

    resp = await client.get(f"{BASE}/files/{name}")

    assert resp.status_code == 200 and resp.content == PNG
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"].startswith("private")


async def test_the_public_address_never_serves_a_private_file_or_a_made_up_name(client, admin, settings):
    ticket = await _ticket(client, admin)
    item = (await client.post(f"{M}/{ticket['number']}/attachments", files={"file": ("a.pdf", PDF, "application/pdf")}, headers=admin)).json()
    private = (storage.uploads_dir(settings)).glob("*.bin").__next__().name

    for name in (private, private.replace(".bin", ".png"), "x.png", "../x.png", "..%2Fx.png", "a" * 32 + ".png", "a" * 32 + ".svg", "a" * 32):
        assert (await client.get(f"{BASE}/files/{name}")).status_code == 404, name
    assert item["id"]


# --- The mailbox -----------------------------------------------------------------


async def test_the_mailbox_status_says_what_is_set_up_and_never_the_secrets(client, admin):
    resp = await client.get(f"{M}/mailbox", headers=admin)

    body = resp.json()
    assert resp.status_code == 200
    assert (body["configured"], body["address"], body["poll_seconds"]) == (True, "tickets@example.com", 120)
    assert (body["last_checked_at"], body["last_error"], body["last_result"]) == (None, None, None)
    assert "imap-secret" not in resp.text and "imap.example.com" not in resp.text


async def test_the_mailbox_status_when_nothing_is_configured(client, admin, tmp_path):
    _app.dependency_overrides[get_settings] = lambda: tickets_settings(tmp_path, tickets_imap_host="")

    body = (await client.get(f"{M}/mailbox", headers=admin)).json()

    assert (body["configured"], body["address"]) == (False, None)


async def test_checking_the_mailbox_now_files_the_mail_and_reports_it(client, admin, db_session, monkeypatch):
    class Box:
        folder = "INBOX"

        def __init__(self, settings):
            self.done = []

        async def open(self):
            pass

        async def unseen(self):
            return [b"1"]

        async def fetch(self, uid):
            return make_mail(subject="Z pošty", message_id="<router@x>")

        async def mark_seen(self, uid):
            self.done.append(uid)

        async def mark_failed(self, uid):
            raise AssertionError

        async def close(self):
            pass

    async def same_session():
        return None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr(mailbox, "ImapMailbox", Box)
    monkeypatch.setattr(mailbox, "_default_session", factory)

    resp = await client.post(f"{M}/mailbox/poll", headers=admin)

    assert resp.status_code == 200
    assert (resp.json()["fetched"], resp.json()["created"]) == (1, 1)
    status = (await client.get(f"{M}/mailbox", headers=admin)).json()
    assert status["last_result"]["created"] == 1 and status["last_checked_at"] is not None
    assert (await db_session.scalar(select(Ticket.subject))) == "Z pošty"


async def test_checking_a_mailbox_that_is_not_configured_is_a_conflict(client, admin, tmp_path):
    _app.dependency_overrides[get_settings] = lambda: tickets_settings(tmp_path, tickets_imap_host="")

    resp = await client.post(f"{M}/mailbox/poll", headers=admin)

    assert (resp.status_code, resp.json()["detail"]) == (409, "mailbox_not_configured")


async def test_a_mailbox_that_cannot_be_reached_is_a_bad_gateway_with_the_cause_in_the_status(client, admin, db_session, monkeypatch):
    from contextlib import asynccontextmanager

    class Down:
        folder = "INBOX"

        def __init__(self, settings):
            pass

        async def open(self):
            raise OSError("connection refused")

        async def close(self):
            pass

    @asynccontextmanager
    async def factory():
        yield db_session

    monkeypatch.setattr(mailbox, "ImapMailbox", Down)
    monkeypatch.setattr(mailbox, "_default_session", factory)

    resp = await client.post(f"{M}/mailbox/poll", headers=admin)

    assert (resp.status_code, resp.json()["detail"]) == (502, "mailbox_error")
    assert "connection refused" in (await client.get(f"{M}/mailbox", headers=admin)).json()["last_error"]
