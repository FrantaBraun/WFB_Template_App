# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Image uploads for articles (thumbnails and in-text images).

Files are named by this module (never by the client - no path traversal, no
collisions), accepted only when their bytes match the declared image type,
and served back with a Content-Type derived from the same table, never from
the client.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import BASE_DIR, Settings

# Declared Content-Type -> (extension, magic bytes the file must start with).
_IMAGE_TYPES = {
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/webp": (".webp", (b"RIFF",)),
    "image/gif": (".gif", (b"GIF87a", b"GIF89a")),
}
_MEDIA_TYPES = {ext: content_type for content_type, (ext, _) in _IMAGE_TYPES.items()}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
_NAME_LEN = 32  # uuid4().hex


def uploads_dir(settings: Settings) -> Path:
    base = Path(settings.uploads_dir)
    if not base.is_absolute():
        base = BASE_DIR / base
    return base / "articles"


def media_type_for(filename: str) -> str | None:
    """The Content-Type to serve `filename` with, or None unless it looks
    exactly like a name this module generated (32 hex chars + a known extension)."""
    stem, _, ext = filename.partition(".")
    media_type = _MEDIA_TYPES.get(f".{ext}")
    if media_type is None or len(stem) != _NAME_LEN or not all(c in "0123456789abcdef" for c in stem):
        return None
    return media_type


async def save_image(file: UploadFile, settings: Settings) -> str:
    """Validates and stores the upload, returns its file name."""
    entry = _IMAGE_TYPES.get(file.content_type or "")
    if entry is None:
        raise HTTPException(status_code=415, detail="Unsupported image type")
    ext, signatures = entry
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 5 MB)")
    if not contents.startswith(signatures):
        raise HTTPException(status_code=415, detail="File content does not match its image type")

    directory = uploads_dir(settings)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (directory / filename).write_bytes(contents)
    return filename
