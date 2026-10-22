# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Uploading images, importing them from an address, and reading them back.
An image belongs to whoever uploaded it until a record that holds its id is
saved (then to that record, still only to its owner's eyes)."""

import uuid

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.repository import fetch, images
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.schemas import ImageImport, ImageOut
from app.modules.repository.service import errors_422

router = APIRouter(prefix="/images")


@router.post("", status_code=201)
async def upload_image(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> ImageOut:
    """One image per call (multipart `file`): png, jpeg, webp or gif, recognised
    by its content and at most max_image_bytes. Use the returned id as the value
    of an image attribute when saving a record."""
    await images.maybe_purge(db, limits)
    contents = await file.read(limits.max_image_bytes + 1)
    return ImageOut.model_validate(await images.store_image(db, user, contents, limits))


@router.post("/import-url", status_code=201)
async def import_image(
    body: ImageImport,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> ImageOut:
    """Downloads the image at `url` on the server (see fetch.py for what is
    refused - internal addresses above all) and stores it like an upload.
    Failures answer 422 `{"errors": {"url": code}}`."""
    await images.maybe_purge(db, limits)
    try:
        contents = await fetch.fetch_image_bytes(body.url, max_bytes=limits.max_image_bytes)
    except fetch.FetchError as error:
        raise errors_422({"url": error.code}) from error
    return ImageOut.model_validate(await images.store_image(db, user, contents, limits))


@router.get("/{image_id}")
async def get_image(image_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
    """The image itself, to its owner only. The frontend fetches it with the
    bearer token and shows it from a blob - an <img src> cannot send one."""
    image = await images.get_image(db, user, image_id)
    return Response(
        content=images.decode(image),
        media_type=image.mime,
        headers={"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )
