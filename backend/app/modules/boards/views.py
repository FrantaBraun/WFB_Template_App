# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What the public router and the administrators' router share: turning rows
into what each audience may see, and the lookups both need."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boards.config import BoardsConfig
from app.modules.boards.models import STATUS_BLOCKED, STATUS_PUBLISHED, Category, Post, Receipt
from app.modules.boards.moderation.assess import Assessment
from app.modules.boards.schemas import (
    AdminCategoryOut,
    AdminPostOut,
    AdminReceiptOut,
    AssessmentOut,
    CategoryOut,
    FindingOut,
    MyPostOut,
    PostOut,
    ReceiptOut,
    ScoreOut,
)
from app.modules.boards.service import post_value


def category_out(category: Category, post_count: int) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        title=category.title,
        slug=category.slug,
        description=category.description,
        post_count=post_count,
        created_at=category.created_at,
    )


def _value(post: Post, config: BoardsConfig, now: datetime | None) -> int:
    return post_value(post.paid_cents, post.resonance_count, post.created_at, now or datetime.now(timezone.utc), config)


def post_out(
    post: Post, config: BoardsConfig, *, resonated: bool, mine: bool = False, now: datetime | None = None
) -> PostOut:
    return PostOut(
        id=post.id,
        title=post.title,
        body=post.body,
        value=_value(post, config, now),
        resonance_count=post.resonance_count,
        resonated_by_me=resonated,
        mine=mine,
        paid_cents=post.paid_cents if mine else None,
        created_at=post.created_at,
    )


def my_post_out(post: Post, category: Category, config: BoardsConfig, *, now: datetime | None = None) -> MyPostOut:
    return MyPostOut(
        id=post.id,
        category_slug=category.slug,
        category_title=category.title,
        title=post.title,
        body=post.body,
        status=post.status,
        value=_value(post, config, now),
        resonance_count=post.resonance_count,
        paid_cents=post.paid_cents,
        category_blocked=category.status == STATUS_BLOCKED,
        moderation_reason=post.moderation_reason,
        created_at=post.created_at,
    )


def stored_findings(post: Post) -> list[FindingOut]:
    """The findings kept with the post when it was published (none for a
    post that was never assessed)."""
    return [FindingOut(**finding) for finding in (post.assessment or {}).get("findings", [])]


def admin_post_out(
    post: Post, category: Category, config: BoardsConfig, *, author_blocked: bool, now: datetime | None = None
) -> AdminPostOut:
    return AdminPostOut(
        id=post.id,
        category_slug=category.slug,
        category_title=category.title,
        title=post.title,
        body=post.body,
        status=post.status,
        value=_value(post, config, now),
        resonance_count=post.resonance_count,
        violation_score=post.violation_score,
        topic_mismatch_score=post.topic_mismatch_score,
        findings=stored_findings(post),
        category_blocked=category.status != STATUS_PUBLISHED,
        moderation_reason=post.moderation_reason,
        moderated_at=post.moderated_at,
        author_id=post.author_id,
        author_blocked=author_blocked,
        created_at=post.created_at,
    )


def admin_category_out(category: Category, post_count: int) -> AdminCategoryOut:
    return AdminCategoryOut(
        id=category.id,
        title=category.title,
        slug=category.slug,
        description=category.description,
        status=category.status,
        post_count=post_count,
        violation_score=category.violation_score,
        moderation_reason=category.moderation_reason,
        moderated_at=category.moderated_at,
        created_by_id=category.created_by_id,
        created_at=category.created_at,
    )


def receipt_out(receipt: Receipt) -> ReceiptOut:
    document = receipt.document
    return ReceiptOut(
        id=receipt.id,
        number=receipt.number,
        issued_at=receipt.issued_at,
        amount=document["amount"],
        currency=document["currency"],
        post_title=document["item"]["post_title"],
        points=document["item"]["points"],
        emailed=receipt.emailed_at is not None,
    )


def admin_receipt_out(receipt: Receipt) -> AdminReceiptOut:
    return AdminReceiptOut(
        **receipt_out(receipt).model_dump(),
        payment_id=receipt.payment_id,
        email_to=receipt.email_to,
        email_attempts=receipt.email_attempts,
        email_error=receipt.email_error,
    )


def assessment_out(assessment: Assessment) -> AssessmentOut:
    """What the author is shown. Only the aspects behind a score that is
    actually over the warning threshold are listed - a faint "does not fit
    the category" (1 %) under a verdict about vulgar language would just be
    noise. (The stored assessment keeps every finding, for administrators.)"""
    levels = {"violation": assessment.violation.level, "topic": assessment.topic.level if assessment.topic else "ok"}
    return AssessmentOut(
        level=assessment.level,
        violation=ScoreOut(percent=assessment.violation.percent, level=assessment.violation.level),
        topic=ScoreOut(percent=assessment.topic.percent, level=assessment.topic.level) if assessment.topic else None,
        findings=[
            FindingOut(code=f.code, aspect=f.aspect, matches=list(f.matches))
            for f in assessment.findings
            if levels.get(f.aspect, "ok") != "ok"
        ],
    )


async def get_category(db: AsyncSession, slug: str, *, include_blocked: bool = False) -> Category:
    """The category with this slug. A blocked one is "not found" for everyone
    but the administrators, who ask for it with include_blocked."""
    query = select(Category).where(Category.slug == slug)
    if not include_blocked:
        query = query.where(Category.status == STATUS_PUBLISHED)
    category = (await db.scalars(query)).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category
