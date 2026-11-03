# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.author_messages.schemas import AuthorOut

RecheckPeriod = Literal["manual", "daily", "weekly", "monthly"]


class ApiDocumentCreate(BaseModel):
    team_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    docs_url: str | None = Field(default=None, max_length=2048)
    recheck_period: RecheckPeriod = "manual"
    notes: str | None = None


class ApiDocumentUpdate(BaseModel):
    """PATCH body - every field optional/partial. The router applies this via
    model_dump(exclude_unset=True) so an omitted field is left untouched,
    while an explicitly-sent null still clears a nullable field such as
    source_url (see api_docs/router.py's update_document)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    recheck_period: RecheckPeriod | None = None
    is_public: bool | None = None
    # Not nullable (the column is NOT NULL): an explicit null is a 422.
    detect_content_changes: bool = True
    source_url: str | None = Field(default=None, max_length=2048)
    docs_url: str | None = Field(default=None, max_length=2048)


class ApiDocumentSummary(BaseModel):
    """List-item shape shared by GET /api/api-docs and GET /api/public/api-docs.
    current_version is just the current row's version string (or null) -
    not the richer object ApiDocumentDetail nests below."""

    id: uuid.UUID
    title: str
    team_id: uuid.UUID
    is_public: bool
    recheck_period: str
    last_checked_at: datetime | None
    last_check_error: str | None
    current_version: str | None


class ChangeSummaryOut(BaseModel):
    """How many structural changes a version brought over the one it replaced,
    by severity (app/services/spec_diff.py): breaking ones can make an
    existing client fail, warnings may, info ones are safe. Null on a version
    where there is nothing to say (a first version, or one recorded before
    this existed or when the comparison failed)."""

    breaking: int
    warning: int
    info: int

    @classmethod
    def from_stored(cls, summary: dict | None) -> "ChangeSummaryOut | None":
        """From ApiDocumentVersion.change_summary (null or {"breaking": n, ...})."""
        if not summary:
            return None
        return cls(
            breaking=summary.get("breaking", 0), warning=summary.get("warning", 0), info=summary.get("info", 0)
        )


class IntegrationRefOut(BaseModel):
    """An integration, as another page names it: just enough to show and link
    it. Only ever integrations of teams the caller belongs to - integrations
    are team-private, so their names must not reach anyone else."""

    id: uuid.UUID
    name: str


class LatestChangeOut(BaseModel):
    """What a document's current version changed over the one it replaced -
    present only when it replaced one (and the comparison could be made).
    version_id is the current version's id, which the Changes page takes."""

    version_id: uuid.UUID
    version: str
    fetched_at: datetime
    content_changed: bool
    summary: ChangeSummaryOut


class ApiDocumentCurrentVersion(BaseModel):
    """The current-version object nested in ApiDocumentDetail. Distinct from
    ApiDocumentVersionOut (the /versions list-item shape below): this one
    carries format instead of archived_at, since archived_at is always null
    here by definition (it's always the current row)."""

    id: uuid.UUID
    version: str
    spec_title: str | None
    format: str
    fetched_at: datetime
    source: str
    content_changed: bool
    change_summary: ChangeSummaryOut | None


class ApiDocumentDetail(BaseModel):
    """is_subscribed is null for an anonymous caller (no identity to check a
    Subscription row against) and true/false otherwise - see
    api_docs/router.py's _build_detail, which computes it from the same
    current_user already used for can_edit. author is who created the
    document and the team that owns it (see AuthorOut) - what the "contact
    the author" card shows. integrations are the caller's own teams'
    integrations that use this document (directly or through a collection) -
    empty for an anonymous caller and for anyone whose teams use it nowhere."""

    id: uuid.UUID
    team_id: uuid.UUID
    title: str
    notes: str | None
    source_url: str | None
    docs_url: str | None
    recheck_period: str
    is_public: bool
    detect_content_changes: bool
    last_checked_at: datetime | None
    last_check_error: str | None
    created_at: datetime
    current_version: ApiDocumentCurrentVersion | None
    can_edit: bool
    is_subscribed: bool | None
    author: AuthorOut
    integrations: list[IntegrationRefOut]


class ApiDocumentCheckResult(ApiDocumentDetail):
    """Response of POST /{id}/recheck and POST /{id}/upload-version: the
    document as ApiDocumentDetail, plus what this particular call did - so the
    UI can say so instead of leaving the user to compare versions by eye.
    new_version_found is true only when this call archived the old current
    version and created a new one with a DIFFERENT info.version (an unchanged
    info.version is false, and a failed check never gets here - it is an HTTP
    error). content_changed is true when the call found the same info.version
    with different content and recorded it as a new row (see
    ApiDocument.detect_content_changes); it is never true together with
    new_version_found. previous_version is the current version's string
    before the call, null if there was none yet."""

    new_version_found: bool
    content_changed: bool
    previous_version: str | None


class ApiDocumentVersionOut(BaseModel):
    """GET /api/api-docs/{id}/versions list item - carries archived_at
    (unlike ApiDocumentCurrentVersion above) so the frontend can tell current
    from archived rows within the same list."""

    id: uuid.UUID
    version: str
    spec_title: str | None
    fetched_at: datetime
    archived_at: datetime | None
    source: str
    content_changed: bool
    change_summary: ChangeSummaryOut | None


class SpecChangeOut(BaseModel):
    """One structural change (app/services/spec_diff.py's Change): kind names
    what changed and the frontend words it, severity is "breaking", "warning"
    or "info", method/path say which operation (null for none), scope is
    "parameter", "request" or "response", status the response's status code,
    media_type the body's, location where inside it ("query:limit",
    "address.zip", "items[].id"), detail the few facts the wording needs."""

    kind: str
    severity: Literal["breaking", "warning", "info"]
    method: str | None
    path: str | None
    scope: str | None
    status: str | None
    media_type: str | None
    location: str
    detail: dict[str, Any]


class VersionRefOut(BaseModel):
    id: uuid.UUID
    version: str
    fetched_at: datetime
    content_changed: bool


class VersionChangesOut(BaseModel):
    """GET /api/api-docs/{id}/versions/{version_id}/changes: what differs
    between `base` (the older side) and `target`, most severe first.
    truncated is true when the list was cut off at the diff's limit - the
    summary then counts only what was kept. An empty list means no
    structural change: descriptions, examples and other documentation may
    still differ."""

    base: VersionRefOut
    target: VersionRefOut
    summary: ChangeSummaryOut
    changes: list[SpecChangeOut]
    truncated: bool
