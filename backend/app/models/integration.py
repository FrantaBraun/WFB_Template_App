# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Integration(Base):
    """Combines Collections and standalone ApiDocuments under one Team, via
    IntegrationCollection/IntegrationDocument below - see CLAUDE.md's domain
    model. Deliberately has no is_public column: per the plan's locked-in
    assumption, integrations are always team-gated, never public, never
    subscribable (unlike ApiDocument/Collection above it)."""

    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IntegrationCollection(Base):
    """Join table: one Collection's membership in one Integration. Unique per
    (integration_id, collection_id) - the same collection may belong to
    several integrations, but not twice to the same one."""

    __tablename__ = "integration_collections"
    __table_args__ = (
        UniqueConstraint(
            "integration_id", "collection_id", name="uq_integration_collections_integration_id_collection_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IntegrationDocument(Base):
    """Join table: one ApiDocument's direct membership in one Integration -
    independent of (and possibly overlapping with) that same document being
    reachable through a member Collection via CollectionDocument; the
    de-duplication between the two is done at read time by the merged
    documents endpoint (a later phase), not enforced here. Unique per
    (integration_id, documentation_id) - the same document may be a direct
    member of several integrations, but not twice of the same one."""

    __tablename__ = "integration_documents"
    __table_args__ = (
        UniqueConstraint(
            "integration_id", "documentation_id", name="uq_integration_documents_integration_id_documentation_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    documentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IntegrationDocumentPin(Base):
    """The version of a document an integration was built against - "we
    integrated with 1.2.0". Pinned per (integration, document) whichever way
    the document reaches the integration (directly or through a collection),
    so there is at most one. It never changes by itself: the integration page
    compares the pinned version with the document's current one, which is the
    answer to "what changed since we built this", and that stays true when
    several versions have gone by - unlike the change summary of the newest
    version, which only says what it brought over the one before it.

    A pin whose document is no longer part of the integration is simply not
    shown (and comes back with the document); the document, the version and
    the integration all cascade it away when they are deleted."""

    __tablename__ = "integration_document_pins"
    __table_args__ = (
        UniqueConstraint(
            "integration_id", "documentation_id", name="uq_integration_document_pins_integration_id_documentation_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    documentation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pinned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
