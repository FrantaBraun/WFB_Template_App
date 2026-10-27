# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.modules.tickets.service: numbering and tagging, the contact
form hook, filing a received mail, and the mail we send. Everything runs in
db_session's rolled-back transaction, so it never leaves rows behind."""

from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path

import pytest
from fastapi_mail import FastMail
from sqlalchemy import delete, func, select

from app.modules.crm.models import Partner
from app.modules.kontaktni_formular.hooks import ContactSubmission
from app.modules.tickets import service, storage
from app.modules.tickets.mailparse import parse_message
from app.modules.tickets.models import Ticket, TicketAttachment, TicketEntry
from app.services.email import _connection_config
from tests.tickets_support import PDF, PNG, make_mail, tickets_settings


@pytest.fixture(autouse=True)
async def _clean(db_session):
    await db_session.execute(delete(Ticket))
    await db_session.execute(delete(Partner))


@pytest.fixture()
def settings(tmp_path):
    return tickets_settings(tmp_path)


@pytest.fixture()
def crm_on(monkeypatch):
    monkeypatch.setattr(service, "crm_enabled", lambda: True)


@pytest.fixture(autouse=True)
def _crm_off_by_default(monkeypatch):
    """Which modules a branch has switched on must not decide these tests."""
    monkeypatch.setattr(service, "crm_enabled", lambda: False)


async def _entries(db, ticket) -> list[TicketEntry]:
    return list(
        (await db.scalars(select(TicketEntry).where(TicketEntry.ticket_id == ticket.id).order_by(TicketEntry.seq))).all()
    )


async def _partner(db, **fields) -> Partner:
    partner = Partner(name=fields.pop("name", "Jana Nováková"), **fields)
    db.add(partner)
    await db.flush()
    return partner


# --- Numbers and subjects ------------------------------------------------------


def test_the_tag_is_what_the_subject_is_matched_by():
    assert service.subject_tag(100253) == "[Ticket#100253]"
    assert service.find_ticket_number("[Ticket#100253] - Dotaz") == 100253
    assert service.find_ticket_number("Re: [Ticket#100253] - Dotaz") == 100253
    assert service.find_ticket_number("RE: [ticket # 7 ] Dotaz") == 7
    assert service.find_ticket_number("Odp: Fwd: [Ticket#42]") == 42


@pytest.mark.parametrize("subject", ["Dotaz", "", "[Ticket#] x", "[Ticket#abc]", "Ticket#100253", "[Ticket 100253]"])
def test_a_subject_without_a_proper_tag_names_no_ticket(subject):
    assert service.find_ticket_number(subject) is None


def test_stripping_removes_the_tag_and_the_dash_after_it():
    assert service.strip_ticket_tag("[Ticket#100253] - Dotaz na cenu") == "Dotaz na cenu"
    assert service.strip_ticket_tag("Re: [Ticket#1]   Dotaz") == "Re: Dotaz"
    assert service.strip_ticket_tag("Dotaz") == "Dotaz"
    assert service.strip_ticket_tag("[Ticket#1] - [Ticket#2] - x") == "x"


def test_outgoing_subject_puts_the_number_in_front_of_the_title():
    assert service.outgoing_subject(Ticket(number=100253, subject="Dotaz")) == "[Ticket#100253] - Dotaz"


def test_plain_text_becomes_escaped_paragraphs():
    assert service.plain_to_html("Ahoj <b>\nsvěte\n\nDruhý & odstavec") == (
        "<p>Ahoj &lt;b&gt;<br>světe</p><p>Druhý &amp; odstavec</p>"
    )
    assert service.plain_to_html("") == ""


@pytest.mark.parametrize(
    "content, expected",
    [
        ("<p></p>", False),
        ("<p>&nbsp;</p>", False),
        ("", False),
        ("<p>Ahoj</p>", True),
        ('<p><img src="http://x/y.png"></p>', True),
    ],
)
def test_has_content_sees_text_or_a_picture(content, expected):
    assert service.has_content(content) is expected


# --- The mailbox's own address -------------------------------------------------


