# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Payment lifecycle: create a Checkout Session for a registered purpose,
then reconcile the local payment row from Stripe's view of that session.

Both functions are plain async calls, so another module can start a
payment from its own code (not just through this module's HTTP endpoint)."""

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.user import User
from app.modules.stripe_payment_gate import stripe_client
from app.modules.stripe_payment_gate.models import (
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PAID,
    STATUS_PENDING,
    StripePayment,
)
from app.modules.stripe_payment_gate.purposes import PaymentRejected, get_purpose

logger = logging.getLogger(__name__)

RESULT_PATH = "/platba/vysledek"

_CURRENCY_RE = re.compile(r"^[a-z]{3}$")


def result_url(settings: Settings, payment_id: uuid.UUID, *, canceled: bool = False) -> str:
    url = f"{settings.frontend_url.rstrip('/')}{RESULT_PATH}?payment_id={payment_id}"
    return f"{url}&canceled=1" if canceled else url


async def create_payment(
    db: AsyncSession,
    settings: Settings,
    *,
    purpose_key: str,
    payload: dict,
    user: User | None,
    customer_email: str | None = None,
    consents: list[str] | None = None,
) -> tuple[StripePayment, str]:
    """Price the request via the purpose's resolve(), persist a pending
    payment and open a Stripe Checkout Session for it. Returns the payment
    and the Stripe-hosted checkout URL the browser should be sent to.

    If Stripe refuses or is unreachable, the whole transaction (including
    anything resolve() itself changed) is rolled back and the error re-raised
    - no orphaned pending row without a session."""
    purpose = get_purpose(purpose_key)
    if purpose is None:
        raise PaymentRejected("Unknown payment purpose", status_code=404)
    if purpose.require_user and user is None:
        raise PaymentRejected("Sign in to pay", status_code=401)
    missing = [consent for consent in purpose.required_consents if consent not in (consents or [])]
    if missing:
        raise PaymentRejected(f"Missing consent: {', '.join(missing)}", status_code=422)

    quote = await purpose.resolve(db, user, payload)
    currency = quote.currency.lower()
    if quote.amount <= 0 or not _CURRENCY_RE.match(currency):
        raise ValueError(f"Purpose {purpose_key!r} produced an invalid quote: {quote!r}")

    extra = dict(quote.extra)
    if consents:
        # Evidence of what the payer agreed to, and when - the burden of
        # proving that the terms (or a withdrawal waiver) were accepted lies
        # with the provider.
        extra["consents"] = sorted(set(consents))
        extra["consented_at"] = datetime.now(timezone.utc).isoformat()

    payment = StripePayment(
        id=uuid.uuid4(),
        user_id=user.id if user is not None else None,
        purpose=purpose_key,
        reference=quote.reference,
        amount=quote.amount,
        currency=currency,
        description=quote.description,
        return_path=quote.return_path,
        extra=extra,
        status=STATUS_PENDING,
    )
    db.add(payment)
    try:
        session = await stripe_client.create_checkout_session(
            settings,
            payment_id=str(payment.id),
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            success_url=result_url(settings, payment.id),
            cancel_url=result_url(settings, payment.id, canceled=True),
            customer_email=customer_email,
        )
    except Exception:
        await db.rollback()
        raise
    payment.stripe_session_id = session["id"]
    await db.commit()
    return payment, session["url"]


def _payment_id_of(session: dict) -> uuid.UUID | None:
    raw = (session.get("metadata") or {}).get("payment_id") or session.get("client_reference_id")
    try:
        return uuid.UUID(raw) if raw else None
    except ValueError:
        return None


async def sync_from_session(db: AsyncSession, session: dict, *, failed: bool = False) -> StripePayment | None:
    """Apply a Stripe Checkout Session's state to its local payment row.

    Called from both the webhook and the result page's status poll, possibly
    concurrently - the row is locked (SELECT ... FOR UPDATE) and a payment
    that has already left `pending` is never touched again, so on_paid runs
    exactly once no matter how many times Stripe (or the poll) reports the
    same success. Returns None for a session that isn't one of ours (e.g.
    another application sharing the same Stripe account)."""
    payment_id = _payment_id_of(session)
    if payment_id is None:
        return None
    payment = (
        await db.execute(select(StripePayment).where(StripePayment.id == payment_id).with_for_update())
    ).scalar_one_or_none()
    if payment is None:
        return None
    if payment.status != STATUS_PENDING:
        await db.commit()
        return payment

    if session.get("payment_intent"):
        payment.stripe_payment_intent_id = session["payment_intent"]

    if failed:
        payment.status = STATUS_FAILED
    elif session.get("status") == "complete" and session.get("payment_status") in ("paid", "no_payment_required"):
        payment.status = STATUS_PAID
        payment.paid_at = datetime.now(timezone.utc)
        purpose = get_purpose(payment.purpose)
        if purpose is None:
            logger.warning("Payment %s paid for unregistered purpose %r - on_paid skipped", payment.id, payment.purpose)
        elif purpose.on_paid is not None:
            try:
                await purpose.on_paid(db, payment)
            except Exception:
                await db.rollback()
                raise
    elif session.get("status") == "expired":
        payment.status = STATUS_EXPIRED

    await db.commit()
    return payment
