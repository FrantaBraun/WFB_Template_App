# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationListOut, NotificationOut

router = APIRouter()


@router.get("")
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    unread: bool | None = None,
    reference_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    """unread_count is always the caller's true unread total within the
    reference_id scope (if given), but is deliberately never affected by the
    unread filter itself - this lets one call serve the header bell (no
    filters -> global unread badge) and another serve a scoped view
    (reference_id + unread=true -> both "is there anything new" and "what is
    it")."""
    unread_count_stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    )
    if reference_id is not None:
        unread_count_stmt = unread_count_stmt.where(Notification.reference_id == reference_id)
    unread_count = await db.scalar(unread_count_stmt) or 0

    items_stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if reference_id is not None:
        items_stmt = items_stmt.where(Notification.reference_id == reference_id)
    if unread is not None:
        items_stmt = items_stmt.where(Notification.is_read.is_(not unread))

    notifications = (await db.scalars(items_stmt)).all()
    items = [NotificationOut.model_validate(n) for n in notifications]
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
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
