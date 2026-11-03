# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApiDocument(Base):
    """One third-party API's registered documentation, owned by a Team - see
    CLAUDE.md's domain model. Holds the current-facing metadata only; the
    actual spec files (current + archived) live in ApiDocumentVersion rows
    below, one per fetched/uploaded version."""

    __tablename__ = "api_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    docs_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    recheck_period: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Whether a check that finds the same info.version but different content
    # archives the old version and records a new one marked content_changed
    # (see app/services/api_document_versions.py). On by default; a spec that
    # embeds something volatile (a build time, random examples) would
    # otherwise "change" on every check, so it can be switched off per document.
    detect_content_changes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_check_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApiDocumentVersion(Base):
    """One archived-or-current snapshot of an ApiDocument's spec file.
    archived_at IS NULL marks the current version; anything else is retained
    history. The partial unique index below enforces "at most one current
    version per document" at the database level, not just in application
    logic - see backend/app/services/api_document_versions.py (a later
    phase) for the archive-on-change flow that relies on it."""

    __tablename__ = "api_document_versions"
    __table_args__ = (
        Index(
            "uq_api_document_versions_current_per_doc",
            "documentation_id",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    documentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    spec_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # True when this row replaced a version with the SAME version string
    # whose content was different - the vendor changed the spec without
    # bumping info.version. The replaced row stays in the history, archived.
    content_changed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # What changed against the version this one replaced, counted by severity
    # ({"breaking": n, "warning": n, "info": n} - app/services/spec_diff.py).
    # NULL for a first version, for rows from before the diff existed, and
    # when the comparison itself failed; the changes themselves are computed
    # on demand from the two stored files (GET .../versions/{id}/changes).
    change_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
