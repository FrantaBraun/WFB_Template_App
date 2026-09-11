# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    """document_title/version are not columns on Notification itself - the
    router joins against ApiDocument/ApiDocumentVersion to populate them,
    since a bell dropdown or notification list needs to display something
    human-readable, not just the two foreign keys."""

    id: uuid.UUID
    documentation_id: uuid.UUID
    document_title: str
    version: str
    is_read: bool
    created_at: datetime


class NotificationListOut(BaseModel):
    """unread_count is always the caller's true unread total within the
    documentation_id scope (if given) - never narrowed by the unread filter
    itself. See notifications/router.py's list_notifications."""

    items: list[NotificationOut]
    unread_count: int
