# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Column sizes are the text limits the API enforces (schemas.py).
CATEGORY_TITLE_MAX = 120
CATEGORY_DESCRIPTION_MAX = 4096
POST_TITLE_MAX = 120
POST_BODY_MAX = 2048
SLUG_MAX = 140
MODERATION_REASON_MAX = 1000

# A post is "published" (listed, can be resonated with), "blocked" (an
# administrator marked it as violating the rules - removed without refund,
# and it counts as a strike against its author) or "removed" (taken down
# because its author's account was blocked - no strike of its own).
STATUS_PUBLISHED = "published"
STATUS_BLOCKED = "blocked"
STATUS_REMOVED = "removed"


class Category(Base):
    """One publication board: a title (its slug is generated from it) and a
    short description of what belongs there. created_by_id is kept for
    moderation and never leaves the backend - boards show no authors.

    status is "published" or "blocked" (an administrator took the whole board
    down, with a reason its creator is sent). A blocked category is gone for
    every visitor - not listed, not found, nothing can be posted, resonated
    with or paid for in it - but nothing in it is changed or deleted, so
    restoring it brings it back as it was. Its slug stays taken."""

    # Prefixed like module_events / module_notifications, so it can't collide
    # with an application's own table (module models are imported even when
    # the module is disabled).
    __tablename__ = "module_boards_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(CATEGORY_TITLE_MAX), nullable=False)
    slug: Mapped[str] = mapped_column(String(SLUG_MAX), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(CATEGORY_DESCRIPTION_MAX), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # The local violation score (percent) the category's title and description
    # got when it was created.
    violation_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    # The machine rules posts are compared against (moderation/topic.py):
    # {"keywords": [{"term", "weight"}], "notes"}; machine_rules_source is
    # "algorithm", "ai" or "admin" (who wrote them last).
    machine_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    machine_rules_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    machine_rules_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PUBLISHED, server_default=STATUS_PUBLISHED, index=True
    )
    # Set while the category is blocked: why, when, and by whom.
    moderation_reason: Mapped[str | None] = mapped_column(String(MODERATION_REASON_MAX), nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class Post(Base):
    """A post on one board - only a title and a text, no author shown.

    Its *value* is not stored: it is computed from paid_cents,
    resonance_count and the post's age (see service.py), and the listing
    orders by that value. resonance_count is denormalized from the
    Resonance rows (kept in step in the same transaction) so ordering needs
    no per-post count. paid_cents is the running total of what has been paid
    for the post; only a confirmed payment writes it (see payments.py).
    author_id is kept for moderation and never exposed.
    """

    __tablename__ = "module_boards_posts"
    __table_args__ = (
        CheckConstraint("paid_cents >= 0", name="ck_module_boards_posts_paid_cents_nonneg"),
        CheckConstraint("resonance_count >= 0", name="ck_module_boards_posts_resonance_count_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_boards_categories.id"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(POST_TITLE_MAX), nullable=False)
    body: Mapped[str] = mapped_column(String(POST_BODY_MAX), nullable=False)
    paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    resonance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PUBLISHED, server_default=STATUS_PUBLISHED, index=True
    )
    # What the local (and AI) checks scored it when it was published, and the
    # findings behind the scores - for an administrator reviewing it.
    violation_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    topic_mismatch_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    assessment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Set when the post is blocked or removed: why, when, and by whom (None
    # when the system did it, as for a removal after an account block).
    moderation_reason: Mapped[str | None] = mapped_column(String(MODERATION_REASON_MAX), nullable=True)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class Resonance(Base):
    """One user's agreement with one post. The composite primary key is what
    makes a resonance count only once per user and post. Nothing outside the
    backend ever reads user_id back out - who resonated is hidden, even from
    the post's author."""

    __tablename__ = "module_boards_resonances"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_boards_posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    """The document issued for one confirmed payment.

    `document` is a snapshot taken when the payment was confirmed - the
    issuer's details, the payer's email, the amount, the post's title - and
    is never rewritten, so a document keeps reading as it did when it was
    issued however the configuration or the post change later. `number` runs
    without gaps within a year (see ReceiptCounter). The email_* columns are
    the delivery state: the confirmation email is sent after the payment is
    committed and may fail, in which case it is retried.
    """

    __tablename__ = "module_boards_receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stripe_payments.id"), unique=True, nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    email_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    email_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ReceiptCounter(Base):
    """The last document number issued in a year. Bumped in the transaction
    that confirms the payment (one INSERT ... ON CONFLICT DO UPDATE), so two
    simultaneous confirmations queue on the row instead of taking the same
    number, and a number whose transaction rolls back is never used up."""

    __tablename__ = "module_boards_receipt_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
