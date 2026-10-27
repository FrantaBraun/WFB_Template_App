# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Helpers shared by the tickets module's tests: raw RFC 822 messages as a
mailbox would hand them over, and the settings those tests run with."""

import itertools
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone

from app.config import Settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PDF = b"%PDF-1.4\n%fake\n"
_ids = itertools.count(1)


def make_mail(
    *,
    subject: str = "Dotaz",
    sender: str = "Jana Nováková <jana@example.com>",
    to: str = "tickets@example.com",
    text: str | None = "Dobrý den,\n\nmám otázku.",
    html: str | None = None,
    message_id: str | None = None,
    sent_at: datetime | None = None,
    attachments: list[tuple[str, str, bytes]] | None = None,
    inline_images: list[tuple[str, str, bytes]] | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
    """A message as bytes. `attachments` are (filename, content_type, data);
    `inline_images` are (content_id, content_type, data), referenced from the
    HTML as cid:<content_id>."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    message["Message-ID"] = message_id or f"<test-{next(_ids)}@example.com>"
    message["Date"] = format_datetime(sent_at or datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc))
    for name, value in (headers or {}).items():
        message[name] = value

    if text is not None:
        message.set_content(text)
    if html is not None:
        if text is None:
            message.set_content(html, subtype="html")
        else:
            message.add_alternative(html, subtype="html")
    for content_id, content_type, data in inline_images or []:
        maintype, subtype = content_type.split("/", 1)
        target = message.get_body(preferencelist=("html",)) or message
        target.add_related(data, maintype, subtype, cid=f"<{content_id}>", disposition="inline")
    for filename, content_type, data in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()


def tickets_settings(tmp_path, **overrides) -> Settings:
    """Settings for the module: files in tmp_path, a mailbox configured (it is
    never contacted - tests hand the poller a fake), mail not actually sent."""
    values = {
        "uploads_dir": str(tmp_path),
        "app_base_url": "http://app.test",
        "mail_from": "noreply@example.com",
        "mail_suppress_send": True,
        "mail_username": "smtp-user",
        "mail_password": "smtp-pass",
        "mail_server": "smtp.example.com",
        "tickets_imap_host": "imap.example.com",
        "tickets_imap_username": "tickets@example.com",
        "tickets_imap_password": "imap-secret",
    }
    values.update(overrides)
    return Settings(**values)
