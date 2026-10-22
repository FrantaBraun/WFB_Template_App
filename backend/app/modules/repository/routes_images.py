# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Uploading images, importing them from an address, and reading them back.
An image belongs to whoever uploaded it until a record that holds its id is
saved (then to that record, still only to its owner's eyes)."""

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.repository import fetch, images
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.schemas import ImageImport, ImageOut
from app.modules.repository.service import errors_422

# What a multipart body adds to the file itself (boundaries, headers).
MULTIPART_OVERHEAD = 64 * 1024


def _too_large() -> HTTPException:
    return HTTPException(status_code=413, detail={"errors": {"file": "too_large"}})


class UploadLimitRoute(APIRoute):
    """A route that refuses a request body larger than an image may be BEFORE it
    is read. Starlette receives and spools a whole multipart body before the
    endpoint (or any dependency) runs, so the endpoint's own size check would come
    after a huge upload had already been written to disk. A declared
    Content-Length over the limit is refused at once; a body that does not declare
    one (chunked) is cut off as soon as it has sent more than the limit. The
    answer is 413 `{"errors": {"file": "too_large"}}`, like an oversized image
    that did arrive."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def limited(request: Request) -> Response:
            # The dependency override lets tests set the limits, as for the endpoints themselves.
            limits = request.app.dependency_overrides.get(get_limits, get_limits)()
            allowed = limits.max_image_bytes + MULTIPART_OVERHEAD
            declared = request.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > allowed:
                raise _too_large()
            received = 0
            receive = request.receive

            async def counting_receive():
                nonlocal received
                message = await receive()
                received += len(message.get("body", b""))
                if received > allowed:
                    raise _too_large()
                return message

            return await handler(Request(request.scope, counting_receive, request._send))

        return limited


upload_router = APIRouter(prefix="/images", route_class=UploadLimitRoute)
router = APIRouter(prefix="/images")


@upload_router.post("", status_code=201)
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
