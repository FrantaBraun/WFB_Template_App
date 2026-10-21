# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Settings of the booking module, read from the git-tracked
backend/modules/event_booking.json - per-application content that follows the
branch, like backend/modules.json (see app/modules/registry.py). Per-server
values - where the administrator's notifications go (BOOKING_NOTIFY_MAIL, else
CONTACT_MAIL), the public address the cancellation link is built from
(frontend_url) - stay in .env.

- max_days_ahead: how far ahead (days from today) slots are offered.
- retention_months: bookings, their answers and their change history are
  deleted this many months after their date.
- max_active_per_email: how many upcoming confirmed bookings one e-mail
  address may hold in one registration (a light brake on abuse).
- send_confirmation / notify_admin: the e-mail to the person booking, and the
  one to the administrator about each new booking.
- privacy_url: where the consent checkbox links to (a path like /ochrana-udaju
  or an http(s) address); none = no link.
- default_language, all_day_labels, note_headings, templates: the texts of the
  e-mails. `templates.<type>.<language>.{subject,body}` for the types in
  TEMPLATE_TYPES, rendered with str.format; only the placeholders in
  PLACEHOLDERS (and, for what an administrator does, ADMIN_PLACEHOLDERS) are
  allowed (`{{` / `}}` for a literal brace). `{note_section}` is the
  administrator's note with its heading (note_headings) or nothing when there
  is no note, so a template need not care. The language of an e-mail is the one
  the person booked in, matched exactly ("pt-br"), then by primary subtag
  ("en-US" -> "en"), else default_language's.

Everything is validated when the file is loaded, so a broken template fails
there and not when someone books.
"""

import string
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import BASE_DIR

CONFIG_FILE = BASE_DIR / "modules" / "event_booking.json"

TEMPLATE_TYPES = ("confirmation", "admin_notification", "cancellation", "changed", "cancelled_by_admin")
PLACEHOLDERS = frozenset({"name", "email", "event_title", "registration_name", "date", "time", "cancel_url"})
ADMIN_PLACEHOLDERS = frozenset({"old_date", "old_time", "note_section"})
TYPES_WITH_ADMIN_PLACEHOLDERS = frozenset({"changed", "cancelled_by_admin"})


def normalize_language(code: str) -> str:
    """Lower-cases and uses "-" ("en_US" -> "en-us"), so config keys and request values compare equal."""
    return code.strip().lower().replace("_", "-")


def for_language(items: dict, language: str | None):
    """The entry for `language` - an exact match first ("pt-br"), then its
    primary subtag ("en-US" -> "en") - or None when there is none."""
    if language:
        code = normalize_language(language)
        for candidate in (code, code.split("-")[0]):
            if candidate in items:
                return items[candidate]
    return None


def allowed_placeholders(template_type: str) -> frozenset[str]:
    return PLACEHOLDERS | (ADMIN_PLACEHOLDERS if template_type in TYPES_WITH_ADMIN_PLACEHOLDERS else frozenset())


class MailTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)

    def check(self, template_type: str) -> None:
        allowed = allowed_placeholders(template_type)
        for text in (self.subject, self.body):
            # Checking the names first also rejects attribute/index access such
            # as {name.__class__}, which a plain trial render would let through.
            for _, field_name, _, _ in string.Formatter().parse(text):
                if field_name is not None and field_name not in allowed:
                    raise ValueError(f"unknown placeholder {{{field_name}}} in a {template_type} template - allowed: {', '.join(sorted(allowed))}")
            text.format(**dict.fromkeys(allowed, ""))

    def render(self, values: dict[str, str]) -> tuple[str, str]:
        return self.subject.format(**values), self.body.format(**values)


class EventBookingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_days_ahead: int = Field(default=365, ge=1, le=1000)
    retention_months: int = Field(default=12, ge=1, le=120)
    max_active_per_email: int = Field(default=5, ge=1, le=100)
    send_confirmation: bool = True
    notify_admin: bool = True
    privacy_url: str | None = None
    default_language: str
    all_day_labels: dict[str, str] = Field(min_length=1)
    note_headings: dict[str, str] = Field(min_length=1)
    templates: dict[str, dict[str, MailTemplate]]

    @field_validator("default_language")
    @classmethod
    def _normalize_default_language(cls, code: str) -> str:
        return normalize_language(code)

    @field_validator("privacy_url")
    @classmethod
    def _privacy_url_is_a_path_or_http(cls, url: str | None) -> str | None:
        if url is None or url.strip() == "":
            return None
        url = url.strip()
        if not (url.startswith("https://") or url.startswith("http://") or (url.startswith("/") and not url.startswith("//"))):
            raise ValueError("privacy_url must be a site path (/…) or an http(s) address")
        return url

    @field_validator("all_day_labels", "note_headings")
    @classmethod
    def _normalize_text_languages(cls, texts: dict[str, str]) -> dict[str, str]:
        return {normalize_language(code): text for code, text in texts.items()}

    @model_validator(mode="after")
    def _templates_are_complete_and_valid(self) -> "EventBookingConfig":
        unknown = set(self.templates) - set(TEMPLATE_TYPES)
        missing = set(TEMPLATE_TYPES) - set(self.templates)
        if unknown or missing:
            raise ValueError(f"templates must have exactly {', '.join(TEMPLATE_TYPES)} (unknown: {sorted(unknown)}, missing: {sorted(missing)})")
        normalized: dict[str, dict[str, MailTemplate]] = {}
        for template_type, by_language in self.templates.items():
            normalized[template_type] = {normalize_language(code): template for code, template in by_language.items()}
            if self.default_language not in normalized[template_type]:
                raise ValueError(f"{template_type}: default_language {self.default_language!r} has no template")
            for template in normalized[template_type].values():
                template.check(template_type)
        self.templates = normalized
        for name, texts in (("all_day_labels", self.all_day_labels), ("note_headings", self.note_headings)):
            if self.default_language not in texts:
                raise ValueError(f"{name}: default_language {self.default_language!r} has no entry")
        return self

    def resolve_language(self, language: str | None) -> str:
        """The configured language an e-mail in `language` is written in."""
        for candidate in (normalize_language(language), normalize_language(language).split("-")[0]) if language else ():
            if candidate in self.templates["confirmation"]:
                return candidate
        return self.default_language

    def template(self, template_type: str, language: str | None) -> MailTemplate:
        return for_language(self.templates[template_type], language) or self.templates[template_type][self.default_language]

    def all_day_label(self, language: str | None) -> str:
        return for_language(self.all_day_labels, language) or self.all_day_labels[self.default_language]

    def note_heading(self, language: str | None) -> str:
        return for_language(self.note_headings, language) or self.note_headings[self.default_language]


def load_config(path: Path = CONFIG_FILE) -> EventBookingConfig:
    return EventBookingConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> EventBookingConfig:
    return load_config()
