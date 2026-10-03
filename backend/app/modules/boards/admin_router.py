# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The administrators' side of moderation, mounted under /manage.

Administrators are this application's own: the local User.is_admin flag
(app.api.deps.require_admin), never the auth service's role. They can find
any post, block it with a reason (level 3 of the content checks - see
moderation/enforcement.py) or restore a blocked one, read and edit a category's machine rules, and
lift an account block. They can also block a whole category (and restore
it). This is the only place an author's or a creator's id is ever returned:
following up on repeat violations needs it.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards import receipts
from app.modules.boards.models import STATUS_BLOCKED, STATUS_PUBLISHED, Category, Post, Receipt
from app.modules.boards.moderation import enforcement
from app.modules.boards.moderation.ai import AiModerator, get_ai_moderator
from app.modules.boards.schemas import (
    AdminCategoryOut,
    AdminCategoryPage,
    AdminPostOut,
    AdminPostPage,
    AdminReceiptOut,
    BlockCategoryIn,
    BlockedUserOut,
    BlockPostIn,
    BlockPostOut,
    MachineRules,
    RetryOut,
    RulesOut,
)
from app.modules.boards.service import make_machine_rules
from app.modules.boards.views import admin_category_out, admin_post_out, admin_receipt_out, get_category

router = APIRouter(dependencies=[Depends(require_admin)])

_BLOCKED_USERS_LIMIT = 100