def test_mailbox_address_prefers_the_explicit_setting_then_the_imap_user(tmp_path):
    assert service.mailbox_address(tickets_settings(tmp_path, tickets_mailbox_address=" help@example.com ")) == "help@example.com"
    assert service.mailbox_address(tickets_settings(tmp_path)) == "tickets@example.com"
    assert service.mailbox_address(tickets_settings(tmp_path, tickets_imap_username="plainlogin")) == "noreply@example.com"


def test_without_a_mailbox_there_is_no_reply_to_address(tmp_path):
    assert service.mailbox_address(tickets_settings(tmp_path, tickets_imap_host="")) is None
    explicit = tickets_settings(tmp_path, tickets_imap_host="", tickets_mailbox_address="help@example.com")
    assert service.mailbox_address(explicit) == "help@example.com"


def test_our_own_addresses_are_recognised(settings):
    assert service.is_own_address("Noreply@Example.com", settings)
    assert service.is_own_address("tickets@example.com", settings)
    assert not service.is_own_address("jana@example.com", settings)
    assert not service.is_own_address("", settings)


# --- Creating tickets ---------------------------------------------------------


async def test_numbers_start_at_100001_and_only_grow(db_session):
    first = await service.create_ticket(db_session, subject="A", source="manual")
    second = await service.create_ticket(db_session, subject="B", source="manual")

    assert first.number >= 100001
    assert second.number > first.number
    assert (first.type, first.status) == ("general", "open")


async def test_the_subject_is_cleaned_and_limited(db_session):
    ticket = await service.create_ticket(db_session, subject="  " + "x" * 300, source="manual")
    blank = await service.create_ticket(db_session, subject="   ", source="manual")

    assert len(ticket.subject) == 200
    assert blank.subject == "-"


async def test_a_partner_is_looked_up_by_the_requesters_address_when_the_crm_is_on(db_session, crm_on):
    partner = await _partner(db_session, email="Jana@Example.com")

    ticket = await service.create_ticket(db_session, subject="A", source="email", requester_email="jana@example.com")
    stranger = await service.create_ticket(db_session, subject="B", source="email", requester_email="x@example.com")

    assert ticket.partner_id == partner.id
    assert stranger.partner_id is None


async def test_no_partner_is_looked_up_when_the_crm_is_off(db_session):
    await _partner(db_session, email="jana@example.com")

    ticket = await service.create_ticket(db_session, subject="A", source="email", requester_email="jana@example.com")

    assert ticket.partner_id is None


async def test_an_active_partner_beats_an_archived_one_and_the_oldest_wins(db_session, crm_on):
    archived = await _partner(db_session, name="Old", email="jana@example.com", archived=True)
    first = await _partner(db_session, name="First", email="jana@example.com")
    first.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    second = await _partner(db_session, name="Second", email="jana@example.com")
    second.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.flush()

    found = await service.find_partner_by_email(db_session, " JANA@example.com ")

    assert found.id == first.id
    assert archived.id != found.id


async def test_an_explicit_partner_is_kept_and_lookup_can_be_switched_off(db_session, crm_on):
    chosen = await _partner(db_session, name="Chosen")
    other = await _partner(db_session, name="Other", email="jana@example.com")

    linked = await service.create_ticket(
        db_session, subject="A", source="manual", requester_email="jana@example.com", partner_id=chosen.id
    )
    unlinked = await service.create_ticket(
        db_session, subject="B", source="manual", requester_email="jana@example.com", lookup_partner=False
    )

    assert linked.partner_id == chosen.id
    assert unlinked.partner_id is None
    assert other.id != chosen.id


async def test_adding_an_entry_marks_the_ticket_active(db_session):
    ticket = await service.create_ticket(db_session, subject="A", source="manual")
    ticket.last_activity_at = datetime(2020, 1, 1, tzinfo=timezone.utc)

    service.add_entry(db_session, ticket, kind="note", content_html="<p>x</p>")

    assert ticket.last_activity_at > datetime(2025, 1, 1, tzinfo=timezone.utc)


# --- The contact form hook ----------------------------------------------------


