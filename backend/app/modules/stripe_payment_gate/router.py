# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.stripe_payment_gate import stripe_client
from app.modules.stripe_payment_gate.models import STATUS_PENDING, StripePayment
from app.modules.stripe_payment_gate.purposes import PaymentRejected
from app.modules.stripe_payment_gate.schemas import CheckoutRequest, CheckoutResponse, PaymentOut
from app.modules.stripe_payment_gate.service import create_payment, sync_from_session
from app.security.jwt import get_current_user_claims

logger = logging.getLogger(__name__)

router = APIRouter()

# auto_error=False: a purpose may allow anonymous payments
# (PaymentPurpose.require_user=False), so an unauthenticated request must
# still reach the handler - create_payment() enforces require_user itself.
_optional_bearer = HTTPBearer(auto_error=False)

_SESSION_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.expired",
}
_FAILED_EVENT = "checkout.session.async_payment_failed"


async def _optional_user_and_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> tuple[User | None, dict | None]:
    """A present-but-invalid token is a 401, not silently anonymous - the
    caller clearly meant to be signed in, and apiFetch refreshes on 401."""
    if credentials is None:
        return None, None
    claims = await get_current_user_claims(credentials)
    return await get_current_user(claims=claims, db=db), claims


def _not_configured(exc: stripe_client.StripeNotConfigured) -> HTTPException:
    logger.error("%s", exc)
    return HTTPException(status_code=503, detail="Payment gateway is not configured")


@router.post("/checkout")
async def start_checkout(
    body: CheckoutRequest,
    auth: tuple[User | None, dict | None] = Depends(_optional_user_and_claims),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CheckoutResponse:
    user, claims = auth
    try:
        payment, checkout_url = await create_payment(
            db,
            settings,
            purpose_key=body.purpose,
            payload=body.payload,
            user=user,
            customer_email=(claims or {}).get("email"),
        )
    except PaymentRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except stripe_client.StripeNotConfigured as exc:
        raise _not_configured(exc) from exc
    except httpx.HTTPError as exc:
        logger.exception("Stripe refused or failed to create a checkout session")
        raise HTTPException(status_code=502, detail="Payment gateway error") from exc
    return CheckoutResponse(payment_id=payment.id, checkout_url=checkout_url)


@router.get("/payments/{payment_id}")
async def get_payment(
    payment_id: uuid.UUID,
    auth: tuple[User | None, dict | None] = Depends(_optional_user_and_claims),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PaymentOut:
    """A payment tied to a user is visible only to that user (404 for
    anyone else, never revealing it exists); an anonymous one only to
    whoever holds its unguessable id. While still pending, re-reads the
    session from Stripe directly so the result page resolves even if the
    webhook is late or (in local dev) not forwarded at all - best-effort,
    a Stripe hiccup just leaves it pending for the next poll."""
    user, _ = auth
    payment = await db.get(StripePayment, payment_id)
    if payment is None or (payment.user_id is not None and (user is None or user.id != payment.user_id)):
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == STATUS_PENDING and payment.stripe_session_id:
        try:
            session = await stripe_client.retrieve_checkout_session(settings, payment.stripe_session_id)
            payment = await sync_from_session(db, session) or payment
        except Exception:
            logger.exception("Could not reconcile payment %s from Stripe", payment.id)
            payment = await db.get(StripePayment, payment_id)

    return PaymentOut.model_validate(payment)


@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Stripe's server-to-server confirmation. Signature-verified against
    the raw body; unrelated event types and sessions that aren't ours are
    acknowledged (200) so Stripe doesn't retry them forever. An on_paid
    failure propagates as a 500 on purpose - Stripe then retries."""
    payload = await request.body()
    try:
        event = stripe_client.verify_webhook(payload, stripe_signature, settings.stripe_webhook_secret)
    except stripe_client.StripeNotConfigured as exc:
        raise _not_configured(exc) from exc
    except stripe_client.InvalidSignature as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    event_type = event.get("type")
    if event_type in _SESSION_EVENTS or event_type == _FAILED_EVENT:
        session = event.get("data", {}).get("object", {})
        payment = await sync_from_session(db, session, failed=event_type == _FAILED_EVENT)
        if payment is None:
            logger.info("Stripe event %s for a session this app doesn't know - ignored", event.get("id"))
    return {"received": True}
