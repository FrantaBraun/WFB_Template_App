# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class NotificationMessageOut(BaseModel):
    """What a bell entry of kind "author_message" shows: who wrote, about
    what, and the first words of the text (the whole message is read on
    /messages - see GET /api/author-messages). target_title is the document's
    title or the collection's name."""

    id: uuid.UUID
    sender_name: str | None
    target_kind: Literal["document", "collection"]
    target_id: uuid.UUID
    target_title: str
    preview: str


class NotificationOut(BaseModel):
    """kind says which fields are filled: "new_version" has
    documentation_id, document_title and version (they are not columns on
    Notification itself - the router joins against
    ApiDocument/ApiDocumentVersion to populate them, since a bell dropdown or
    notification list needs to display something human-readable, not just
    the foreign keys); "author_message" has message instead and leaves those
    three null. content_changed is true for a "new_version" entry whose
    version string did not change - the spec did (see
    ApiDocumentVersion.content_changed); the UI words those differently.
    breaking_changes is how many breaking changes that version brought over
    the one it replaced (ApiDocumentVersion.change_summary), 0 when none or
    unknown."""

    id: uuid.UUID
    kind: Literal["new_version", "author_message"]
    documentation_id: uuid.UUID | None
    document_title: str | None
    version: str | None
    content_changed: bool
    breaking_changes: int
    message: NotificationMessageOut | None
    is_read: bool
    created_at: datetime


class NotificationListOut(BaseModel):
    """unread_count is always the caller's true unread total within the
    documentation_id scope (if given) - never narrowed by the unread filter
    itself. See notifications/router.py's list_notifications."""

    items: list[NotificationOut]
    unread_count: int
