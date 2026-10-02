# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Level 3 and its consequences: an administrator blocks a post, and
repeated violations block the author's account.

Blocking a post removes it without any refund of what was paid for it,
tells its author why (an in-app notification carrying the administrator's
reason) and counts as a *strike*. Once an author has `strike_limit` strikes
within the last `strike_period_days` days, the account is blocked and every
post of theirs still published is removed with it - no refund either.
Those collateral removals are "removed", not "blocked": they are not strikes.
When an administrator lifts the block, the account gets a clean start:
violations from before that moment (User.strikes_reset_at) no longer count.

Everything here changes the session without committing; the caller owns the
transaction.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.boards.config import ModerationConfig
from app.modules.boards.models import STATUS_BLOCKED, STATUS_PUBLISHED, STATUS_REMOVED, Post
from app.modules.notifications.service import create_notification

REASON_REPEATED_VIOLATIONS = "repeated_violations"
REASON_ACCOUNT_BLOCKED = "account_blocked"

NOTIFICATION_POST_BLOCKED = "boards:notification.postBlocked"
NOTIFICATION_ACCOUNT_BLOCKED = "boards:notification.accountBlocked"


async def strikes_in_period(db: AsyncSession, author: User, config: ModerationConfig, now: datetime) -> int:
    """The author's posts blocked within the last strike_period_days days -
    and since their account was last unblocked, if that is more recent."""
    cutoff = now - timedelta(days=config.strike_period_days)
    if author.strikes_reset_at is not None:
        cutoff = max(cutoff, author.strikes_reset_at)
    return (
        await db.scalar(
            select(func.count())
            .select_from(Post)
            .where(Post.author_id == author.id, Post.status == STATUS_BLOCKED, Post.moderated_at >= cutoff)
        )
        or 0
    )


async def block_account(db: AsyncSession, user: User, reason: str, now: datetime) -> None:
    """Blocks the account and takes down everything of theirs that is still
    published."""
    user.is_blocked = True
    user.blocked_at = now
    user.blocked_reason = reason
    await db.execute(
        update(Post)
        .where(Post.author_id == user.id, Post.status == STATUS_PUBLISHED)
        .values(status=STATUS_REMOVED, moderation_reason=REASON_ACCOUNT_BLOCKED, moderated_at=now, moderated_by_id=None)
    )
    await create_notification(db, user.id, NOTIFICATION_ACCOUNT_BLOCKED, {})


def unblock_account(user: User, now: datetime) -> None:
    """Lifts the block and wipes the slate: earlier violations stop counting.
    Posts taken down with the block stay down."""
    user.is_blocked = False
    user.blocked_at = None
    user.blocked_reason = None
    user.strikes_reset_at = now


async def block_post(
    db: AsyncSession, post: Post, admin_id: uuid.UUID, reason: str, config: ModerationConfig, now: datetime
) -> bool:
    """Marks a published post as violating the rules: removed from the
    boards, its author told why, a strike against them. Returns whether that
    strike also blocked the author's account."""
    post.status = STATUS_BLOCKED
    post.moderation_reason = reason
    post.moderated_at = now
    post.moderated_by_id = admin_id
    await create_notification(
        db, post.author_id, NOTIFICATION_POST_BLOCKED, {"title": post.title, "reason": reason}, reference_id=post.id
    )
    await db.flush()

    author = await db.get(User, post.author_id)
    if author.is_blocked or await strikes_in_period(db, author, config, now) < config.strike_limit:
        return False
    await block_account(db, author, REASON_REPEATED_VIOLATIONS, now)
    return True
