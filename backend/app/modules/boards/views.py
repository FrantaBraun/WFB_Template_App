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
from app.modules.boards.models import Category, Post
from app.modules.boards.moderation.assess import Assessment
from app.modules.boards.schemas import (
    AdminPostOut,
    AssessmentOut,
    CategoryOut,
    FindingOut,
    PostOut,
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


def post_out(post: Post, config: BoardsConfig, *, resonated: bool, now: datetime | None = None) -> PostOut:
    return PostOut(
        id=post.id,
        title=post.title,
        body=post.body,
        value=_value(post, config, now),
        resonance_count=post.resonance_count,
        resonated_by_me=resonated,
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
        moderation_reason=post.moderation_reason,
        moderated_at=post.moderated_at,
        author_id=post.author_id,
        author_blocked=author_blocked,
        created_at=post.created_at,
    )


def assessment_out(assessment: Assessment) -> AssessmentOut:
    return AssessmentOut(
        level=assessment.level,
        violation=ScoreOut(percent=assessment.violation.percent, level=assessment.violation.level),
        topic=ScoreOut(percent=assessment.topic.percent, level=assessment.topic.level) if assessment.topic else None,
        findings=[FindingOut(code=f.code, aspect=f.aspect, matches=list(f.matches)) for f in assessment.findings],
    )


async def get_category(db: AsyncSession, slug: str) -> Category:
    category = (await db.scalars(select(Category).where(Category.slug == slug))).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category
