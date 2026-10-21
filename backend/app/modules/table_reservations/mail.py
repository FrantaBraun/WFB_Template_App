# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The e-mails of the table reservations module: building the values a template
may use and sending it. Sending never raises - an e-mail that cannot go out must
not break a reservation or the pub's cancellation - it logs and reports (sent,
error) so the caller can record it (Reservation.email_error, `email_sent` in the
API response)."""

import logging
from datetime import date, time

from app.config import Settings
from app.modules.table_reservations.config import TableReservationsConfig, normalize_language
from app.modules.table_reservations.models import Reservation
from app.services.email import send_email

logger = logging.getLogger(__name__)

ERROR_MAX = 500


def format_date(value: date, language: str | None) -> str:
    """"20. 5. 2027" in Czech, the unambiguous ISO form (2027-05-20) in any other language."""
    if language and normalize_language(language).split("-")[0] == "cs":
        return f"{value.day}. {value.month}. {value.year}"
    return value.isoformat()


def format_time(value: time) -> str:
    return value.strftime("%H:%M")


def cancel_url(settings: Settings, cancel_token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/reservations/cancel/{cancel_token}"


def note_section(config: TableReservationsConfig, language: str | None, note: str | None) -> str:
    """The pub's message under its heading, with the blank line that separates it
    from what follows - or nothing when there is no message, so a template that
    puts {note_section} at the start of a line needs no care."""
    text = (note or "").strip()
    if not text:
        return ""
    return f"{config.note_heading(language)}\n{text}\n\n"


def template_values(
    config: TableReservationsConfig,
    settings: Settings,
    language: str | None,
    reservation: Reservation,
    *,
    table_name: str | None = None,
    note: str | None = None,
) -> dict[str, str]:
    """Every placeholder a template may use (a type may use only some of them,
    see config.allowed_placeholders)."""
    return {
        "pub_name": config.pub_name,
        "name": reservation.name,
        "email": reservation.email,
        "phone": reservation.phone or "-",
        "guest_note": reservation.note or "-",
        "table": table_name or config.kind_label(reservation.kind, language),
        "date": format_date(reservation.day, language),
        "start": format_time(reservation.start_time),
        "end": format_time(reservation.end_time),
        "party_size": str(reservation.party_size),
        "what": config.kind_label(reservation.kind, language),
        "cancel_url": cancel_url(settings, reservation.cancel_token),
        "note_section": note_section(config, language, note),
    }


async def deliver(
    config: TableReservationsConfig,
    settings: Settings,
    template_type: str,
    language: str | None,
    recipient: str,
    values: dict[str, str],
) -> tuple[bool, str | None]:
    """Renders the template in `language` and sends it to `recipient`; returns
    (True, None), or (False, why) after logging when it failed."""
    try:
        subject, body = config.template(template_type, language).render(values)
        await send_email(subject, [recipient], body, settings=settings)
    except Exception as exc:  # noqa: BLE001 - whatever the transport raises, the caller goes on
        logger.exception("Could not send the %s e-mail of a reservation", template_type)
        return False, (str(exc) or type(exc).__name__)[:ERROR_MAX]
    return True, None


def notify_address(settings: Settings) -> str:
    """Where the notice about a new reservation goes: BOOKING_NOTIFY_MAIL, else CONTACT_MAIL ('' = nowhere)."""
    return settings.booking_notify_mail.strip() or settings.contact_mail.strip()
