# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Categories (boards), their posts and resonances.

Reading is public; creating a category or a post and resonating need a
signed-in user whose account is not blocked. Nothing here ever returns who
wrote a post or created a category, or who resonated (see schemas.PostOut) -
those ids are stored for moderation only.

Nothing is published unchecked: a new post or category is assessed first
(moderation/assess.py) - not allowed above the block threshold, published
only on the author's explicit confirmation above the risk threshold - and
the same assessment is available on its own (the /check endpoints) so the
frontend can show the author the verdict before they commit. Once payments
exist, this is the check that runs before a payment is confirmed.

An author can pay to raise their own post's value (payments.py, through the
stripe_payment_gate module); GET /payments tells the frontend whether that is
switched on. The administrators' endpoints live in admin_router.py and are
mounted under /manage.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import and_, exists, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.boards.admin_router import router as admin_router
from app.modules.boards.config import BoardsConfig, get_config
from app.modules.boards.deps import get_active_user, get_optional_user
from app.modules.boards import documents, receipts
from app.modules.boards.models import STATUS_PUBLISHED, Category, Post, Receipt, Resonance
from app.modules.boards.payments import CURRENCY
from app.modules.boards.moderation.ai import AiModerator, get_ai_moderator
from app.modules.boards.moderation.assess import Assessment, assess_category, assess_post
from app.modules.boards.schemas import (
    AssessmentOut,
    CategoryCreate,
    CategoryOut,
    CategoryPage,
    MeOut,
    MyPostPage,
    PaymentsInfo,
    PostCreate,
    PostOut,
    PostPage,
    ReceiptOut,
)
from app.modules.boards.service import make_machine_rules, rank_expression, unique_slug
from app.modules.boards.views import assessment_out, category_out, get_category, my_post_out, post_out, receipt_out
from app.modules.registry import load_enabled_module_keys

router = APIRouter()

# unique_slug() can lose a race to a concurrent request with the same title.
_SLUG_ATTEMPTS = 5


def enforce(assessment: Assessment, confirm_risk: bool) -> None:
    """Refuses what the checks do not let through: 422 {"code":
    "moderation_blocked"} above the block threshold, and 409 {"code":
    "confirmation_required"} at risk level unless the author already
    confirmed - both carry the whole assessment so the author can see why."""
    if assessment.level == "blocked":
        raise HTTPException(
            status_code=422,
            detail={"code": "moderation_blocked", "assessment": assessment_out(assessment).model_dump(mode="json")},
        )
    if assessment.level == "risk" and not confirm_risk:
        raise HTTPException(
            status_code=409,
            detail={"code": "confirmation_required", "assessment": assessment_out(assessment).model_dump(mode="json")},
        )


