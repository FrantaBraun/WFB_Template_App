# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""An author's payment overview: every payment they started to raise one of
their posts, whatever became of it, with the post's state today and the
document issued for it.

The payments table belongs to the gateway module, which knows nothing of
posts, so a payment is tied to its post through the reference the boost
purpose put there (the post's id) - read in Python and looked up with one IN
query rather than joined on a cast, which would keep the database from using
the posts' index. Only the signed-in user's own payments are ever read.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boards.models import Category, Post, Receipt
from app.modules.boards.payments import CURRENCY, POST_BOOST
from app.modules.stripe_payment_gate.models import STATUS_PAID, StripePayment


@dataclass
class Entry:
    """One payment with what it was for. post and category are None when the
    reference points at nothing (it cannot happen for a payment this module
    created, but a row is never assumed); receipt is None until one is issued
    - only a paid payment gets one."""

    payment: StripePayment
    post: Post | None
    category: Category | None
    receipt: Receipt | None


def _mine(user_id: uuid.UUID):
    return (StripePayment.user_id == user_id) & (StripePayment.purpose == POST_BOOST)


def _post_id(payment: StripePayment) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(payment.reference))
    except ValueError:
        return None


async def paid_totals(db: AsyncSession, user_id: uuid.UUID) -> tuple[int, int]:
    """How many payments the user has completed and how much they came to, in
    cents. Payments that were never completed - abandoned, failed, still
    waiting - are not money spent and are left out."""
    count, cents = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(StripePayment.amount), 0)).where(
                _mine(user_id), StripePayment.status == STATUS_PAID, StripePayment.currency == CURRENCY
            )
        )
    ).one()
    return count, int(cents)


async def entries(db: AsyncSession, user_id: uuid.UUID, *, offset: int, limit: int) -> list[Entry]:
    """The user's payments, newest first - `limit` of them from `offset`."""
    payments = list(
        await db.scalars(
            select(StripePayment)
            .where(_mine(user_id))
            .order_by(StripePayment.created_at.desc(), StripePayment.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    post_ids = {post_id for payment in payments if (post_id := _post_id(payment)) is not None}
    posts: dict[uuid.UUID, tuple[Post, Category]] = {}
    if post_ids:
        rows = await db.execute(
            select(Post, Category).join(Category, Category.id == Post.category_id).where(Post.id.in_(post_ids))
        )
        posts = {post.id: (post, category) for post, category in rows}
    receipts: dict[uuid.UUID, Receipt] = {}
    if payments:
        found = await db.scalars(select(Receipt).where(Receipt.payment_id.in_([payment.id for payment in payments])))
        receipts = {receipt.payment_id: receipt for receipt in found}

    result = []
    for payment in payments:
        post, category = posts.get(_post_id(payment), (None, None))
        result.append(Entry(payment, post, category, receipts.get(payment.id)))
    return result
