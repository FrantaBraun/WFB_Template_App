# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_key: str
    message_params: dict
    link_url: str | None
    is_read: bool
    created_at: datetime


class NotificationListOut(BaseModel):
    """unread_count is always the caller's true unread total within the
    reference_id scope (if given) - never narrowed by the unread filter
    itself. See router.py's list_notifications."""

    items: list[NotificationOut]
    unread_count: int
