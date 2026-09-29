# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Minimal Stripe REST client - just the three calls this module needs.

Talks to Stripe's API directly over httpx rather than pulling in the
`stripe` SDK: it's the HTTP client the rest of the backend already uses
(see app/services/auth_client.py), it keeps the dependency set unchanged,
and it lets tests mock Stripe with respx exactly like the auth service.
"""

import hashlib
import hmac
import json
import time

import httpx

from app.config import Settings

# Stripe's own default for its SDKs' construct_event().
WEBHOOK_TOLERANCE_SECONDS = 300


class StripeNotConfigured(RuntimeError):
    pass


class InvalidSignature(Exception):
    pass


def _require_secret_key(settings: Settings) -> str:
    if not settings.stripe_secret_key:
        raise StripeNotConfigured(
            "STRIPE_SECRET_KEY is not configured - set it in backend/.env before enabling this module."
        )
    return settings.stripe_secret_key


def _client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.stripe_api_url,
        auth=(_require_secret_key(settings), ""),
        timeout=15.0,
    )


async def create_checkout_session(
    settings: Settings,
    *,
    payment_id: str,
    amount: int,
    currency: str,
    description: str,
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
) -> dict:
    """POST /v1/checkout/sessions (form-encoded, as Stripe's API requires).
    payment_id doubles as the Idempotency-Key, so a retried request for the
    same local payment can never open two sessions."""
    data = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": payment_id,
        "metadata[payment_id]": payment_id,
        "payment_intent_data[metadata][payment_id]": payment_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": currency,
        "line_items[0][price_data][unit_amount]": str(amount),
        "line_items[0][price_data][product_data][name]": description,
    }
    if customer_email:
        data["customer_email"] = customer_email
    async with _client(settings) as client:
        resp = await client.post(
            "/v1/checkout/sessions", data=data, headers={"Idempotency-Key": payment_id}
        )
        resp.raise_for_status()
        return resp.json()


async def retrieve_checkout_session(settings: Settings, session_id: str) -> dict:
    async with _client(settings) as client:
        resp = await client.get(f"/v1/checkout/sessions/{session_id}")
        resp.raise_for_status()
        return resp.json()


def verify_webhook(payload: bytes, signature_header: str, secret: str, now: float | None = None) -> dict:
    """Verify a Stripe-Signature header (t=<ts>,v1=<hmac>[,v1=...]) against
    the raw request body and return the parsed event. Mirrors the official
    SDKs' construct_event(): HMAC-SHA256 over "<t>.<body>", constant-time
    compared against every v1 signature, rejected outside the tolerance
    window to limit replays."""
    if not secret:
        raise StripeNotConfigured(
            "STRIPE_WEBHOOK_SECRET is not configured - set it in backend/.env before enabling this module."
        )
    timestamp = None
    signatures = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        raise InvalidSignature("Malformed Stripe-Signature header")
    try:
        timestamp_int = int(timestamp)
    except ValueError as exc:
        raise InvalidSignature("Malformed Stripe-Signature timestamp") from exc

    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise InvalidSignature("No matching v1 signature")
    if abs((now if now is not None else time.time()) - timestamp_int) > WEBHOOK_TOLERANCE_SECONDS:
        raise InvalidSignature("Timestamp outside the tolerance window")
    return json.loads(payload)
