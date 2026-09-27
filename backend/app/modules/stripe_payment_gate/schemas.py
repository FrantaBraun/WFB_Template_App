# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckoutRequest(BaseModel):
    """payload is passed verbatim to the purpose's resolve() - its shape is
    whatever that purpose defines (e.g. {"order_id": "..."}). It must never
    carry a price the backend trusts; resolve() computes the amount."""

    purpose: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


class CheckoutResponse(BaseModel):
    payment_id: uuid.UUID
    checkout_url: str


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purpose: str
    reference: str | None
    amount: int
    currency: str
    description: str
    status: str
    return_path: str | None
    created_at: datetime
    paid_at: datetime | None
