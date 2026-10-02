# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Issuing the document for a confirmed payment and emailing it.

Two steps with different guarantees, so they live in two hooks of the payment
gateway (see payments.py):

1. issue_receipt - in `on_paid`, *inside* the transaction that marks the
   payment paid and raises the post's value. The document number and the
   receipt row commit together with the money, or not at all: there is never
   a paid post without its document, and never a document for a payment that
   rolled back.
2. deliver - in `after_paid`, once that transaction is committed. Sending an
   email can fail (SMTP down, a bad address) and must neither undo the
   payment nor be sent for one that was rolled back, so it comes afterwards;
   the outcome is recorded on the receipt, a failed send is retried (when the
   next payment is confirmed, and on demand by an administrator), and the
   payer can read the document in the app regardless.
"""

import logging
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi_mail import MessageType
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.boards import documents
from app.modules.boards.config import BoardsConfig
from app.modules.boards.models import Post, Receipt, ReceiptCounter
from app.modules.stripe_payment_gate.models import StripePayment
from app.services.email import send_email

logger = logging.getLogger(__name__)

# After this many failed sends a receipt is left to an administrator (resend).
MAX_AUTOMATIC_ATTEMPTS = 5
# How many older unsent receipts one confirmed payment retries.
RETRY_BATCH = 5


def provider_ready(config: BoardsConfig) -> bool:
    return config.invoicing.provider.complete


async def _next_number(db: AsyncSession, year: int) -> int:
    """The next document number of `year`. One upsert: the row lock it takes
    lasts until the surrounding transaction ends, which is what makes the
    numbers gapless and unique under concurrent confirmations."""
    statement = pg_insert(ReceiptCounter).values(year=year, last_number=1)
    statement = statement.on_conflict_do_update(
        index_elements=[ReceiptCounter.year], set_={"last_number": ReceiptCounter.last_number + 1}
    ).returning(ReceiptCounter.last_number)
    return await db.scalar(statement)


async def issue_receipt(db: AsyncSession, payment: StripePayment, config: BoardsConfig, now: datetime | None = None) -> Receipt:
    """Allocates a number and stores the document of a confirmed payment.
    Joins the caller's transaction (it flushes, never commits)."""
    invoicing = config.invoicing
    now = now or datetime.now(timezone.utc)
    year = now.astimezone(ZoneInfo(invoicing.timezone)).year
    number = f"{year}-{await _next_number(db, year):06d}"

    extra = payment.extra or {}
    post = await db.get(Post, uuid.UUID(payment.reference))
    snapshot = documents.build_snapshot(
        number=number,
        issued_at=now,
        paid_at=payment.paid_at or now,
        timezone=invoicing.timezone,
        language=documents.normalize_language(extra.get("language"), invoicing.default_language),
        provider=invoicing.provider.model_dump(),
        customer_email=extra.get("customer_email"),
        post_title=post.title if post is not None else "",
        points=int(extra.get("points", 0)),
        amount_cents=payment.amount,
        currency=payment.currency,
        payment_id=str(payment.id),
        payment_intent=payment.stripe_payment_intent_id,
        consents=list(extra.get("consents", [])),
    )
    receipt = Receipt(
        payment_id=payment.id,
        user_id=payment.user_id,
        number=number,
        issued_at=now,
        document=snapshot,
        email_to=extra.get("customer_email"),
    )
    db.add(receipt)
    await db.flush()
    return receipt


async def send_receipt(db: AsyncSession, receipt: Receipt, settings: Settings) -> bool:
    """Emails the confirmation and document, recording the outcome. Never
    raises: a failure is stored on the receipt (and logged) for a retry."""
    if not receipt.email_to:
        receipt.email_error = "No recipient: the payer's email was not known"
        await db.commit()
        return False
    base = settings.frontend_url.rstrip("/")
    subject, html = documents.render_email(
        receipt.document,
        None,
        terms_url=f"{base}/obchodni-podminky",
        receipts_url=f"{base}/receipts",
    )
    receipt.email_attempts += 1
    try:
        await send_email(subject, [receipt.email_to], html, subtype=MessageType.html, settings=settings)
    except Exception as exc:  # SMTP, DNS, a rejected address ... - whatever it is, record it and go on
        logger.exception("Could not email receipt %s", receipt.number)
        receipt.email_error = f"{type(exc).__name__}: {exc}"[:500]
        await db.commit()
        return False
    receipt.emailed_at = datetime.now(timezone.utc)
    receipt.email_error = None
    await db.commit()
    return True


async def unsent(db: AsyncSession, *, only_automatic: bool, skip: Receipt | None = None, limit: int | None = None) -> list[Receipt]:
    """Receipts with a recipient whose email has not gone out yet, oldest first."""
    query = select(Receipt).where(Receipt.emailed_at.is_(None), Receipt.email_to.is_not(None))
    if only_automatic:
        query = query.where(Receipt.email_attempts < MAX_AUTOMATIC_ATTEMPTS)
    if skip is not None:
        query = query.where(Receipt.id != skip.id)
    query = query.order_by(Receipt.issued_at.asc())
    if limit is not None:
        query = query.limit(limit)
    return list((await db.scalars(query)).all())


async def deliver(db: AsyncSession, payment: StripePayment, settings: Settings) -> None:
    """After a payment is committed: email its document, then give a few older
    receipts whose email failed another chance."""
    receipt = (await db.scalars(select(Receipt).where(Receipt.payment_id == payment.id))).first()
    if receipt is not None:
        await send_receipt(db, receipt, settings)
    for older in await unsent(db, only_automatic=True, skip=receipt, limit=RETRY_BATCH):
        await send_receipt(db, older, settings)


async def retry_unsent(db: AsyncSession, settings: Settings) -> dict:
    """Administrators' retry: every unsent receipt, whatever its attempt count."""
    pending = await unsent(db, only_automatic=False)
    sent = 0
    for receipt in pending:
        sent += await send_receipt(db, receipt, settings)
    remaining = (
        await db.scalar(select(func.count()).select_from(Receipt).where(Receipt.emailed_at.is_(None), Receipt.email_to.is_not(None)))
    ) or 0
    return {"tried": len(pending), "sent": sent, "still_unsent": remaining}
