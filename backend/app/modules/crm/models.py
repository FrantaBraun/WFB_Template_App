# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

TASK_STATUSES = ("new", "in_progress", "done", "invoiced", "paid", "cancelled")
STATUS_NEW = "new"

# Tables are prefixed like module_events / module_notifications, so they
# can't collide with an application's own tables (module models are imported
# even when the module is disabled).


class Partner(Base):
    """A client or other business contact. `name` is the contact person (or
    just the display name of a sole trader); `company` is optional. There is
    no hard delete of a partner that has tasks - `archived` hides it from
    the default list instead."""

    __tablename__ = "module_crm_partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Company registration number (IČO in the Czech Republic) and tax/VAT id (DIČ).
    company_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Task(Base):
    """One job done for a partner. RESTRICT on the partner FK: a partner with
    tasks can't be deleted by accident (the router answers 409 instead)."""

    __tablename__ = "module_crm_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_crm_partners.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_NEW)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CZK")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Invoice(Base):
    """A PDF invoice uploaded against a task. The file lives under
    Settings.uploads_dir/crm/ as `stored_name` (server-generated, never the
    client's name); `original_filename` is only what the file is called when
    downloaded. RESTRICT on the task FK, like Task -> Partner."""

    __tablename__ = "module_crm_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_crm_tasks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
