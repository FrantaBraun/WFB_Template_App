# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    message_key: str,
    message_params: dict | None = None,
    link_url: str | None = None,
    reference_id: uuid.UUID | None = None,
) -> Notification:
    """Adds the row to the session without committing - the caller controls
    the transaction boundary, e.g. to batch many recipients into one commit."""
    notification = Notification(
        user_id=user_id,
        message_key=message_key,
        message_params=message_params if message_params is not None else {},
        link_url=link_url,
        reference_id=reference_id,
    )
    db.add(notification)
    return notification
