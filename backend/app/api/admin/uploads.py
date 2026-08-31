# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.config import Settings, get_settings

router = APIRouter()

# Trusts the client's declared Content-Type rather than sniffing the actual
# image bytes - a deliberate v1 scope cut, not an oversight. Files are always
# served back through StaticFiles with a Content-Type derived from this same
# extension mapping, not from re-inspecting the bytes, so a mislabeled upload
# can't be coerced into executing as anything other than an image response.
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_MAX_SIZE_BYTES = 5 * 1024 * 1024


@router.post("/image")
async def upload_image(file: UploadFile, settings: Settings = Depends(get_settings)) -> dict:
    """Admin-only (gated by admin/router.py's require_admin). Never trusts
    the client's own filename - generates a random one, both to avoid path
    traversal and to avoid collisions between uploads."""
    ext = _EXTENSIONS.get(file.content_type or "")
    if ext is None:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    contents = await file.read(_MAX_SIZE_BYTES + 1)
    if len(contents) > _MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 5MB)")

    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (uploads_dir / filename).write_bytes(contents)

    return {"url": f"{settings.app_base_url}/uploads/{filename}"}
