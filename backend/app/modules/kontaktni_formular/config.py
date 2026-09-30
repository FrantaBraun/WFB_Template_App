# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Confirmation-email settings for the contact form, read from the
git-tracked backend/modules/kontaktni_formular.json rather than .env - for
the same reason as backend/modules.json (see app/modules/registry.py): the
texts are per-application content that should follow the branch, and
multi-line, per-language templates don't fit .env anyway.

Each language under `reply_templates` has a `subject` and `body` rendered
with str.format; only the placeholders in TEMPLATE_PLACEHOLDERS are allowed
(`{{` / `}}` for a literal brace). Everything is validated when the file is
loaded, so a broken template fails there rather than on a visitor's submit.
"""

import string
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import BASE_DIR

CONFIG_FILE = BASE_DIR / "modules" / "kontaktni_formular.json"

TEMPLATE_PLACEHOLDERS = frozenset({"sender_name", "reply_to", "subject", "message"})


def normalize_language(code: str) -> str:
    """Lower-cases and uses "-" ("en_US" -> "en-us"), so config keys and request values compare equal."""
    return code.strip().lower().replace("_", "-")


class ReplyTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)

    @field_validator("subject", "body")
    @classmethod
    def _only_known_placeholders(cls, template: str) -> str:
        # Checking names first also rejects attribute/index access such as
        # {message.__class__}, which a plain trial render would let through.
        for _, name, _, _ in string.Formatter().parse(template):
            if name is not None and name not in TEMPLATE_PLACEHOLDERS:
                raise ValueError(
                    f"unknown placeholder {{{name}}} - allowed: {', '.join(sorted(TEMPLATE_PLACEHOLDERS))}"
                )
        template.format(**dict.fromkeys(TEMPLATE_PLACEHOLDERS, ""))
        return template

    def render(self, *, sender_name: str, reply_to: str, subject: str, message: str) -> tuple[str, str]:
        values = {"sender_name": sender_name, "reply_to": reply_to, "subject": subject, "message": message}
        return self.subject.format(**values), self.body.format(**values)


class ContactFormConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    send_reply: bool = True
    default_language: str
    reply_templates: dict[str, ReplyTemplate] = Field(min_length=1)

    @field_validator("default_language")
    @classmethod
    def _normalize_default_language(cls, code: str) -> str:
        return normalize_language(code)

    @field_validator("reply_templates")
    @classmethod
    def _normalize_template_languages(cls, templates: dict[str, ReplyTemplate]) -> dict[str, ReplyTemplate]:
        return {normalize_language(code): template for code, template in templates.items()}

    @model_validator(mode="after")
    def _default_language_has_template(self) -> "ContactFormConfig":
        if self.default_language not in self.reply_templates:
            raise ValueError(
                f"default_language {self.default_language!r} has no entry in reply_templates "
                f"(configured: {', '.join(sorted(self.reply_templates))})"
            )
        return self

    def reply_template_for(self, language: str | None) -> ReplyTemplate:
        """The template for `language` - an exact match first ("pt-br"),
        then its primary subtag ("en-US" -> "en") - or default_language's
        when no language was sent or none of those is configured."""
        if language:
            code = normalize_language(language)
            for candidate in (code, code.split("-")[0]):
                if candidate in self.reply_templates:
                    return self.reply_templates[candidate]
        return self.reply_templates[self.default_language]


def load_contact_form_config(path: Path = CONFIG_FILE) -> ContactFormConfig:
    return ContactFormConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_contact_form_config() -> ContactFormConfig:
    """Loaded once and cached for the process lifetime, like get_settings()
    - editing the JSON needs a restart. Injected into the route via Depends
    so tests can override it the same way they override get_settings."""
    return load_contact_form_config()
