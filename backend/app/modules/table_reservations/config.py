# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Settings of the table reservations module, read from the git-tracked
backend/modules/table_reservations.json - per-application content that follows
the branch, like backend/modules.json (see app/modules/registry.py). Per-server
values - where the notice about a new reservation goes (BOOKING_NOTIFY_MAIL, else
CONTACT_MAIL) and the public address the cancellation link is built from
(frontend_url) - stay in .env.

- max_days_ahead: how many days ahead (from today) a table can be reserved.
- lead_minutes: how long before the start (today) the latest reservation may be made.
- default_duration / duration_options: the length of a table reservation in
  minutes the form offers first / lets the guest choose from (each a multiple of
  rules.STEP_MINUTES within MIN_DURATION..MAX_DURATION, the default among them).
- max_active_per_email: how many upcoming confirmed reservations one e-mail
  address may hold (a light brake on abuse; there is no rate limiting).
- retention_months: reservations, with the personal data in them, are deleted
  this many months after their day.
- send_confirmation / notify_admin: the e-mail to the guest, and the one to the
  pub about each new reservation.
- privacy_url: where the consent checkbox links to (a path like /ochrana-udaju or
  an http(s) address); none = no link.
- pub_name, default_language, kind_labels, note_headings, templates: the texts of
  the e-mails. `templates.<type>.<language>.{subject,body}` for the types in
  TEMPLATE_TYPES, rendered with str.format; only the placeholders allowed for the
  type (see allowed_placeholders; `{{` / `}}` for a literal brace) may be used.
  `{note_section}` (the pub's cancellation message under its heading from
  note_headings, or nothing) is only for "cancelled_by_admin", so a template need
  not care whether there is a message. The language of an e-mail is the one the guest
  reserved in, matched exactly ("pt-br"), then by primary subtag ("en-US" ->
  "en"), else default_language's.

Everything is validated when the file is loaded, so a broken template fails there
and not when someone reserves.
"""

import string
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import BASE_DIR
from app.modules.table_reservations import rules
from app.modules.table_reservations.models import KINDS

CONFIG_FILE = BASE_DIR / "modules" / "table_reservations.json"

TEMPLATE_TYPES = ("confirmation", "admin_notification", "cancellation", "cancelled_by_admin")
BASE_PLACEHOLDERS = frozenset({"pub_name", "name", "email", "date", "start", "end", "party_size", "what", "cancel_url"})
EXTRA_PLACEHOLDERS = {
    "admin_notification": frozenset({"phone", "guest_note", "table"}),
    "cancelled_by_admin": frozenset({"note_section"}),
}


def normalize_language(code: str) -> str:
    """Lower-cases and uses "-" ("en_US" -> "en-us"), so config keys and request values compare equal."""
    return code.strip().lower().replace("_", "-")


def for_language(items: dict, language: str | None):
    """The entry for `language` - an exact match first ("pt-br"), then its primary
    subtag ("en-US" -> "en") - or None when there is none."""
    if language:
        code = normalize_language(language)
        for candidate in (code, code.split("-")[0]):
            if candidate in items:
                return items[candidate]
    return None


def allowed_placeholders(template_type: str) -> frozenset[str]:
    return BASE_PLACEHOLDERS | EXTRA_PLACEHOLDERS.get(template_type, frozenset())


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


class TableReservationsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_days_ahead: int = Field(default=90, ge=1, le=365)
    lead_minutes: int = Field(default=30, ge=0, le=1440)
    default_duration: int = rules.DEFAULT_DURATION
    duration_options: list[int] = Field(default_factory=lambda: [60, 90, 120, 150, 180, 240], min_length=1)
    max_active_per_email: int = Field(default=3, ge=1, le=100)
    retention_months: int = Field(default=12, ge=1, le=120)
    send_confirmation: bool = True
    notify_admin: bool = True
    privacy_url: str | None = None
    pub_name: str = Field(min_length=1, max_length=200)
    default_language: str
    kind_labels: dict[str, dict[str, str]] = Field(min_length=1)
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

    @field_validator("duration_options")
    @classmethod
    def _durations_are_valid(cls, options: list[int]) -> list[int]:
        for minutes in options:
            if not rules.MIN_DURATION <= minutes <= rules.MAX_DURATION or minutes % rules.STEP_MINUTES:
                raise ValueError(f"duration {minutes} must be a multiple of {rules.STEP_MINUTES} within {rules.MIN_DURATION}..{rules.MAX_DURATION} minutes")
        return sorted(set(options))

    @field_validator("note_headings")
    @classmethod
    def _normalize_note_headings(cls, texts: dict[str, str]) -> dict[str, str]:
        return {normalize_language(code): text for code, text in texts.items()}

    @field_validator("kind_labels")
    @classmethod
    def _normalize_kind_labels(cls, labels: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        for code, by_kind in labels.items():
            if set(by_kind) != set(KINDS):
                raise ValueError(f"kind_labels.{code} must have exactly {', '.join(KINDS)}")
        return {normalize_language(code): by_kind for code, by_kind in labels.items()}

    @model_validator(mode="after")
    def _templates_are_complete_and_valid(self) -> "TableReservationsConfig":
        if self.default_duration not in self.duration_options:
            raise ValueError(f"default_duration {self.default_duration} must be one of duration_options {self.duration_options}")
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
        for name, texts in (("kind_labels", self.kind_labels), ("note_headings", self.note_headings)):
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

    def kind_label(self, kind: str, language: str | None) -> str:
        return (for_language(self.kind_labels, language) or self.kind_labels[self.default_language])[kind]

    def note_heading(self, language: str | None) -> str:
        return for_language(self.note_headings, language) or self.note_headings[self.default_language]


def load_config(path: Path = CONFIG_FILE) -> TableReservationsConfig:
    return TableReservationsConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> TableReservationsConfig:
    return load_config()
