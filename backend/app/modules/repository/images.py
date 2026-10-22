# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Images of records: what is accepted, how it is stored (base64 text in the
images table - see models.Image) and how a record claims it.

Only png, jpeg, webp and gif are accepted, recognised by their first bytes -
never by what the client (or a remote server) says the content type is - and
never SVG, which is a document that can carry script. A person's images count
against max_image_bytes_per_user; an upload nobody claims is deleted after
unattached_image_hours (`maybe_purge`, at most once an hour per process, since
there is no scheduler).
"""

import base64
import binascii
import logging
import uuid
from collections.abc import Collection
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.repository.config import RepositoryConfig
from app.modules.repository.models import Image
from app.modules.repository.service import errors_422, limit_reached

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")


def detect_mime(contents: bytes) -> str | None:
    """The image type `contents` starts like, or None when it is not one we accept."""
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contents.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contents.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "image/webp"
    return None


async def store_image(db: AsyncSession, user: User, contents: bytes, limits: RepositoryConfig) -> Image:
    """Stores an upload for `user`, not yet attached to any record. Refused with
    422 `{"errors": {"file": ...}}` - `empty`, `too_large` (over max_image_bytes),
    `unsupported_type` (not png, jpeg, webp or gif) - and with 409 `limit` when
    the person's images together would exceed their quota. Commits."""
    if not contents:
        raise errors_422({"file": "empty"})
    if len(contents) > limits.max_image_bytes:
        raise errors_422({"file": "too_large"})
    mime = detect_mime(contents)
    if mime is None:
        raise errors_422({"file": "unsupported_type"})
    used = await db.scalar(select(func.coalesce(func.sum(Image.size_bytes), 0)).where(Image.owner_id == user.id))
    if used + len(contents) > limits.max_image_bytes_per_user:
        raise limit_reached("max_image_bytes_per_user", limits.max_image_bytes_per_user)
    image = Image(
        owner_id=user.id,
        mime=mime,
        size_bytes=len(contents),
        data=base64.b64encode(contents).decode("ascii"),
    )
    db.add(image)
    await db.commit()
    return image


async def get_image(db: AsyncSession, user: User, image_id: uuid.UUID) -> Image:
    image = await db.scalar(select(Image).where(Image.id == image_id, Image.owner_id == user.id))
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


def decode(image: Image) -> bytes:
    try:
        return base64.b64decode(image.data, validate=True)
    except binascii.Error as exc:  # cannot happen for what store_image wrote
        raise HTTPException(status_code=500, detail="Image data is damaged") from exc


async def usable_image_ids(db: AsyncSession, user: User, record_id: uuid.UUID | None, image_ids: Collection[str]) -> set[str]:
    """Of `image_ids`, those this person may put on the record: theirs, and either
    not yet on any record or already on this one."""
    if not image_ids:
        return set()
    attachable = Image.record_id.is_(None)
    if record_id is not None:
        attachable = attachable | (Image.record_id == record_id)
    rows = await db.scalars(
        select(Image.id).where(
            Image.id.in_([uuid.UUID(image_id) for image_id in image_ids]), Image.owner_id == user.id, attachable
        )
    )
    return {str(image_id) for image_id in rows.all()}


async def sync_record_images(db: AsyncSession, record_id: uuid.UUID, image_ids: Collection[str]) -> None:
    """Makes the images attached to the record exactly `image_ids` (already
    checked with usable_image_ids): claims the new ones, deletes those the
    record no longer holds. Flush only."""
    wanted = [uuid.UUID(image_id) for image_id in image_ids]
    if wanted:
        await db.execute(update(Image).where(Image.id.in_(wanted), Image.record_id.is_(None)).values(record_id=record_id))
    keep = Image.id.notin_(wanted) if wanted else Image.id.is_not(None)
    await db.execute(delete(Image).where(Image.record_id == record_id, keep))


async def purge_unattached(db: AsyncSession, limits: RepositoryConfig, now: datetime | None = None) -> int:
    """Deletes uploads nobody claimed within unattached_image_hours; how many there were."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=limits.unattached_image_hours)
    result = await db.execute(delete(Image).where(Image.record_id.is_(None), Image.created_at < cutoff))
    return result.rowcount or 0


_last_purge: datetime | None = None


async def maybe_purge(db: AsyncSession, limits: RepositoryConfig) -> None:
    """purge_unattached at most once an hour per process, called from the places
    that are busy anyway (an upload). A failure is logged and never reaches the caller."""
    global _last_purge
    now = datetime.now(timezone.utc)
    if _last_purge is not None and now - _last_purge < timedelta(hours=1):
        return
    try:
        # A savepoint, so a failure undoes only the purge: a rollback of the whole
        # transaction would expire the signed-in user the caller still holds.
        async with db.begin_nested():
            deleted = await purge_unattached(db, limits, now)
    except Exception:  # noqa: BLE001 - the purge must never break an upload
        logger.exception("Purging unattached images failed")
        return
    await db.commit()
    _last_purge = now
    if deleted:
        logger.info("Purged %d unattached images", deleted)


def reset_purge_throttle() -> None:
    """For tests: forget that the purge already ran."""
    global _last_purge
    _last_purge = None
