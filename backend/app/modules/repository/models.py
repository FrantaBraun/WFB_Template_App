# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Tables are prefixed like module_forms / module_crm_*, so they can't collide
# with an application's own tables (module models are imported even when the
# module is disabled). There are deliberately no ORM relationships: the module
# queries what it needs, and the foreign keys below cascade in the database
# (deleting a repository removes its tables, attributes and records).


class Repository(Base):
    """A person's own database. Private to its `owner`; `slug` is unique per
    owner (so `/repository/<slug>` needs no owner in it)."""

    __tablename__ = "module_repository_repositories"
    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_module_repository_repositories_owner_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    # A key of logic.COLOR_SCHEMES; the colours themselves are the frontend's.
    color_scheme: Mapped[str] = mapped_column(String(20), nullable=False, default="blue")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RepositoryTable(Base):
    """An object type of a repository - what is elsewhere called a table. Its
    records have the attributes below plus the system ones (id, name, slug,
    created_on, deleted_on, which live on Record itself). `slug` is unique in
    the repository."""

    __tablename__ = "module_repository_tables"
    __table_args__ = (
        UniqueConstraint("repository_id", "slug", name="uq_module_repository_tables_repository_slug"),
        CheckConstraint("view_type in ('table', 'grid')", name="ck_module_repository_tables_view_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_repository_repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    view_type: Mapped[str] = mapped_column(String(10), nullable=False, default="table")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Attribute(Base):
    """One attribute of a table, in the order of `position` (0-based). The id is
    chosen by the client and is the key of the attribute's value in
    Record.data, so renaming an attribute changes nothing stored; a table's
    attributes are saved as one ordered list (see service.replace_attributes).
    `type` and what `config` points at never change after creation (see
    logic.canonical_config for what config holds)."""

    __tablename__ = "module_repository_attributes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_repository_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_in_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Record(Base):
    """One record (item) of a table. `name` and `slug` are system attributes
    (`slug` is made from `name`, may be edited, and is unique in the table
    INCLUDING deleted records, so restoring one never collides); `data` holds
    the values of the table's attributes keyed by attribute id (see logic.py
    for the formats). A deleted record is only marked (`deleted_on`)."""

    __tablename__ = "module_repository_records"
    __table_args__ = (
        UniqueConstraint("table_id", "slug", name="uq_module_repository_records_table_slug"),
        Index("ix_module_repository_records_data", "data", postgresql_using="gin", postgresql_ops={"data": "jsonb_path_ops"}),
        Index("ix_module_repository_records_table_created", "table_id", "created_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_repository_tables.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
