# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The hook other modules use to take part in a contact form submission.

A module declares `hooks={CONTACT_FORM_RECEIVED: handler}` in its manifest
(see app.modules.base.ModuleManifest); the router below calls every *enabled*
module's handler as `await handler(db, submission)` before it sends any mail,
and the handler returns a ContactHookResult (or None). This module never
imports the modules that use it - the tickets module turns a message into a
ticket this way, and anything else can follow.

A handler runs inside the request's database session and commits its own
work. One that raises is logged and skipped (see router._run_hooks): a
contact form message must never be lost because something built on top of it
failed.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.modules.registry import get_enabled_hooks

CONTACT_FORM_RECEIVED = "contact_form.received"


@dataclass(frozen=True)
class ContactSubmission:
    """What a hook gets to see. `sender_name` is the real name of a signed-in
    sender, else their address (as in the message sent to the owner);
    `reply_to` is "" for a signed-in sender whose account has no address."""

    subject: str
    message: str
    sender_name: str
    reply_to: str
    language: str | None
    signed_in: bool


@dataclass(frozen=True)
class ContactHookResult:
    """What a hook may change about the mail the router sends.

    `subject_tag` is put in front of the subject of every mail about this
    submission as "<tag> - <subject>" (e.g. "[Ticket#100253]"), `reply_to`
    becomes the Reply-To of the confirmation to the sender, so that their
    answer lands where the hook's module reads it."""

    subject_tag: str | None = None
    reply_to: str | None = None


ContactFormHook = Callable[..., Awaitable[ContactHookResult | None]]


def get_contact_form_hooks() -> list[ContactFormHook]:
    """FastAPI dependency: the enabled modules' handlers. A dependency (not a
    direct call in the route) so tests can pin it to none and never depend on
    the modules a branch has switched on."""
    return get_enabled_hooks(CONTACT_FORM_RECEIVED)
