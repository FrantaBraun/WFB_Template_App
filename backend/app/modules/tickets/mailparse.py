# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Turns a raw RFC 822 message (what the mailbox hands over) into the few
things a ticket needs: who wrote it, the subject, a Message-ID, the text as
HTML and the files. Pure and database-free; service.import_message does the
rest. Uses only the standard library's email package."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import message_from_bytes
from email.message import Message
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime

MAX_ATTACHMENTS_PER_MAIL = 20


@dataclass
class ParsedAttachment:
    filename: str
    content_type: str
    data: bytes
    # The Content-ID without angle brackets - what an inline picture is
    # referred to by in the HTML ("cid:<this>").
    content_id: str | None = None
    inline: bool = False


@dataclass
class ParsedMail:
    message_id: str
    subject: str
    from_name: str | None
    from_address: str
    sent_at: datetime | None
    html: str | None
    text: str
    # A mail machines send to machines (out-of-office replies, bounces,
    # newsletters): it may be attached to a ticket it names, but never starts one.
    automatic: bool = False
    attachments: list[ParsedAttachment] = field(default_factory=list)


def _header(message: Message, name: str) -> str:
    value = message.get(name)
    return str(value).strip() if value is not None else ""


def _is_automatic(message: Message) -> bool:
    auto_submitted = _header(message, "Auto-Submitted").lower()
    if auto_submitted and auto_submitted != "no":
        return True
    if _header(message, "Precedence").lower() in {"bulk", "junk", "list", "auto_reply"}:
        return True
    return bool(_header(message, "X-Autoreply") or _header(message, "X-Autorespond") or _header(message, "List-Id"))


def _text_of(part: Message) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def _sent_at(message: Message) -> datetime | None:
    raw = _header(message, "Date")
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_message(raw: bytes) -> ParsedMail:
    """Parse one message. Never raises for a merely odd message (a missing
    header, a broken charset): it falls back to empty values, since a mail we
    cannot read perfectly is still a request somebody sent."""
    message = message_from_bytes(raw, policy=default_policy)

    name, address = parseaddr(_header(message, "From"))
    message_id = _header(message, "Message-ID")
    if not message_id:
        # Without one there is nothing to recognise the mail by when it turns
        # up again, so derive a stable id from the content.
        message_id = f"<{hashlib.sha256(raw).hexdigest()}@generated.invalid>"

    html: str | None = None
    text = ""
    attachments: list[ParsedAttachment] = []
    for part in message.walk():
        if part.is_multipart() or part.get_content_type() == "message/rfc822":
            continue
        content_type = part.get_content_type()
        disposition = (part.get_content_disposition() or "").lower()
        filename = part.get_filename()
        is_body = content_type in ("text/html", "text/plain") and disposition != "attachment" and not filename
        if is_body:
            if content_type == "text/html":
                html = html if html is not None else _text_of(part)
            elif not text:
                text = _text_of(part)
            continue
        if len(attachments) >= MAX_ATTACHMENTS_PER_MAIL:
            continue
        data = part.get_payload(decode=True) or b""
        if not data:
            continue
        content_id = _header(part, "Content-ID").strip("<>") or None
        attachments.append(
            ParsedAttachment(
                filename=filename or f"attachment-{len(attachments) + 1}",
                content_type=content_type,
                data=data,
                content_id=content_id,
                inline=content_id is not None and disposition != "attachment" and content_type.startswith("image/"),
            )
        )

    return ParsedMail(
        message_id=message_id[:500],
        subject=re.sub(r"\s+", " ", _header(message, "Subject")),
        from_name=name.strip() or None,
        from_address=address.strip().lower(),
        sent_at=_sent_at(message),
        html=html,
        text=text,
        automatic=_is_automatic(message),
        attachments=attachments,
    )