async def _assess_post(category: Category, body: PostCreate, config: BoardsConfig, ai: AiModerator) -> Assessment:
    return await assess_post(
        title=body.title,
        body=body.body,
        category_title=category.title,
        category_description=category.description,
        category_rules=category.machine_rules,
        config=config.moderation,
        ai=ai,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> MeOut:
    """The signed-in user's standing here: whether they administer this
    application and whether it has blocked their account."""
    return MeOut(is_admin=user.is_admin, blocked=user.is_blocked, blocked_reason=user.blocked_reason)


@router.get("/me/posts")
async def my_posts(
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> MyPostPage:
    """The signed-in user's own posts in every state, newest first - the one
    place an author finds their anonymous posts again (to raise their value,
    or to see that one was blocked). A blocked account may still look."""
    rows = (
        await db.execute(
            select(Post, Category)
            .join(Category, Category.id == Post.category_id)
            .where(Post.author_id == user.id)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .offset(offset)
            .limit(config.page_size + 1)
        )
    ).all()
    now = datetime.now(timezone.utc)
    return MyPostPage(
        items=[my_post_out(post, category, config, now=now) for post, category in rows[: config.page_size]],
        has_more=len(rows) > config.page_size,
    )


@router.get("/me/receipts")
async def my_receipts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[ReceiptOut]:
    """The signed-in user's payment documents, newest first."""
    rows = await db.scalars(select(Receipt).where(Receipt.user_id == user.id).order_by(Receipt.issued_at.desc()).limit(100))
    return [receipt_out(receipt) for receipt in rows]


@router.get("/me/receipts/{receipt_id}/document")
async def my_receipt_document(
    receipt_id: uuid.UUID,
    language: str | None = Query(default=None, max_length=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """A payment document as a complete HTML page, in its own language or
    the one asked for. Only its payer may read it; anyone else gets 404."""
    receipt = await db.get(Receipt, receipt_id)
    if receipt is None or receipt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    return HTMLResponse(documents.render_page(receipt.document, language))


def gateway_enabled(settings: Settings = Depends(get_settings)) -> bool:
    """Payments work only where the gateway module is switched on in
    modules.json and its Stripe keys are set - otherwise its endpoints answer
    404 or 503."""
    return "stripe_payment_gate" in load_enabled_module_keys() and bool(
        settings.stripe_secret_key and settings.stripe_webhook_secret
    )


@router.get("/payments")
async def payments_info(
    enabled: bool = Depends(gateway_enabled), config: BoardsConfig = Depends(get_config)
) -> PaymentsInfo:
    """Public: whether authors can pay to raise a post's value here, and the
    limits of one payment. Off until the provider's details (who issues the
    payment documents) are filled in."""
    return PaymentsInfo(
        enabled=enabled and receipts.provider_ready(config),
        currency=CURRENCY,
        min_amount_usd=config.payments.min_amount_usd,
        max_amount_usd=config.payments.max_amount_usd,
        points_per_usd=config.points_per_usd,
    )


# --- Categories ---------------------------------------------------------------


@router.get("/categories")
async def list_categories(
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> CategoryPage:
    """Busiest categories first (most published posts), then by title; the
    client asks for the next page via offset."""
    post_count = func.count(Post.id)
    rows = (
        await db.execute(
            select(Category, post_count)
            .outerjoin(Post, and_(Post.category_id == Category.id, Post.status == STATUS_PUBLISHED))
            .group_by(Category.id)
            .order_by(post_count.desc(), Category.title.asc(), Category.id.asc())
            .offset(offset)
            .limit(config.page_size + 1)
        )
    ).all()
    return CategoryPage(
        items=[category_out(category, count) for category, count in rows[: config.page_size]],
        has_more=len(rows) > config.page_size,
    )


@router.post("/categories/check")
async def check_category(
    body: CategoryCreate,
    user: User = Depends(get_active_user),
    config: BoardsConfig = Depends(get_config),
    ai: AiModerator = Depends(get_ai_moderator),
) -> AssessmentOut:
    """The verdict on a draft category, without creating it."""
    return assessment_out(await assess_category(title=body.title, description=body.description, config=config.moderation, ai=ai))


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreate,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
    ai: AiModerator = Depends(get_ai_moderator),
) -> CategoryOut:
    assessment = await assess_category(title=body.title, description=body.description, config=config.moderation, ai=ai)
    enforce(assessment, body.confirm_risk)
    rules, rules_source = await make_machine_rules(body.title, body.description, config.moderation, ai)

    # Read now: the rollback below expires every loaded object, and touching
    # `user.id` afterwards would try a lazy load, which async sessions can't do.
    user_id = user.id
    for _ in range(_SLUG_ATTEMPTS):
        category = Category(
            title=body.title,
            slug=await unique_slug(db, body.title),
            description=body.description,
            created_by_id=user_id,
            violation_score=assessment.violation.percent,
            machine_rules=rules,
            machine_rules_source=rules_source,
            machine_rules_updated_at=datetime.now(timezone.utc),
        )
        db.add(category)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()  # the slug was taken meanwhile - pick again
            continue
        await db.refresh(category)
        return category_out(category, 0)
    raise HTTPException(status_code=409, detail="Could not find a free address for the category, try again")


@router.get("/categories/{slug}")
async def read_category(slug: str, db: AsyncSession = Depends(get_db)) -> CategoryOut:
    category = await get_category(db, slug)
    post_count = await db.scalar(
        select(func.count()).select_from(Post).where(Post.category_id == category.id, Post.status == STATUS_PUBLISHED)
    )
    return category_out(category, post_count or 0)


# --- Posts --------------------------------------------------------------------


@router.get("/categories/{slug}/posts")
async def list_posts(
    slug: str,
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> PostPage:
    """The category's published posts, highest value first - the page the
    frontend scrolls endlessly by asking for the next offset."""
    category = await get_category(db, slug)
    if user is None:
        resonated = literal(False)
        mine = literal(False)
    else:
        resonated = exists().where(Resonance.post_id == Post.id, Resonance.user_id == user.id)
        mine = Post.author_id == user.id
    rows = (
        await db.execute(
            select(Post, resonated.label("resonated"), mine.label("mine"))
            .where(Post.category_id == category.id, Post.status == STATUS_PUBLISHED)
            .order_by(rank_expression(config).desc(), Post.id.desc())
            .offset(offset)
            .limit(config.page_size + 1)
        )
    ).all()
    now = datetime.now(timezone.utc)
    return PostPage(
        items=[
            post_out(post, config, resonated=bool(flag), mine=bool(is_mine), now=now)
            for post, flag, is_mine in rows[: config.page_size]
        ],
        has_more=len(rows) > config.page_size,
    )


@router.post("/categories/{slug}/posts/check")
async def check_post(
    slug: str,
    body: PostCreate,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
    ai: AiModerator = Depends(get_ai_moderator),
) -> AssessmentOut:
    """The verdict on a draft post - violation and topic scores with the
    aspects behind them - without publishing it."""
    category = await get_category(db, slug)
    return assessment_out(await _assess_post(category, body, config, ai))


@router.post("/categories/{slug}/posts", status_code=201)
async def create_post(
    slug: str,
    body: PostCreate,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
    ai: AiModerator = Depends(get_ai_moderator),
) -> PostOut:
    category = await get_category(db, slug)
    assessment = await _assess_post(category, body, config, ai)
    enforce(assessment, body.confirm_risk)

    post = Post(
        category_id=category.id,
        author_id=user.id,
        title=body.title,
        body=body.body,
        violation_score=assessment.violation.percent,
        topic_mismatch_score=assessment.topic.percent if assessment.topic else 0,
        assessment=assessment.to_json(),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post_out(post, config, resonated=False, mine=True)


@router.post("/posts/{post_id}/resonance")
async def add_resonance(
    post_id: uuid.UUID,
    user: User = Depends(get_active_user),
    db: AsyncSession = Depends(get_db),
    config: BoardsConfig = Depends(get_config),
) -> PostOut:
    """One resonance (+1 by default) per user and post, ever. The insert
    decides whether this one counts - the primary key plus ON CONFLICT DO
    NOTHING keeps two simultaneous requests from both counting - and the
    counter only moves when it did. A post that is no longer published
    (blocked, removed) can't be resonated with: it is as good as gone."""
    post = await db.get(Post, post_id)
    if post is None or post.status != STATUS_PUBLISHED:
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
    return post_out(post, config, resonated=True, mine=post.author_id == user.id)


# The administrators' endpoints, under /manage. Included last: this module's
# own fixed paths above never collide with them, and keeping the include here
# means the package's single `router` is the whole module.
router.include_router(admin_router, prefix="/manage")