async def test_a_contact_form_message_becomes_a_ticket_and_is_tagged(db_session, settings, monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    result = await service.contact_form_hook(
        db_session,
        ContactSubmission(
            subject="Dotaz na cenu",
            message="Dobrý den,\n\nkolik to stojí? <script>x</script>",
            sender_name="host@example.com",
            reply_to="host@example.com",
            language="cs",
            signed_in=False,
        ),
    )

    ticket = await db_session.scalar(select(Ticket))
    [entry] = await _entries(db_session, ticket)
    assert result.subject_tag == f"[Ticket#{ticket.number}]"
    assert result.reply_to == "tickets@example.com"
    assert (ticket.source, ticket.type, ticket.status) == ("contact_form", "general", "open")
    assert ticket.subject == "Dotaz na cenu"
    assert (ticket.requester_name, ticket.requester_email) == (None, "host@example.com")
    assert entry.kind == "incoming"
    assert "<p>Dobrý den,</p>" in entry.content_html and "<script>" not in entry.content_html
    assert (entry.from_address, entry.from_name, entry.email_subject) == ("host@example.com", None, "Dotaz na cenu")


async def test_a_signed_in_sender_is_the_requester_by_name(db_session, settings, monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    await service.contact_form_hook(
        db_session,
        ContactSubmission("Dotaz", "Ahoj", "Jana Nováková", "jana@example.com", "cs", True),
    )

    ticket = await db_session.scalar(select(Ticket))
    assert (ticket.requester_name, ticket.requester_email) == ("Jana Nováková", "jana@example.com")


async def test_a_contact_form_ticket_is_linked_to_the_partner_with_that_address(db_session, settings, monkeypatch, crm_on):
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    partner = await _partner(db_session, email="host@example.com")

    await service.contact_form_hook(
        db_session, ContactSubmission("Dotaz", "Ahoj", "host@example.com", "host@example.com", None, False)
    )

    assert (await db_session.scalar(select(Ticket))).partner_id == partner.id


# --- Filing a received mail ---------------------------------------------------


async def _import(db, settings, **mail_args):
    return await service.import_message(db, parse_message(make_mail(**mail_args)), settings)


async def test_a_new_mail_opens_a_ticket(db_session, settings):
    outcome = await _import(db_session, settings, subject="Dotaz na cenu", message_id="<m1@x>")

    ticket = outcome.ticket
    [entry] = await _entries(db_session, ticket)
    assert outcome.created is True
    assert (ticket.source, ticket.status, ticket.type) == ("email", "open", "general")
    assert ticket.subject == "Dotaz na cenu"
    assert (ticket.requester_name, ticket.requester_email) == ("Jana Nováková", "jana@example.com")
    assert (entry.kind, entry.message_id, entry.from_address) == ("incoming", "<m1@x>", "jana@example.com")
    assert entry.created_at == datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
    assert "<p>Dobrý den,</p>" in entry.content_html


async def test_the_partner_with_the_senders_address_is_linked_or_none(db_session, settings, crm_on):
    partner = await _partner(db_session, email="jana@example.com")

    known = await _import(db_session, settings, message_id="<a@x>")
    unknown = await _import(db_session, settings, sender="x@example.com", message_id="<b@x>")

    assert known.ticket.partner_id == partner.id
    assert unknown.ticket.partner_id is None
    assert unknown.created is True


async def test_a_mail_naming_a_ticket_is_filed_there_not_as_a_new_one(db_session, settings):
    first = await _import(db_session, settings, subject="Dotaz", message_id="<a@x>")
    number = first.ticket.number

    reply = await _import(db_session, settings, subject=f"Re: [Ticket#{number}] - Dotaz", text="Odpověď", message_id="<b@x>")

    assert reply.created is False
    assert reply.ticket.id == first.ticket.id
    assert await db_session.scalar(select(func.count(Ticket.id))) == 1
    assert [e.kind for e in await _entries(db_session, first.ticket)] == ["incoming", "incoming"]


async def test_a_reply_reopens_a_closed_ticket(db_session, settings):
    first = await _import(db_session, settings, message_id="<a@x>")
    first.ticket.status = "closed"

    await _import(db_session, settings, subject=f"Re: [Ticket#{first.ticket.number}]", message_id="<b@x>")

    assert first.ticket.status == "open"


async def test_the_same_mail_is_filed_once(db_session, settings):
    await _import(db_session, settings, message_id="<same@x>")

    again = await _import(db_session, settings, message_id="<same@x>")

    assert again.skipped == "already imported" and again.ticket is None
    assert await db_session.scalar(select(func.count(TicketEntry.id))) == 1


async def test_mail_from_our_own_addresses_is_never_filed(db_session, settings):
    for sender in ("noreply@example.com", "Tickets <tickets@example.com>"):
        outcome = await _import(db_session, settings, sender=sender, message_id=f"<{sender}@x>")
        assert outcome.skipped == "own address"

    assert await db_session.scalar(select(func.count(Ticket.id))) == 0


async def test_an_automatic_mail_never_starts_a_ticket_but_may_join_one(db_session, settings):
    auto = {"Auto-Submitted": "auto-replied"}
    refused = await _import(db_session, settings, subject="Out of office", headers=auto, message_id="<a@x>")
    first = await _import(db_session, settings, message_id="<b@x>")

    joined = await _import(
        db_session, settings, subject=f"Automatic reply: [Ticket#{first.ticket.number}] - Dotaz", headers=auto, message_id="<c@x>"
    )

    assert refused.skipped == "automatic mail"
    assert joined.ticket.id == first.ticket.id and joined.created is False


async def test_a_number_nobody_has_starts_a_new_ticket_without_the_tag(db_session, settings):
    outcome = await _import(db_session, settings, subject="Re: [Ticket#999999999] - Dotaz", message_id="<a@x>")

    assert outcome.created is True
    assert outcome.ticket.subject == "Re: Dotaz"


async def test_a_mail_without_a_subject_gets_a_placeholder_title(db_session, settings):
    outcome = await _import(db_session, settings, subject="", message_id="<a@x>")

    assert outcome.ticket.subject == "(no subject)"


async def test_html_mail_is_sanitized_and_its_divs_keep_their_lines(db_session, settings):
    html = (
        "<html><head><title>Secret</title><style>p{}</style></head><body>"
        '<div>První řádek</div><div>Druhý <a href="javascript:alert(1)">odkaz</a></div>'
        '<script>alert(1)</script><img src="http://evil.example/x.png" onerror="x()"></body></html>'
    )

    outcome = await _import(db_session, settings, text="fallback", html=html, message_id="<a@x>")

    [entry] = await _entries(db_session, outcome.ticket)
    content = entry.content_html
    assert "<p>První řádek</p>" in content and "<p>Druhý" in content
    assert "Secret" not in content and "alert" not in content and "onerror" not in content
    assert "javascript:" not in content


async def test_an_html_part_with_no_text_falls_back_to_the_plain_part(db_session, settings):
    outcome = await _import(db_session, settings, text="Jen text", html="<html><head></head><body></body></html>", message_id="<a@x>")

    [entry] = await _entries(db_session, outcome.ticket)
    assert "Jen text" in entry.content_html


async def test_files_of_a_mail_are_stored_privately_and_linked_to_its_entry(db_session, settings):
    outcome = await _import(
        db_session, settings, attachments=[("faktura č.1.pdf", "application/pdf", PDF)], message_id="<a@x>"
    )

    [item] = (await db_session.scalars(select(TicketAttachment))).all()
    assert item.entry_id == outcome.entry.id and item.ticket_id == outcome.ticket.id
    assert (item.original_filename, item.content_type, item.size_bytes, item.is_inline) == (
        "faktura č.1.pdf",
        "application/pdf",
        len(PDF),
        False,
    )
    assert item.stored_name.endswith(".bin") and storage.image_media_type(item.stored_name) is None
    assert storage.stored_path(settings, item.stored_name).read_bytes() == PDF
    assert outcome.files == [item.stored_name]


async def test_an_inline_picture_is_stored_publicly_and_the_html_points_at_it(db_session, settings):
    outcome = await _import(
        db_session,
        settings,
        html='<p>Logo <img src="cid:Logo123"></p>',
        inline_images=[("Logo123", "image/png", PNG)],
        message_id="<a@x>",
    )

    [item] = (await db_session.scalars(select(TicketAttachment))).all()
    url = f"http://app.test/api/modules/tickets/files/{item.stored_name}"
    assert item.is_inline is True and item.entry_id is None
    assert item.stored_name.endswith(".png") and storage.image_media_type(item.stored_name) == "image/png"
    assert url in outcome.entry.content_html and "cid:" not in outcome.entry.content_html


async def test_a_picture_the_text_never_shows_is_an_ordinary_attachment(db_session, settings):
    outcome = await _import(
        db_session, settings, html="<p>No picture here</p>", inline_images=[("x1", "image/png", PNG)], message_id="<a@x>"
    )

    [item] = (await db_session.scalars(select(TicketAttachment))).all()
    assert item.is_inline is False and item.entry_id == outcome.entry.id and item.stored_name.endswith(".bin")


async def test_a_picture_that_is_not_one_is_not_shown_inline(db_session, settings):
    await _import(
        db_session,
        settings,
        html='<p><img src="cid:x1"></p>',
        inline_images=[("x1", "image/png", b"<?php echo 1; ?>")],
        message_id="<a@x>",
    )

    [item] = (await db_session.scalars(select(TicketAttachment))).all()
    assert item.is_inline is False and item.stored_name.endswith(".bin")


async def test_an_oversized_file_is_left_out(db_session, settings, monkeypatch):
    monkeypatch.setattr(storage, "MAX_ATTACHMENT_BYTES", 10)

    await _import(db_session, settings, attachments=[("big.pdf", "application/pdf", PDF)], message_id="<a@x>")

    assert await db_session.scalar(select(func.count(TicketAttachment.id))) == 0
    assert not list(Path(settings.uploads_dir, "tickets").glob("*"))


async def test_a_failed_import_leaves_no_file_behind(db_session, settings, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_mail_html", boom)

    with pytest.raises(RuntimeError):
        await _import(db_session, settings, attachments=[("a.pdf", "application/pdf", PDF)], message_id="<a@x>")

    assert not list(Path(settings.uploads_dir, "tickets").glob("*"))


# --- Sending ------------------------------------------------------------------


def _subject(message) -> str:
    return str(make_header(decode_header(message["Subject"])))


async def test_the_mail_to_the_requester_carries_the_number_the_mailbox_and_the_files(db_session, settings):
    ticket = await service.create_ticket(
        db_session, subject="Dotaz", source="manual", requester_email="jana@example.com"
    )
    stored = storage.save_bytes(settings, PDF, storage.PRIVATE_EXTENSION)
    item = TicketAttachment(
        ticket_id=ticket.id,
        original_filename="nabídka.pdf",
        stored_name=stored,
        content_type="application/pdf",
        size_bytes=len(PDF),
    )

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        await service.send_to_requester(settings, ticket, "<p>Dobrý den</p>", [item])

    [message] = outbox
    assert _subject(message) == f"[Ticket#{ticket.number}] - Dotaz"
    assert "jana@example.com" in str(message["To"])
    assert "tickets@example.com" in str(message["Reply-To"])
    assert message.get_content_type() == "multipart/mixed"
    parts = list(message.walk())
    assert any(p.get_content_type() == "text/html" and "Dobrý den" in p.get_payload(decode=True).decode() for p in parts)
    pdf = next(p for p in parts if p.get_content_type() == "application/pdf")
    assert pdf.get_payload(decode=True) == PDF
    assert pdf.get_filename() == "nabídka.pdf"


async def test_without_a_mailbox_the_mail_has_no_reply_to(db_session, tmp_path):
    settings = tickets_settings(tmp_path, tickets_imap_host="")
    ticket = await service.create_ticket(db_session, subject="Dotaz", source="manual", requester_email="jana@example.com")

    mail = FastMail(_connection_config(settings))
    with mail.record_messages() as outbox:
        await service.send_to_requester(settings, ticket, "<p>x</p>", [])

    assert outbox[0]["Reply-To"] is None
