# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.modules.tickets.mailparse: raw messages -> what a ticket needs."""

from datetime import datetime, timezone

from app.modules.tickets.mailparse import parse_message
from tests.tickets_support import PDF, PNG, make_mail


def test_a_plain_text_mail_is_read_with_its_sender_subject_and_date():
    raw = make_mail(
        subject="Dotaz  na   cenu",
        sender="Jana Nováková <Jana@Example.com>",
        text="Dobrý den,\nmám otázku.",
        message_id="<abc@example.com>",
        sent_at=datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc),
    )

    mail = parse_message(raw)

    assert mail.subject == "Dotaz na cenu"
    assert (mail.from_name, mail.from_address) == ("Jana Nováková", "jana@example.com")
    assert mail.message_id == "<abc@example.com>"
    assert mail.sent_at == datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc)
    assert "mám otázku." in mail.text
    assert mail.html is None
    assert mail.attachments == []
    assert mail.automatic is False


def test_both_parts_of_an_alternative_mail_are_kept():
    mail = parse_message(make_mail(text="plain", html="<p>html <b>bold</b></p>"))

    assert mail.text.strip() == "plain"
    assert "<b>bold</b>" in mail.html


def test_a_mail_without_a_message_id_gets_a_stable_one():
    raw = make_mail().replace(b"Message-ID:", b"X-Old:")
    first, second = parse_message(raw), parse_message(raw)

    assert first.message_id == second.message_id
    assert first.message_id.endswith("@generated.invalid>")
    assert parse_message(raw + b"\n.").message_id != first.message_id


def test_a_missing_or_broken_date_is_none_not_an_error():
    raw = make_mail().replace(b"Date:", b"X-Date:")
    assert parse_message(raw).sent_at is None
    assert parse_message(make_mail(headers={"X-A": "1"}).replace(b"Date: ", b"Date: not a date ")).sent_at is None


def test_files_are_collected_with_their_names_and_content():
    mail = parse_message(make_mail(attachments=[("faktura.pdf", "application/pdf", PDF)]))

    [item] = mail.attachments
    assert (item.filename, item.content_type, item.data) == ("faktura.pdf", "application/pdf", PDF)
    assert item.inline is False and item.content_id is None
    assert "mám otázku" in mail.text


def test_an_inline_picture_is_recognised_by_its_content_id():
    mail = parse_message(
        make_mail(html='<p>Hi <img src="cid:logo123"></p>', inline_images=[("logo123", "image/png", PNG)])
    )

    [item] = mail.attachments
    assert item.content_id == "logo123"
    assert item.inline is True
    assert item.data == PNG
    assert 'cid:logo123' in mail.html


def test_a_pdf_with_a_content_id_is_not_inline():
    mail = parse_message(
        make_mail(html="<p>x</p>", inline_images=[("doc1", "application/pdf", PDF)])
    )

    assert [a.inline for a in mail.attachments] == [False]


def test_only_a_limited_number_of_files_is_collected():
    files = [(f"f{i}.pdf", "application/pdf", PDF) for i in range(25)]

    assert len(parse_message(make_mail(attachments=files)).attachments) == 20


def test_machine_generated_mail_is_flagged_automatic():
    for headers in (
        {"Auto-Submitted": "auto-replied"},
        {"Precedence": "bulk"},
        {"X-Autoreply": "yes"},
        {"List-Id": "<news.example.com>"},
    ):
        assert parse_message(make_mail(headers=headers)).automatic is True, headers

    assert parse_message(make_mail(headers={"Auto-Submitted": "no"})).automatic is False


def test_an_odd_message_never_raises():
    mail = parse_message(b"Subject: only a subject\n\n")

    assert mail.subject == "only a subject"
    assert mail.from_address == ""
    assert mail.text.strip() == ""
