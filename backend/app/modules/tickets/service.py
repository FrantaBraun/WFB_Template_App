# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the tickets module does, apart from HTTP: numbering and tagging,
creating tickets from the three sources (the form, the contact form hook, the
mailbox), matching a received mail to its ticket and sending ours.

Nothing in here commits except contact_form_hook (which runs inside another
module's request and has nobody else to do it): the callers - the router, the
mailbox poller - own their transaction, so a refusal leaves nothing behind.
"""

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO

from fastapi_mail import MessageType
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers, UploadFile

from app.config import Settings, get_settings
from app.modules.crm.models import Partner
from app.modules.kontaktni_formular.hooks import ContactHookResult, ContactSubmission
from app.modules.registry import load_enabled_module_keys
from app.modules.tickets import storage
from app.modules.tickets.mailparse import ParsedMail
from app.modules.tickets.models import DEFAULT_TYPE, Ticket, TicketAttachment, TicketEntry
from app.services.email import send_email
from app.services.sanitize import sanitize_html

logger = logging.getLogger(__name__)

# What the subject of every mail of a ticket carries, and what a received mail
# is matched to its ticket by. Tolerant of the spaces a mail client may add.
TICKET_TAG = re.compile(r"\[\s*Ticket\s*#\s*(\d{1,12})\s*\]", re.IGNORECASE)
SUBJECT_LIMIT = 200
MAX_HTML_CHARS = 300_000
_HEAD = re.compile(r"(?is)<head\b.*?</head>")
_DIV = re.compile(r"(?i)<(/?)div\b")
_IMG = re.compile(r"(?i)<img\b")
_TAGS = re.compile(r"(?s)<[^>]*>")


# --- Numbers, subjects, text --------------------------------------------------


def subject_tag(number: int) -> str:
    return f"[Ticket#{number}]"


def find_ticket_number(subject: str) -> int | None:
    """The ticket number a subject names ("Re: [Ticket#100253] - Dotaz"), or None."""
    match = TICKET_TAG.search(subject or "")
    return int(match.group(1)) if match else None


def strip_ticket_tag(subject: str) -> str:
    """The subject without any "[Ticket#N]" tag (and the " - " after it)."""
    cleaned = re.sub(rf"{TICKET_TAG.pattern}\s*[-–:]?\s*", "", subject or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def outgoing_subject(ticket: Ticket) -> str:
    """The subject of a mail we send about `ticket`: "[Ticket#100253] - Dotaz"."""
    return f"{subject_tag(ticket.number)} - {ticket.subject}"


def plain_to_html(text: str) -> str:
    """Plain text as HTML paragraphs (a blank line starts a new one)."""
    paragraphs = [p for p in re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip()) if p.strip()]
    return "".join(f"<p>{html.escape(p.strip()).replace(chr(10), '<br>')}</p>" for p in paragraphs)


def has_content(content_html: str) -> bool:
    """Whether HTML shows anything: some text, or a picture. The editor hands
    over "<p></p>" for an empty field."""
    return bool(_IMG.search(content_html) or html.unescape(_TAGS.sub("", content_html)).strip())


def truncate_subject(subject: str) -> str:
    subject = re.sub(r"\s+", " ", subject or "").strip() or "-"
    return subject[:SUBJECT_LIMIT]


# --- CRM and the mailbox's own address ---------------------------------------


def crm_enabled() -> bool:
    """Whether the CRM module is switched on (backend/modules.json). Only then
    are partners looked up and linked: the table is always there, but a
    partner nobody can see in the application is not something to attach to."""
    return "crm" in load_enabled_module_keys()


async def find_partner_by_email(db: AsyncSession, email: str) -> Partner | None:
    """The CRM partner whose e-mail address is `email` (case-insensitive,
    exact). An active partner beats an archived one, then the oldest wins, so
    the same address always finds the same partner."""
    address = (email or "").strip().lower()
    if not address:
        return None
    return await db.scalar(
        select(Partner)
        .where(func.lower(Partner.email) == address)
        .order_by(Partner.archived, Partner.created_at, Partner.id)
        .limit(1)
    )


def mailbox_address(settings: Settings) -> str | None:
    """The address customers' answers must reach (the Reply-To of our mails):
    TICKETS_MAILBOX_ADDRESS, else - once a mailbox is configured at all - the
    IMAP user name when that is an address, else MAIL_FROM. None while no
    mailbox is configured: then nothing reads answers and Reply-To stays unset."""
    explicit = settings.tickets_mailbox_address.strip()
    if explicit:
        return explicit
    if not settings.tickets_imap_host.strip():
        return None
    username = settings.tickets_imap_username.strip()
    return username if "@" in username else (settings.mail_from.strip() or None)


def is_own_address(address: str, settings: Settings) -> bool:
    """Our own sender / mailbox address: mail from it is what we sent (the
    owner's notification of a contact form message, a Bcc of a reply) and
    must never become a ticket or an entry."""
    own = {settings.mail_from.strip().lower(), (mailbox_address(settings) or "").lower()} - {""}
    return address.strip().lower() in own


# --- Creating tickets and entries ---------------------------------------------


async def create_ticket(
    db: AsyncSession,
    *,
    subject: str,
    source: str,
    type: str = DEFAULT_TYPE,
    requester_name: str | None = None,
    requester_email: str | None = None,
    partner_id=None,
    lookup_partner: bool = True,
) -> Ticket:
    """Add a ticket and flush it (so its number exists). Without a
    `partner_id`, and with the CRM on, the partner is looked up by the
    requester's address; none found means a ticket without a link."""
    if partner_id is None and lookup_partner and requester_email and crm_enabled():
        partner = await find_partner_by_email(db, requester_email)
        partner_id = partner.id if partner else None
    ticket = Ticket(
        subject=truncate_subject(subject),
        type=type,
        source=source,
        requester_name=requester_name[:200] if requester_name else None,
        requester_email=requester_email[:254] if requester_email else None,
        partner_id=partner_id,
    )
    db.add(ticket)
    await db.flush()
    return ticket


def add_entry(db: AsyncSession, ticket: Ticket, *, kind: str, **fields) -> TicketEntry:
    """Add an entry to the ticket's thread and mark the ticket as active now."""
    entry = TicketEntry(ticket_id=ticket.id, kind=kind, **fields)
    db.add(entry)
    ticket.last_activity_at = datetime.now(timezone.utc)
    return entry


async def contact_form_hook(db: AsyncSession, submission: ContactSubmission) -> ContactHookResult:
    """The tickets module's part in a contact form message (registered as the
    manifest's CONTACT_FORM_RECEIVED hook): the message becomes a ticket, and
    every mail the form sends about it gets the ticket's number in its subject
    and the mailbox as the place the sender's answer goes."""
    anonymous = submission.sender_name == submission.reply_to
    ticket = await create_ticket(
        db,
        subject=submission.subject,
        source="contact_form",
        requester_name=None if anonymous else submission.sender_name,
        requester_email=submission.reply_to or None,
    )
    add_entry(
        db,
        ticket,
        kind="incoming",
        content_html=sanitize_html(plain_to_html(submission.message)),
        from_name=None if anonymous else submission.sender_name[:200],
        from_address=submission.reply_to or None,
        email_subject=submission.subject[:500],
    )
    await db.commit()
    return ContactHookResult(subject_tag=subject_tag(ticket.number), reply_to=mailbox_address(get_settings()))


# --- Received mail ------------------------------------------------------------


@dataclass
class ImportOutcome:
    """What import_message did: `ticket` / `entry` are None when the mail was
    skipped (`skipped` says why); `created` is whether it opened a new ticket;
    `files` are the stored names it wrote, for a caller whose commit fails."""

    ticket: Ticket | None = None
    entry: TicketEntry | None = None
    created: bool = False
    skipped: str | None = None
    files: list[str] = field(default_factory=list)


def _mail_html(mail: ParsedMail, inline_urls: dict[str, str]) -> str:
    """The body of a received mail as sanitized HTML: its HTML part with the
    pictures it carries pointed at our own copies, else its text part. Mail
    HTML leans on <div>, which the sanitizer (made for the editor's output)
    drops, so divs become paragraphs first to keep the lines apart."""
    cleaned = ""
    if mail.html:
        source = _DIV.sub(r"<\1p", _HEAD.sub("", mail.html))
        for content_id, url in inline_urls.items():
            source = re.sub(f"cid:{re.escape(content_id)}", url, source, flags=re.IGNORECASE)
        cleaned = sanitize_html(source)
    if not has_content(cleaned):
        cleaned = sanitize_html(plain_to_html(mail.text))
    if len(cleaned) > MAX_HTML_CHARS:
        cleaned = sanitize_html(plain_to_html(html.unescape(_TAGS.sub(" ", cleaned))[:MAX_HTML_CHARS]))
    return cleaned


def _store_attachments(
    db: AsyncSession, settings: Settings, ticket: Ticket, entry: TicketEntry, mail: ParsedMail, written: list[str]
) -> dict[str, str]:
    """Save the mail's files; returns the public address of each inline
    picture by its Content-ID. `written` collects the stored names so the
    caller can delete the files when the transaction fails."""
    base = settings.app_base_url.rstrip("/")
    referenced = (mail.html or "").lower()
    inline_urls: dict[str, str] = {}
    for item in mail.attachments:
        if len(item.data) > storage.MAX_ATTACHMENT_BYTES:
            logger.warning("Ticket mail %s: attachment %r is over the size limit - left out", mail.message_id, item.filename)
            continue
        extension = storage.sniff_image(item.content_type, item.data) if item.inline else None
        shown_inline = bool(extension and item.content_id and f"cid:{item.content_id.lower()}" in referenced)
        stored_name = storage.save_bytes(settings, item.data, extension if shown_inline else storage.PRIVATE_EXTENSION)
        written.append(stored_name)
        db.add(
            TicketAttachment(
                ticket_id=ticket.id,
                entry_id=None if shown_inline else entry.id,
                original_filename=storage.clean_filename(item.filename),
                stored_name=stored_name,
                content_type=storage.clean_content_type(item.content_type),
                size_bytes=len(item.data),
                is_inline=shown_inline,
            )
        )
        if shown_inline:
            inline_urls[item.content_id] = f"{base}/api/modules/tickets/files/{stored_name}"
    return inline_urls


async def import_message(db: AsyncSession, mail: ParsedMail, settings: Settings) -> ImportOutcome:
    """File a received mail: onto the ticket its subject names, else as a new
    ticket (with the CRM's partner for the sender, when there is one). Skips a
    mail it has seen (same Message-ID), one from our own address, and an
    automatic mail that names no ticket. Flushes only - the caller commits (and
    deletes ImportOutcome.files if that fails); a failure inside this function
    deletes the files it had written and is re-raised."""
    if is_own_address(mail.from_address, settings):
        return ImportOutcome(skipped="own address")
    if await db.scalar(select(TicketEntry.id).where(TicketEntry.message_id == mail.message_id)):
        return ImportOutcome(skipped="already imported")

    number = find_ticket_number(mail.subject)
    ticket = await db.scalar(select(Ticket).where(Ticket.number == number)) if number else None
    created = ticket is None
    if ticket is None and mail.automatic:
        return ImportOutcome(skipped="automatic mail")

    written: list[str] = []
    try:
        if ticket is None:
            ticket = await create_ticket(
                db,
                subject=strip_ticket_tag(mail.subject) or "(no subject)",
                source="email",
                requester_name=mail.from_name,
                requester_email=mail.from_address or None,
            )
        elif ticket.status == "closed":
            ticket.status = "open"

        now = datetime.now(timezone.utc)
        entry = add_entry(
            db,
            ticket,
            kind="incoming",
            from_name=mail.from_name and mail.from_name[:200],
            from_address=mail.from_address[:254] or None,
            email_subject=mail.subject[:500] or None,
            message_id=mail.message_id,
            created_at=min(mail.sent_at, now) if mail.sent_at else now,
        )
        await db.flush()
        inline_urls = _store_attachments(db, settings, ticket, entry, mail, written)
        entry.content_html = _mail_html(mail, inline_urls)
        await db.flush()
    except Exception:
        storage.delete_files(settings, written)
        raise
    return ImportOutcome(ticket=ticket, entry=entry, created=created, files=written)


# --- Sending ------------------------------------------------------------------


async def send_to_requester(
    settings: Settings, ticket: Ticket, content_html: str, attachments: list[TicketAttachment]
) -> None:
    """Mail `content_html` (already sanitized) and the files to the ticket's
    requester, with the ticket's number in the subject and the mailbox as
    Reply-To. Raises whatever the mail transport raises."""
    files = []
    for item in attachments:
        data = storage.stored_path(settings, item.stored_name).read_bytes()
        files.append(
            UploadFile(
                file=BytesIO(data),
                filename=item.original_filename,
                headers=Headers({"content-type": item.content_type}),
            )
        )
    reply_to = mailbox_address(settings)
    await send_email(
        outgoing_subject(ticket),
        [ticket.requester_email],
        f"<div>{content_html}</div>",
        subtype=MessageType.html,
        settings=settings,
        reply_to=[reply_to] if reply_to else None,
        attachments=files,
    )
