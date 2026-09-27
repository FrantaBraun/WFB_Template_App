# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Registry of payment purposes - the extension point every application
plugs its own payment logic into.

This module deliberately knows nothing about what is being paid for. An
application registers a PaymentPurpose (typically at import time of its own
module's __init__.py) that supplies:

- resolve(): the initiating event - turns the caller's request payload into
  a PaymentQuote (amount, currency, description, ...). The amount is always
  computed here, server-side; the browser never gets to name a price.
  Raise PaymentRejected to refuse the request (e.g. the order is already
  paid, or the payload is invalid) with a 4xx.
- on_paid(): the follow-up processing - runs exactly once per payment, in
  the same DB transaction that marks it paid, after Stripe confirms it.
  Raising here rolls the whole thing back, so the webhook answers 500 and
  Stripe retries it later.

Example:

    async def resolve(db, user, payload):
        order = await db.get(Order, uuid.UUID(payload["order_id"]))
        return PaymentQuote(amount=order.total_minor, currency="czk",
                            description=f"Objednávka {order.number}",
                            reference=str(order.id), return_path=f"/orders/{order.id}")

    async def on_paid(db, payment):
        order = await db.get(Order, uuid.UUID(payment.reference))
        order.status = "paid"

    register_purpose(PaymentPurpose(key="order", resolve=resolve, on_paid=on_paid))
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.stripe_payment_gate.models import StripePayment


class PaymentRejected(Exception):
    """Raised by a purpose's resolve() to refuse a payment request."""

    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class PaymentQuote:
    amount: int
    """In the currency's minor unit (e.g. 19900 = 199.00 CZK)."""
    currency: str
    """ISO 4217 code, lowercase (e.g. "czk", "eur")."""
    description: str
    """Shown to the payer on Stripe's checkout page."""
    reference: str | None = None
    """The purpose's own opaque identifier, handed back to on_paid."""
    return_path: str | None = None
    """Frontend path the result page offers as "continue" once paid."""
    extra: dict = field(default_factory=dict)
    """Any additional data the purpose wants stored with the payment."""


ResolveFn = Callable[[AsyncSession, User | None, dict], Awaitable[PaymentQuote]]
OnPaidFn = Callable[[AsyncSession, StripePayment], Awaitable[None]]


@dataclass(frozen=True)
class PaymentPurpose:
    key: str
    resolve: ResolveFn
    on_paid: OnPaidFn | None = None
    require_user: bool = True


_purposes: dict[str, PaymentPurpose] = {}


def register_purpose(purpose: PaymentPurpose) -> None:
    """Registering the same key twice replaces the earlier registration."""
    _purposes[purpose.key] = purpose


def unregister_purpose(key: str) -> None:
    _purposes.pop(key, None)


def get_purpose(key: str) -> PaymentPurpose | None:
    return _purposes.get(key)
