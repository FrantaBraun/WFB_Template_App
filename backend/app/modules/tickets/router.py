# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The tickets module's endpoints.

Everything under /manage is administrator-only (the local User.is_admin flag,
never the JWT's role_name - see app.api.deps.require_admin): those routes are
declared on `admin_router`, which carries require_admin, so a route added
later cannot forget it. The one deliberate exception is declared on the outer
`router` and listed in tests/test_modules_tickets_access.py:

- GET /files/{filename}, the pictures inside entries. The editor and the
  mail client of a customer who received one of our mails load them without
  signing in, so the address is the secret: 128 random bits, serving only
  names of the exact shape this module generates and only image types (see
  storage.py). Private attachments have no such address.

Tickets are addressed by their number (what people see), entries and files by
id. Refusals use short `detail` codes the frontend translates, like the forms
module's error codes.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.crm.models import Partner
from app.modules.tickets import mailbox, service, storage
from app.modules.tickets.models import Ticket, TicketAttachment, TicketEntry
from app.modules.tickets.schemas import (
    AttachmentOut,
    EntryCreate,
    EntryOut,
    EntryUpdate,
    ImageUploadOut,
    MailboxPollResult,
    MailboxStatusOut,
    PartnerRef,
    TicketCreate,
    TicketDetail,
    TicketListItem,
    TicketOut,
    TicketPage,
    TicketSource,
    TicketStatus,
    TicketType,
    TicketUpdate,
)
from app.security.jwt import get_current_user_claims
from app.services.sanitize import sanitize_html

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter(dependencies=[Depends(require_admin)])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _refuse(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=code)


def _like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def _get_ticket(db: AsyncSession, number: int) -> Ticket:
    ticket = await db.scalar(select(Ticket).where(Ticket.number == number))
    if ticket is None:
        raise _refuse(404, "ticket_not_found")
    return ticket


async def _linkable_partner(db: AsyncSession, partner_id: uuid.UUID) -> Partner:
    """The partner a ticket may be linked to: only while the CRM is switched
    on, and only one that exists."""
    if not service.crm_enabled():
        raise _refuse(422, "crm_disabled")
    partner = await db.get(Partner, partner_id)
    if partner is None:
        raise _refuse(422, "partner_not_found")
    return partner


def _author_label(claims: dict) -> str | None:
    label = claims.get("email") or claims.get("login")
    return str(label)[:254] if label else None


def _entry_out(entry: TicketEntry, attachments: list[TicketAttachment]) -> EntryOut:
    return EntryOut.model_validate(entry).model_copy(
        update={"attachments": [AttachmentOut.model_validate(a) for a in attachments]}
    )


async def _detail(db: AsyncSession, ticket: Ticket) -> TicketDetail:
    # updated_at is set by the database on every UPDATE, so after a change it
    # is expired and could only be read lazily - which async sessions cannot do.
    await db.refresh(ticket)
    entries = (
        await db.scalars(
            select(TicketEntry)
            .where(TicketEntry.ticket_id == ticket.id)
            .order_by(TicketEntry.created_at, TicketEntry.seq)
        )
    ).all()
    files = (
        await db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.ticket_id == ticket.id,
                TicketAttachment.entry_id.is_not(None),
                TicketAttachment.is_inline.is_(False),
            )
            .order_by(TicketAttachment.created_at, TicketAttachment.original_filename)
        )
    ).all()
    by_entry: dict[uuid.UUID, list[TicketAttachment]] = {}
    for item in files:
        by_entry.setdefault(item.entry_id, []).append(item)
    partner = await db.get(Partner, ticket.partner_id) if ticket.partner_id else None
    return TicketDetail(
        **TicketOut.model_validate(ticket).model_dump(),
        entries=[_entry_out(e, by_entry.get(e.id, [])) for e in entries],
    ).model_copy(
        update={
            "total_minutes": sum(e.minutes for e in entries),
            "partner": PartnerRef.model_validate(partner) if partner else None,
        }
    )


# --- Public: pictures inside entries ------------------------------------------


