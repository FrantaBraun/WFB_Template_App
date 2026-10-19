# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, model_validator

TaskStatus = Literal["new", "in_progress", "done", "invoiced", "paid", "cancelled"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _blank_to_none(value):
    """A cleared form field arrives as "" - store it as no value at all."""
    value = _strip(value)
    return None if value == "" else value


# Surrounding whitespace never matters in a CRM record.
StrippedStr = Annotated[str, BeforeValidator(_strip)]
OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]


# --- Partners -----------------------------------------------------------------


class PartnerFields(BaseModel):
    name: StrippedStr = Field(min_length=1, max_length=200)
    company: OptionalStr = Field(default=None, max_length=200)
    company_id: OptionalStr = Field(default=None, max_length=30)
    vat_id: OptionalStr = Field(default=None, max_length=30)
    address: StrippedStr = Field(default="", max_length=1000)
    email: Annotated[EmailStr | None, BeforeValidator(_blank_to_none)] = Field(default=None)
    phone: OptionalStr = Field(default=None, max_length=50)
    notes: StrippedStr = Field(default="", max_length=10000)


class PartnerCreate(PartnerFields):
    pass


class PartnerUpdate(BaseModel):
    """Partial update: only the fields sent change. name and the free-text
    fields can be cleared to "" but never to null."""

    name: StrippedStr | None = Field(default=None, min_length=1, max_length=200)
    company: OptionalStr = Field(default=None, max_length=200)
    company_id: OptionalStr = Field(default=None, max_length=30)
    vat_id: OptionalStr = Field(default=None, max_length=30)
    address: StrippedStr | None = Field(default=None, max_length=1000)
    email: Annotated[EmailStr | None, BeforeValidator(_blank_to_none)] = Field(default=None)
    phone: OptionalStr = Field(default=None, max_length=50)
    notes: StrippedStr | None = Field(default=None, max_length=10000)
    archived: bool | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self):
        for field in ("name", "address", "notes", "archived"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PartnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    company: str | None
    company_id: str | None
    vat_id: str | None
    address: str
    email: str | None
    phone: str | None
    notes: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class PartnerListItem(PartnerOut):
    task_count: int


class PartnerRef(BaseModel):
    """The partner a task belongs to, for the task's own page."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    company: str | None


# --- Tasks --------------------------------------------------------------------


class TaskFields(BaseModel):
    title: StrippedStr = Field(min_length=1, max_length=200)
    description: StrippedStr = Field(default="", max_length=10000)
    status: TaskStatus = "new"
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: Annotated[str, BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v)] = Field(
        default="CZK", pattern=r"^[A-Z]{3}$"
    )
    start_date: date | None = None
    due_date: date | None = None


class TaskCreate(TaskFields):
    @model_validator(mode="after")
    def _dates_in_order(self):
        if self.start_date and self.due_date and self.start_date > self.due_date:
            raise ValueError("start_date must not be after due_date")
        return self


class TaskUpdate(BaseModel):
    """Partial update; the start/due order is checked against the stored
    task in the router, since either date may come from it."""

    title: StrippedStr | None = Field(default=None, min_length=1, max_length=200)
    description: StrippedStr | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: Annotated[str | None, BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v)] = Field(
        default=None, pattern=r"^[A-Z]{3}$"
    )
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self):
        for field in ("title", "description", "status", "currency"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    partner_id: uuid.UUID
    title: str
    description: str
    status: TaskStatus
    # Serialized as a string ("1500.00") so no precision is lost on the way out.
    price: Decimal | None
    currency: str
    start_date: date | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class TaskListItem(TaskOut):
    invoice_count: int


# --- Invoices -----------------------------------------------------------------


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    number: str | None
    original_filename: str
    size_bytes: int
    uploaded_at: datetime


class TaskDetail(TaskOut):
    partner: PartnerRef
    invoices: list[InvoiceOut]
