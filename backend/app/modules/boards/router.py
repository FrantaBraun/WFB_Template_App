# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Categories (boards), their posts and resonances.

Reading is public; creating a category or a post and resonating need a
signed-in user. Nothing here ever returns who wrote a post or created a
category, or who resonated (see schemas.PostOut) - those ids are stored for
moderation only.

This is the first phase: there are no payments yet (Post.paid_cents stays
0) and no content checks, so anything a signed-in user submits within the
length limits is published.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards.deps import get_optional_user
from app.modules.boards.models import Category, Post, Resonance
from app.modules.boards.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryPage,
    PostCreate,
    PostOut,
    PostPage,
)
from app.modules.boards.service import post_value, rank_expression, unique_slug

router = APIRouter()

# unique_slug() can lose a race to a concurrent request with the same title.
_SLUG_ATTEMPTS = 5


def _category_out(category: Category, post_count: int) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        title=category.title,
        slug=category.slug,
        description=category.description,
        post_count=post_count,
        created_at=category.created_at,
    )


def _post_out(post: Post, config: BoardsConfig, *, resonated: bool, now: datetime | None = None) -> PostOut:
    return PostOut(
        id=post.id,
        title=post.title,
        body=post.body,
        value=post_value(
            post.paid_cents, post.resonance_count, post.created_at, now or datetime.now(timezone.utc), config
        ),
        resonance_count=post.resonance_count,
        resonated_by_me=resonated,
        created_at=post.created_at,
    )


async def _get_category(db: AsyncSession, slug: str) -> Category:
    category = (await db.scalars(select(Category).where(Category.slug == slug))).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


# --- Categories ---------------------------------------------------------------


@router.get("/categories")
async def list_categories(
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> CategoryPage:
    """Busiest categories first (most posts), then by title; the client asks
    for the next page via offset."""
    post_count = func.count(Post.id)
    rows = (
        await db.execute(
            select(Category, post_count)
            .outerjoin(Post, Post.category_id == Category.id)
            .group_by(Category.id)
            .order_by(post_count.desc(), Category.title.asc(), Category.id.asc())
            .offset(offset)
            .limit(config.page_size + 1)
        )
    ).all()
    return CategoryPage(
        items=[_category_out(category, count) for category, count in rows[: config.page_size]],
        has_more=len(rows) > config.page_size,
    )


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    # Read now: the rollback below expires every loaded object, and touching
    # `user.id` afterwards would try a lazy load, which async sessions can't do.
    user_id = user.id
    for _ in range(_SLUG_ATTEMPTS):
        category = Category(
            title=body.title,
            slug=await unique_slug(db, body.title),
            description=body.description,
            created_by_id=user_id,
        )
        db.add(category)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()  # the slug was taken meanwhile - pick again
            continue
        await db.refresh(category)
        return _category_out(category, 0)
    raise HTTPException(status_code=409, detail="Could not find a free address for the category, try again")


@router.get("/categories/{slug}")
async def get_category(slug: str, db: AsyncSession = Depends(get_db)) -> CategoryOut:
    category = await _get_category(db, slug)
    post_count = await db.scalar(select(func.count()).select_from(Post).where(Post.category_id == category.id))
    return _category_out(category, post_count or 0)


# --- Posts --------------------------------------------------------------------


@router.get("/categories/{slug}/posts")
async def list_posts(
    slug: str,
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> PostPage:
    """The category's posts, highest value first - the page the frontend
    scrolls endlessly by asking for the next offset."""
    category = await _get_category(db, slug)
    if user is None:
        resonated = literal(False)
    else:
        resonated = exists().where(Resonance.post_id == Post.id, Resonance.user_id == user.id)
    rows = (
        await db.execute(
            select(Post, resonated.label("resonated"))
            .where(Post.category_id == category.id)
            .order_by(rank_expression(config).desc(), Post.id.desc())
            .offset(offset)
            .limit(config.page_size + 1)
        )
    ).all()
    now = datetime.now(timezone.utc)
    return PostPage(
        items=[_post_out(post, config, resonated=bool(flag), now=now) for post, flag in rows[: config.page_size]],
        has_more=len(rows) > config.page_size,
    )


@router.post("/categories/{slug}/posts", status_code=201)
async def create_post(
    slug: str,
    body: PostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> PostOut:
    category = await _get_category(db, slug)
    post = Post(category_id=category.id, author_id=user.id, title=body.title, body=body.body)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _post_out(post, config, resonated=False)


@router.post("/posts/{post_id}/resonance")
async def add_resonance(
    post_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> PostOut:
    """One resonance (+1 by default) per user and post, ever. The insert
    decides whether this one counts - the primary key plus ON CONFLICT DO
    NOTHING keeps two simultaneous requests from both counting - and the
    counter only moves when it did."""
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    inserted = await db.scalar(
        pg_insert(Resonance)
        .values(post_id=post.id, user_id=user.id)
        .on_conflict_do_nothing()
        .returning(Resonance.post_id)
    )
    if inserted is None:
        raise HTTPException(status_code=409, detail="You have already resonated with this post")

    await db.execute(update(Post).where(Post.id == post.id).values(resonance_count=Post.resonance_count + 1))
    await db.commit()
    await db.refresh(post)
    return _post_out(post, config, resonated=True)