@router.get("/files/{filename}")
async def get_inline_image(filename: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    media_type = storage.image_media_type(filename)
    if media_type is None:
        raise HTTPException(status_code=404, detail="Not found")
    path = storage.uploads_dir(settings) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


# --- Tickets ------------------------------------------------------------------


@admin_router.get("")
async def list_tickets(
    q: str | None = Query(default=None, max_length=100),
    status: TicketStatus | None = None,
    type: TicketType | None = None,
    source: TicketSource | None = None,
    partner_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
) -> TicketPage:
    """Tickets, the most recently active first. `q` matches the subject, the
    requester's name and address (case-insensitive) and the ticket number
    ("100253", "#100253" or "Ticket#100253")."""
    filters = []
    if status:
        filters.append(Ticket.status == status)
    if type:
        filters.append(Ticket.type == type)
    if source:
        filters.append(Ticket.source == source)
    if partner_id:
        filters.append(Ticket.partner_id == partner_id)
    if q and q.strip():
        text = q.strip()
        pattern = _like_pattern(text)
        conditions = [
            Ticket.subject.ilike(pattern, escape="\\"),
            Ticket.requester_name.ilike(pattern, escape="\\"),
            Ticket.requester_email.ilike(pattern, escape="\\"),
        ]
        digits = text.lower().removeprefix("ticket").lstrip("# ").strip()
        if digits.isdigit() and len(digits) <= 9:
            conditions.append(Ticket.number == int(digits))
        filters.append(or_(*conditions))

    total = await db.scalar(select(func.count(Ticket.id)).where(*filters)) or 0
    minutes = (
        select(func.coalesce(func.sum(TicketEntry.minutes), 0))
        .where(TicketEntry.ticket_id == Ticket.id)
        .correlate(Ticket)
        .scalar_subquery()
    )
    entries = (
        select(func.count(TicketEntry.id)).where(TicketEntry.ticket_id == Ticket.id).correlate(Ticket).scalar_subquery()
    )
    rows = (
        await db.execute(
            select(Ticket, Partner, minutes, entries)
            .outerjoin(Partner, Partner.id == Ticket.partner_id)
            .where(*filters)
            .order_by(Ticket.last_activity_at.desc(), Ticket.number.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        TicketListItem(
            **TicketOut.model_validate(ticket).model_dump(exclude={"partner", "total_minutes"}),
            partner=PartnerRef.model_validate(partner) if partner else None,
            total_minutes=total_minutes,
            entry_count=entry_count,
        )
        for ticket, partner, total_minutes, entry_count in rows
    ]
    return TicketPage(items=items, total=total, page=page, page_size=page_size)


@admin_router.post("", status_code=201)
async def create_ticket(
    body: TicketCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
    claims: dict = Depends(get_current_user_claims),
) -> TicketDetail:
    """A ticket typed in by an administrator. Linking a partner is only
    done when asked for (never guessed from the address, unlike a mailed-in
    request)."""
    partner = await _linkable_partner(db, body.partner_id) if body.partner_id else None
    ticket = await service.create_ticket(
        db,
        subject=body.subject,
        source="manual",
        type=body.type,
        requester_name=body.requester_name or (partner.name if partner else None),
        requester_email=str(body.requester_email) if body.requester_email else (partner.email if partner else None),
        partner_id=partner.id if partner else None,
        lookup_partner=False,
    )
    description = sanitize_html(body.description_html)
    if service.has_content(description):
        service.add_entry(
            db,
            ticket,
            kind="note",
            content_html=description,
            author_user_id=user.id,
            author_label=_author_label(claims),
        )
    await db.commit()
    return await _detail(db, ticket)


@admin_router.get("/mailbox")
async def get_mailbox_status(settings: Settings = Depends(get_settings)) -> MailboxStatusOut:
    last = mailbox.status.last_result
    return MailboxStatusOut(
        configured=mailbox.mailbox_configured(settings),
        address=service.mailbox_address(settings),
        poll_seconds=settings.tickets_poll_seconds,
        last_checked_at=mailbox.status.last_checked_at,
        last_error=mailbox.status.last_error,
        last_result=MailboxPollResult(**vars(last)) if last else None,
    )


@admin_router.post("/mailbox/poll")
async def poll_mailbox(settings: Settings = Depends(get_settings)) -> MailboxPollResult:
    """Check the mailbox now instead of waiting for the next periodic check."""
    if not mailbox.mailbox_configured(settings):
        raise _refuse(409, "mailbox_not_configured")
    try:
        result = await mailbox.poll_once(settings)
    except Exception as exc:
        logger.exception("Checking the ticket mailbox failed")
        raise _refuse(502, "mailbox_error") from exc
    return MailboxPollResult(**vars(result))


@admin_router.get("/attachments/{attachment_id}/file")
async def download_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    item = await db.get(TicketAttachment, attachment_id)
    if item is None:
        raise _refuse(404, "attachment_not_found")
    path = storage.stored_path(settings, item.stored_name)
    if not path.is_file():
        raise _refuse(404, "attachment_missing")
    return FileResponse(
        path,
        media_type=item.content_type,
        filename=item.original_filename,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@admin_router.get("/{number}")
async def get_ticket(number: int, db: AsyncSession = Depends(get_db)) -> TicketDetail:
    return await _detail(db, await _get_ticket(db, number))


@admin_router.patch("/{number}")
async def update_ticket(number: int, body: TicketUpdate, db: AsyncSession = Depends(get_db)) -> TicketDetail:
    ticket = await _get_ticket(db, number)
    changes = body.model_dump(exclude_unset=True)
    for field in ("subject", "type", "status"):
        if field in changes and changes[field] is not None:
            setattr(ticket, field, changes[field])
    for field in ("requester_name", "requester_email"):
        if field in changes:
            value = changes[field]
            setattr(ticket, field, str(value) if value else None)
    if "partner_id" in changes:
        if changes["partner_id"] is not None:
            await _linkable_partner(db, changes["partner_id"])
        ticket.partner_id = changes["partner_id"]
    await db.commit()
    return await _detail(db, ticket)


@admin_router.delete("/{number}", status_code=204)
async def delete_ticket(
    number: int, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> None:
    """A real delete: the ticket, its thread and every file. Close a ticket
    instead to keep it."""
    ticket = await _get_ticket(db, number)
    stored_names = list(
        await db.scalars(select(TicketAttachment.stored_name).where(TicketAttachment.ticket_id == ticket.id))
    )
    await db.delete(ticket)
    await db.commit()
    storage.delete_files(settings, stored_names)


# --- Entries ------------------------------------------------------------------


@admin_router.post("/{number}/entries", status_code=201)
async def create_entry(
    number: int,
    body: EntryCreate,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_admin),
    claims: dict = Depends(get_current_user_claims),
) -> EntryOut:
    """An internal note, or a mail to the requester (sent first: when the mail
    cannot be sent nothing is saved and the answer is 502, so the text can be
    sent again). Either may carry the time spent and files uploaded earlier."""
    ticket = await _get_ticket(db, number)
    attachments: list[TicketAttachment] = []
    if body.attachment_ids:
        wanted = list(dict.fromkeys(body.attachment_ids))
        rows = {
            a.id: a
            for a in (
                await db.scalars(
                    select(TicketAttachment).where(
                        TicketAttachment.id.in_(wanted),
                        TicketAttachment.ticket_id == ticket.id,
                        TicketAttachment.entry_id.is_(None),
                        TicketAttachment.is_inline.is_(False),
                    )
                )
            ).all()
        }
        if len(rows) != len(wanted):
            raise _refuse(422, "attachment_invalid")
        attachments = [rows[i] for i in wanted]

    content = sanitize_html(body.content_html)
    time_only_note = body.kind == "note" and body.minutes > 0
    if not (service.has_content(content) or attachments or time_only_note):
        raise _refuse(422, "empty_entry")
    if body.kind == "outgoing" and not ticket.requester_email:
        raise _refuse(422, "no_requester_email")

    entry = service.add_entry(
        db,
        ticket,
        kind=body.kind,
        content_html=content,
        minutes=body.minutes,
        author_user_id=user.id,
        author_label=_author_label(claims),
        to_address=ticket.requester_email if body.kind == "outgoing" else None,
        email_subject=service.outgoing_subject(ticket) if body.kind == "outgoing" else None,
    )
    await db.flush()
    for item in attachments:
        item.entry_id = entry.id

    if body.kind == "outgoing":
        try:
            await service.send_to_requester(settings, ticket, content, attachments)
        except Exception as exc:
            logger.exception("Failed to send the mail of ticket %s", ticket.number)
            await db.rollback()
            raise _refuse(502, "email_failed") from exc
    await db.commit()
    return _entry_out(entry, attachments)


async def _get_entry(db: AsyncSession, ticket: Ticket, entry_id: uuid.UUID) -> TicketEntry:
    entry = await db.get(TicketEntry, entry_id)
    if entry is None or entry.ticket_id != ticket.id:
        raise _refuse(404, "entry_not_found")
    return entry


@admin_router.patch("/{number}/entries/{entry_id}")
async def update_entry(
    number: int, entry_id: uuid.UUID, body: EntryUpdate, db: AsyncSession = Depends(get_db)
) -> EntryOut:
    ticket = await _get_ticket(db, number)
    entry = await _get_entry(db, ticket, entry_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("content_html") is not None:
        if entry.kind != "note":
            # A mail we sent or received is a record of what was said.
            raise _refuse(422, "entry_not_editable")
        entry.content_html = sanitize_html(changes["content_html"])
    if changes.get("minutes") is not None:
        entry.minutes = changes["minutes"]
    ticket.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    files = (
        await db.scalars(
            select(TicketAttachment).where(
                TicketAttachment.entry_id == entry.id, TicketAttachment.is_inline.is_(False)
            )
        )
    ).all()
    return _entry_out(entry, list(files))


@admin_router.delete("/{number}/entries/{entry_id}", status_code=204)
async def delete_entry(
    number: int,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Only a note: mails stay as a record."""
    ticket = await _get_ticket(db, number)
    entry = await _get_entry(db, ticket, entry_id)
    if entry.kind != "note":
        raise _refuse(422, "entry_not_editable")
    stored_names = list(
        await db.scalars(select(TicketAttachment.stored_name).where(TicketAttachment.entry_id == entry.id))
    )
    await db.delete(entry)
    await db.commit()
    storage.delete_files(settings, stored_names)


# --- Files --------------------------------------------------------------------


@admin_router.post("/{number}/images", status_code=201)
async def upload_image(
    number: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImageUploadOut:
    """A picture for the text of an entry; answers with the address to put in
    the editor (public, see the module docstring)."""
    ticket = await _get_ticket(db, number)
    contents, extension = await storage.read_image(file)
    stored_name = storage.save_bytes(settings, contents, extension)
    db.add(
        TicketAttachment(
            ticket_id=ticket.id,
            original_filename=storage.clean_filename(file.filename, default=f"image{extension}"),
            stored_name=stored_name,
            content_type=storage.image_media_type(stored_name) or "application/octet-stream",
            size_bytes=len(contents),
            is_inline=True,
        )
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        storage.delete_file(settings, stored_name)
        raise
    return ImageUploadOut(url=f"{settings.app_base_url.rstrip('/')}/api/modules/tickets/files/{stored_name}")


@admin_router.post("/{number}/attachments", status_code=201)
async def upload_attachment(
    number: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AttachmentOut:
    """A file for the next entry (up to 10 MB). It stays unattached until an
    entry names it in `attachment_ids`; private either way."""
    ticket = await _get_ticket(db, number)
    contents = await storage.read_limited(file, storage.MAX_ATTACHMENT_BYTES, "File too large (max 10 MB)")
    stored_name = storage.save_bytes(settings, contents, storage.PRIVATE_EXTENSION)
    item = TicketAttachment(
        ticket_id=ticket.id,
        original_filename=storage.clean_filename(file.filename),
        stored_name=stored_name,
        content_type=storage.clean_content_type(file.content_type),
        size_bytes=len(contents),
        is_inline=False,
    )
    db.add(item)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        storage.delete_file(settings, stored_name)
        raise
    await db.refresh(item)
    return AttachmentOut.model_validate(item)


@admin_router.delete("/{number}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    number: int,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Take back a file that was uploaded but not sent with an entry yet."""
    ticket = await _get_ticket(db, number)
    item = await db.get(TicketAttachment, attachment_id)
    if item is None or item.ticket_id != ticket.id:
        raise _refuse(404, "attachment_not_found")
    if item.entry_id is not None or item.is_inline:
        raise _refuse(409, "attachment_in_use")
    stored_name = item.stored_name
    await db.delete(item)
    await db.commit()
    storage.delete_file(settings, stored_name)


router.include_router(admin_router, prefix="/manage")
