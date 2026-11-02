# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.services.author_contact import MAX_MESSAGE_LENGTH


class AuthorOut(BaseModel):
    """The author block of ApiDocumentDetail and CollectionDetail
    (app/api/api_docs/schemas.py, app/api/collections/schemas.py). Only what
    anyone who may see the document may learn: a name (null when the author
    has neither a nickname nor a username on file) and the owning team's
    name - never the e-mail address. accepts_messages is false once the
    author has switched messages off (User.accept_author_messages): the UI
    then offers no form and the contact endpoints answer 403. is_self is
    computed against the caller, so the UI never offers someone to write to
    themselves; it is false for an anonymous caller."""

    display_name: str | None
    team_name: str | None
    accepts_messages: bool
    is_self: bool


class ContactAuthorBody(BaseModel):
    """POST .../contact-author body. Plain text, stored and shown as text
    (never rendered as HTML anywhere); surrounding whitespace is dropped
    before the length checks, so a blank message is a 422."""

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)]


class ContactAuthorResult(BaseModel):
    """email_sent is false when the author has no e-mail address on file or
    sending failed - the message itself is stored and shown to the author in
    the app either way."""

    id: uuid.UUID
    email_sent: bool


class AuthorMessageTargetOut(BaseModel):
    kind: Literal["document", "collection"]
    id: uuid.UUID
    title: str


class AuthorMessageOut(BaseModel):
    """One message the caller received, GET /api/author-messages. The
    sender's e-mail address is included (the author answers with it, exactly
    as the e-mail's Reply-To) - the sender is told so before sending."""

    id: uuid.UUID
    sender_name: str | None
    sender_email: str | None
    target: AuthorMessageTargetOut
    body: str
    created_at: datetime
