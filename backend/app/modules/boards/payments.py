# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Paying to raise a post's value - the boards module's payment purpose for
app/modules/stripe_payment_gate.

An author pays a whole number of US dollars for one of their own published
posts; once Stripe confirms the payment the amount is added to the post's
`paid_cents`, which the value formula turns into points (1 USD = 10 by
default, see service.post_value). Payments accumulate, so a later payment
raises the value again.

The gateway module knows nothing of posts: it calls resolve() to price a
request and on_paid() - exactly once, in the transaction that marks the
payment paid - to apply it. The payer picks the amount, so resolve() is where
it is validated: a whole number inside the configured range, for a post the
payer wrote and that is still published, in a category that is not blocked.

Nothing is refunded: a post blocked for breaking the rules keeps what was paid
(see the terms), and a payment that lands after a post was blocked is still
recorded on it, because the money has been taken either way.

Every confirmed payment also gets a document (receipts.py): numbered and stored
in the same transaction as the post's new value, then emailed to the payer once
that transaction is committed. No payment is offered until the provider's
details are filled in (config.invoicing.provider) - a document without an
issuer would be worthless, and the money would already be taken.
"""

import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.modules.boards import documents, receipts
from app.modules.boards.config import get_config
from app.modules.boards.models import STATUS_PUBLISHED, Category, Post
from app.modules.stripe_payment_gate.models import StripePayment
from app.modules.stripe_payment_gate.purposes import PaymentPurpose, PaymentQuote, PaymentRejected, register_purpose

logger = logging.getLogger(__name__)

POST_BOOST = "post_boost"
CURRENCY = "usd"
# Consents the payer must give before a boost payment can start: the terms,
# and the express request for immediate performance that makes a consumer
# lose the 14-day right of withdrawal once the service is performed.
REQUIRED_CONSENTS = ("terms", "digital_content_waiver")
_DESCRIPTION_TITLE_MAX = 50


async def resolve_boost(db: AsyncSession, user: User | None, payload: dict) -> PaymentQuote:
    """Prices a boost: payload is {"post_id": ..., "amount_usd": <whole number>}."""
    config = get_config()
    if not receipts.provider_ready(config):
        raise PaymentRejected("Payments are not available yet", status_code=503)
    if user.is_blocked:
        raise PaymentRejected("Your account is blocked", status_code=403)

    amount_usd = payload.get("amount_usd")
    low, high = config.payments.min_amount_usd, config.payments.max_amount_usd
    # `type is int` rather than isinstance: True is an int, and 5.0 is not a whole payment.
    if type(amount_usd) is not int or not low <= amount_usd <= high:
        raise PaymentRejected(f"The amount must be a whole number of USD from {low} to {high}", status_code=422)

    try:
        post_id = uuid.UUID(str(payload.get("post_id")))
    except ValueError:
        raise PaymentRejected("Post not found", status_code=404) from None
    row = (
        await db.execute(select(Post, Category).join(Category, Category.id == Post.category_id).where(Post.id == post_id))
    ).first()
    # Someone else's post is "not found", not "forbidden": whether a given
    # post belongs to a given user is not to be learned by probing.
    if row is None or row[0].author_id != user.id:
        raise PaymentRejected("Post not found", status_code=404)
    post, category = row
    if post.status != STATUS_PUBLISHED:
        raise PaymentRejected("The post is no longer published", status_code=409)
    if category.status != STATUS_PUBLISHED:
        raise PaymentRejected("The category is blocked", status_code=409)

    points = amount_usd * config.points_per_usd
    title = post.title if len(post.title) <= _DESCRIPTION_TITLE_MAX else post.title[: _DESCRIPTION_TITLE_MAX - 1] + "…"
    return PaymentQuote(
        amount=amount_usd * 100,
        currency=CURRENCY,
        description=f"ThoughtAuction: raise the value of the post “{title}” by {points} points",
        reference=str(post.id),
        return_path=f"/categories/{category.slug}",
        extra={
            "post_id": str(post.id),
            "amount_usd": amount_usd,
            "points": points,
            # The language the payer is using, for their document and email.
            "language": documents.normalize_language(payload.get("language"), config.invoicing.default_language),
        },
    )


async def apply_boost(db: AsyncSession, payment: StripePayment) -> None:
    """Adds the paid amount to the post. One atomic UPDATE, so two payments
    confirmed at the same moment both count."""
    config = get_config()
    if payment.currency != CURRENCY:
        # Cannot happen - resolve_boost only quotes USD. Raising would make
        # Stripe retry the webhook for ever, so say so loudly and move on.
        logger.error("Boost payment %s is in %r, not %r - not applied", payment.id, payment.currency, CURRENCY)
        return
    result = await db.execute(
        update(Post).where(Post.id == uuid.UUID(payment.reference)).values(paid_cents=Post.paid_cents + payment.amount)
    )
    if result.rowcount == 0:
        logger.error("Boost payment %s refers to post %s, which does not exist", payment.id, payment.reference)
    # In the same transaction as the new value: the document and its number
    # are committed with the money, or not at all.
    await receipts.issue_receipt(db, payment, config)


async def deliver_receipt(db: AsyncSession, payment: StripePayment) -> None:
    """After the payment is committed: email the confirmation and document."""
    await receipts.deliver(db, payment, get_settings())


def register_payment_purposes() -> None:
    register_purpose(
        PaymentPurpose(
            key=POST_BOOST,
            resolve=resolve_boost,
            on_paid=apply_boost,
            after_paid=deliver_receipt,
            required_consents=REQUIRED_CONSENTS,
        )
    )
