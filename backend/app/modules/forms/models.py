# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Form(Base):
    """A form's container: questions and answers hang off it. Which form
    belongs to what (a registration, say) is the consumer's business - it keeps
    the form's id."""

    # Prefixed like module_events / module_notifications, so it can't collide
    # with an application's own table (module models are imported even when
    # the module is disabled).
    __tablename__ = "module_forms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FormQuestion(Base):
    """One question of a form, in the order of `position` (0-based). The id is
    chosen by the client: a question that is new needs one before it is saved,
    so that the conditions of other questions can refer to it, and an unchanged
    id is what keeps the statistics of a question together across edits. `config`
    holds what the type needs (see logic.py), `conditions` the rules that decide
    whether it is shown."""

    __tablename__ = "module_form_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    help_text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    conditions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class FormSubmission(Base):
    """One filled-in form. `answers` is the snapshot logic.validate_answers
    builds - every question as it was worded when answered - so editing or
    deleting a question later changes neither how this answer reads nor the
    statistics. Deliberately no cascade from the form: a form that still has
    answers cannot be deleted (the one who holds them, a registration, removes
    them itself - see service.delete_submissions)."""

    __tablename__ = "module_form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_forms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    answers: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
