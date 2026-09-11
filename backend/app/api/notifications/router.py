# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.notifications.schemas import NotificationListOut, NotificationOut
from app.database import get_db
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.notification import Notification
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    documentation_id: uuid.UUID | None = None,
    unread: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    """items is the caller's own notifications, newest first, filtered by
    documentation_id/unread if given and paginated by limit/offset.
    unread_count is the caller's is_read=false count matching
    documentation_id if given, but is deliberately never affected by the
    unread param itself - see NotificationListOut. This lets one call serve
    the header bell (no filters -> global unread badge) and another serve a
    per-document banner (documentation_id + unread=true -> both "is there
    anything new" and "what is it")."""
    unread_count_stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    )
    if documentation_id is not None:
        unread_count_stmt = unread_count_stmt.where(Notification.documentation_id == documentation_id)
    unread_count = await db.scalar(unread_count_stmt) or 0

    items_stmt = (
        select(Notification, ApiDocument.title, ApiDocumentVersion.version)
        .join(ApiDocument, ApiDocument.id == Notification.documentation_id)
        .join(ApiDocumentVersion, ApiDocumentVersion.id == Notification.version_id)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if documentation_id is not None:
        items_stmt = items_stmt.where(Notification.documentation_id == documentation_id)
    if unread is not None:
        items_stmt = items_stmt.where(Notification.is_read.is_(not unread))

    rows = (await db.execute(items_stmt)).all()
    items = [
        NotificationOut(
            id=notification.id,
            documentation_id=notification.documentation_id,
            document_title=title,
            version=version,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
        for notification, title, version in rows
    ]
    return NotificationListOut(items=items, unread_count=unread_count)


@router.post("/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """404, not 403, for a notification that doesn't exist or belongs to
    someone else - never reveal to the caller which of those it is."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == current_user.id
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """What opening the bell dropdown does - no body, no filters, every
    currently-unread notification of the caller's own in one statement."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
