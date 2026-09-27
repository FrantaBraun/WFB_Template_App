# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"


class StripePayment(Base):
    """One payment attempt through a Stripe Checkout Session.

    purpose is the key of the registered PaymentPurpose that priced it (see
    purposes.py) and reference is that purpose's own opaque identifier for
    whatever is being paid for (an order id, a reservation id, ...) - this
    module never interprets either, it only hands them back to the purpose's
    on_paid hook. amount is in the currency's minor unit (haléře, cents),
    exactly as Stripe expects it. user_id is nullable because a purpose may
    allow anonymous payments (PaymentPurpose.require_user=False).
    """

    __tablename__ = "stripe_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    return_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_PENDING)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