def _like_pattern(text: str) -> str:
    """`text` as a literal inside an ILIKE pattern (escape character \\)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --- Posts --------------------------------------------------------------------


@router.get("/posts")
async def find_posts(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=140),
    status: Literal["published", "blocked", "removed", "all"] = "published",
    min_score: int | None = Query(default=None, ge=0, le=100),
    sort: Literal["new", "score"] = "new",
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> AdminPostPage:
    """Any post, in any state: filter by words in the title or text, by
    category, by state and by the worse of its two scores; newest first, or
    highest score first for a review queue."""
    score = func.greatest(Post.violation_score, Post.topic_mismatch_score)
    query = (
        select(Post, Category, User.is_blocked)
        .join(Category, Category.id == Post.category_id)
        .join(User, User.id == Post.author_id)
    )
    if q:
        pattern = _like_pattern(q)
        query = query.where(Post.title.ilike(pattern, escape="\\") | Post.body.ilike(pattern, escape="\\"))
    if category:
        query = query.where(Category.slug == category)
    if status != "all":
        query = query.where(Post.status == status)
    if min_score is not None:
        query = query.where(score >= min_score)
    order = [Post.created_at.desc(), Post.id.desc()]
    if sort == "score":
        order = [score.desc(), *order]
    rows = (await db.execute(query.order_by(*order).offset(offset).limit(config.page_size + 1))).all()

    now = datetime.now(timezone.utc)
    return AdminPostPage(
        items=[
            admin_post_out(post, cat, config, author_blocked=author_blocked, now=now)
            for post, cat, author_blocked in rows[: config.page_size]
        ],
        has_more=len(rows) > config.page_size,
    )


@router.post("/posts/{post_id}/block")
async def block_post(
    post_id: uuid.UUID,
    body: BlockPostIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> BlockPostOut:
    """Marks a published post as violating the public rules: removed with no
    refund, its author notified with `reason`, and a strike against them -
    which may block their account (`account_blocked` in the answer)."""
    # Locked, so two administrators blocking the same post can't both notify
    # the author and both count a strike.
    post = (await db.scalars(select(Post).where(Post.id == post_id).with_for_update())).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != STATUS_PUBLISHED:
        raise HTTPException(status_code=409, detail="Post is not published")

    now = datetime.now(timezone.utc)
    account_blocked = await enforcement.block_post(db, post, admin.id, body.reason, config.moderation, now)
    await db.commit()

    category = await db.get(Category, post.category_id)
    author = await db.get(User, post.author_id)
    await db.refresh(post)
    return BlockPostOut(
        post=admin_post_out(post, category, config, author_blocked=author.is_blocked, now=now),
        account_blocked=account_blocked,
    )


@router.post("/posts/{post_id}/restore")
async def restore_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> AdminPostOut:
    """Undoes a block: publishes a blocked - or removed - post again, tells
    its author, and stops counting it as a violation (so it may also keep the
    author's account clear of the strike limit). It keeps what was paid for
    it. Refused while its author's account is blocked: that comes first, as
    a published post of a blocked account would contradict the block."""
    # Locked, like blocking: two administrators can't both notify the author.
    post = (await db.scalars(select(Post).where(Post.id == post_id).with_for_update())).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == STATUS_PUBLISHED:
        raise HTTPException(status_code=409, detail="Post is not blocked")
    author = await db.get(User, post.author_id)
    if author.is_blocked:
        raise HTTPException(status_code=409, detail={"code": "author_blocked"})

    await enforcement.restore_post(db, post)
    await db.commit()

    category = await db.get(Category, post.category_id)
    await db.refresh(post)
    return admin_post_out(post, category, config, author_blocked=False, now=datetime.now(timezone.utc))


# --- Categories ---------------------------------------------------------------


async def _published_posts(db: AsyncSession, category: Category) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Post)
            .where(Post.category_id == category.id, Post.status == STATUS_PUBLISHED)
        )
        or 0
    )


@router.get("/categories")
async def find_categories(
    q: str | None = Query(default=None, max_length=100),
    status: Literal["published", "blocked", "all"] = "all",
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> AdminCategoryPage:
    """Every category, blocked ones included (the public list leaves them
    out): filter by words in the title or the address and by state; newest
    first."""
    post_count = func.count(Post.id)
    query = (
        select(Category, post_count)
        .outerjoin(Post, and_(Post.category_id == Category.id, Post.status == STATUS_PUBLISHED))
        .group_by(Category.id)
    )
    if q:
        pattern = _like_pattern(q)
        query = query.where(Category.title.ilike(pattern, escape="\\") | Category.slug.ilike(pattern, escape="\\"))
    if status != "all":
        query = query.where(Category.status == status)
    rows = (
        await db.execute(
            query.order_by(Category.created_at.desc(), Category.id.desc()).offset(offset).limit(config.page_size + 1)
        )
    ).all()
    return AdminCategoryPage(
        items=[admin_category_out(category, count) for category, count in rows[: config.page_size]],
        has_more=len(rows) > config.page_size,
    )


@router.post("/categories/{slug}/block")
async def block_category(
    slug: str,
    body: BlockCategoryIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCategoryOut:
    """Takes a whole category off the boards: hidden from every visitor, no
    new posts, resonances or payments in it, its creator told why. Nothing in
    it is changed or deleted - the posts keep what was paid for them, and
    restoring the category brings everything back."""
    # Locked, so two administrators can't both notify the creator.
    category = (await db.scalars(select(Category).where(Category.slug == slug).with_for_update())).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.status == STATUS_BLOCKED:
        raise HTTPException(status_code=409, detail="Category is already blocked")

    await enforcement.block_category(db, category, admin.id, body.reason, datetime.now(timezone.utc))
    await db.commit()
    await db.refresh(category)
    return admin_category_out(category, await _published_posts(db, category))


@router.post("/categories/{slug}/restore")
async def restore_category(slug: str, db: AsyncSession = Depends(get_db)) -> AdminCategoryOut:
    """Puts a blocked category back on the boards exactly as it was, and
    tells its creator."""
    category = (await db.scalars(select(Category).where(Category.slug == slug).with_for_update())).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.status != STATUS_BLOCKED:
        raise HTTPException(status_code=409, detail="Category is not blocked")

    await enforcement.restore_category(db, category)
    await db.commit()
    await db.refresh(category)
    return admin_category_out(category, await _published_posts(db, category))


# --- Payment documents --------------------------------------------------------


@router.get("/receipts")
async def list_receipts(
    unsent: bool = False, db: AsyncSession = Depends(get_db)
) -> list[AdminReceiptOut]:
    """Recent payment documents with their delivery state; `unsent=true` for
    the ones whose confirmation email has not gone out (or has no recipient)."""
    query = select(Receipt).order_by(Receipt.issued_at.desc()).limit(100)
    if unsent:
        query = query.where(Receipt.emailed_at.is_(None))
    return [admin_receipt_out(receipt) for receipt in await db.scalars(query)]


@router.post("/receipts/retry")
async def retry_receipts(db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> RetryOut:
    """Tries every unsent confirmation email again, however many times it has
    failed before - after the mail server was down, say."""
    return RetryOut(**await receipts.retry_unsent(db, settings))


# --- Machine rules ------------------------------------------------------------


def _rules_out(category: Category) -> RulesOut:
    rules = MachineRules.model_validate(category.machine_rules or {"keywords": [], "notes": ""})
    return RulesOut(rules=rules, source=category.machine_rules_source, updated_at=category.machine_rules_updated_at)


@router.get("/categories/{slug}/rules")
async def read_rules(slug: str, db: AsyncSession = Depends(get_db)) -> RulesOut:
    """The category's machine rules (empty for a category that has none)."""
    return _rules_out(await get_category(db, slug, include_blocked=True))


@router.put("/categories/{slug}/rules")
async def write_rules(slug: str, body: MachineRules, db: AsyncSession = Depends(get_db)) -> RulesOut:
    """Replaces the machine rules with the administrator's own. An empty
    keyword list switches the topic check off for the category."""
    category = await get_category(db, slug, include_blocked=True)
    category.machine_rules = body.model_dump()
    category.machine_rules_source = "admin"
    category.machine_rules_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _rules_out(category)


@router.post("/categories/{slug}/rules/rebuild")
async def rebuild_rules(
    slug: str,
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
    ai: AiModerator = Depends(get_ai_moderator),
) -> RulesOut:
    """Throws away the current rules (an administrator's edits included) and
    builds them again from the category's title and description."""
    category = await get_category(db, slug, include_blocked=True)
    rules, source = await make_machine_rules(category.title, category.description, config.moderation, ai)
    category.machine_rules = rules
    category.machine_rules_source = source
    category.machine_rules_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _rules_out(category)


# --- Blocked accounts ---------------------------------------------------------


@router.get("/users/blocked")
async def list_blocked_users(db: AsyncSession = Depends(get_db)) -> list[BlockedUserOut]:
    """Accounts this application has blocked, most recent first. Ids only -
    nothing here identifies a person beyond what the post list already did."""
    users = (
        await db.scalars(
            select(User).where(User.is_blocked.is_(True)).order_by(User.blocked_at.desc()).limit(_BLOCKED_USERS_LIMIT)
        )
    ).all()
    return [BlockedUserOut(id=u.id, blocked_at=u.blocked_at, blocked_reason=u.blocked_reason) for u in users]


@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BlockedUserOut:
    """Lifts an account block and gives the account a clean start (earlier
    violations stop counting). The posts taken down with it stay down until
    an administrator restores them one by one."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_blocked:
        raise HTTPException(status_code=409, detail="User is not blocked")
    enforcement.unblock_account(user, datetime.now(timezone.utc))
    await db.commit()
    return BlockedUserOut(id=user.id, blocked_at=user.blocked_at, blocked_reason=user.blocked_reason)
