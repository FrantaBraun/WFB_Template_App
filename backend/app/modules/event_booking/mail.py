# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The e-mails of the booking module: building the values a template may use
and sending it. Sending never raises - an e-mail that cannot go out must not
break a booking or an administrator's change - it logs and reports (sent,
error) so the caller can record it (BookingChange.email_error, `email_sent` in
the API response)."""

import logging
from datetime import date, time

from app.config import Settings
from app.modules.event_booking.config import EventBookingConfig, normalize_language
from app.services.email import send_email

logger = logging.getLogger(__name__)

ERROR_MAX = 500


def format_date(value: date, language: str | None) -> str:
    """"20. 5. 2027" in Czech, the unambiguous ISO form (2027-05-20) in any other language."""
    if language and normalize_language(language).split("-")[0] == "cs":
        return f"{value.day}. {value.month}. {value.year}"
    return value.isoformat()


def format_time(value: time | None, config: EventBookingConfig, language: str | None) -> str:
    """HH:MM, or the language's "all day" for a whole-day slot (None)."""
    return config.all_day_label(language) if value is None else value.strftime("%H:%M")


def cancel_url(settings: Settings, cancel_token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/bookings/cancel/{cancel_token}"


def note_section(config: EventBookingConfig, language: str | None, note: str | None) -> str:
    """The administrator's note under its heading, with the blank line that
    separates it from what follows - or nothing when there is no note, so a
    template that puts {note_section} at the start of a line needs no care."""
    text = (note or "").strip()
    if not text:
        return ""
    return f"{config.note_heading(language)}\n{text}\n\n"


def template_values(
    config: EventBookingConfig,
    settings: Settings,
    language: str | None,
    *,
    name: str,
    email: str,
    event_title: str,
    registration_name: str,
    slot_date: date,
    slot_time: time | None,
    cancel_token: str,
    old_slot: tuple[date, time | None] | None = None,
    note: str | None = None,
) -> dict[str, str]:
    """Every placeholder a template may use. `old_slot` is the term before an
    administrator's change (the same one when only something else changed)."""
    old_date, old_time = old_slot or (slot_date, slot_time)
    return {
        "name": name,
        "email": email,
        "event_title": event_title,
        "registration_name": registration_name,
        "date": format_date(slot_date, language),
        "time": format_time(slot_time, config, language),
        "cancel_url": cancel_url(settings, cancel_token),
        "old_date": format_date(old_date, language),
        "old_time": format_time(old_time, config, language),
        "note_section": note_section(config, language, note),
    }


async def deliver(
    config: EventBookingConfig,
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
        logger.exception("Could not send the %s e-mail of a booking", template_type)
        return False, (str(exc) or type(exc).__name__)[:ERROR_MAX]
    return True, None


def notify_address(settings: Settings) -> str:
    """Where the notice about a new booking goes: BOOKING_NOTIFY_MAIL, else CONTACT_MAIL ('' = nowhere)."""
    return settings.booking_notify_mail.strip() or settings.contact_mail.strip()
