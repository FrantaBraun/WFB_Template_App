# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Files of tickets under Settings.uploads_dir/tickets/.

Two kinds, stored side by side under server-generated names (uuid4 hex):

- pictures in the text of an entry ("inline images", `<hex>.png|jpg|webp|gif`):
  the editor and a customer's mail client both have to load them without
  signing in, so they are served from the public /files route. The address is
  an unguessable capability, it only ever serves names of this exact shape and
  only image types, and it is how a picture in a ticket reaches the customer in
  the mail we send;
- every other file (`<hex>.bin`): private. There is no address for it - it is
  read back only through the administrators' download route, which finds it
  through its TicketAttachment row, and attached to the mails we send.
"""

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import BASE_DIR, Settings

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_ENTRY = 10

# Declared Content-Type -> (extension, magic bytes the file must start with).
_IMAGE_TYPES = {
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/webp": (".webp", (b"RIFF",)),
    "image/gif": (".gif", (b"GIF87a", b"GIF89a")),
}
_MEDIA_TYPES = {ext: content_type for content_type, (ext, _) in _IMAGE_TYPES.items()}
_NAME_LEN = 32  # uuid4().hex
PRIVATE_EXTENSION = ".bin"

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_FILENAME_LEN = 255
_CONTENT_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$")


def uploads_dir(settings: Settings) -> Path:
    base = Path(settings.uploads_dir)
    if not base.is_absolute():
        base = BASE_DIR / base
    return base / "tickets"


def sniff_image(content_type: str | None, contents: bytes) -> str | None:
    """The extension a picture is stored with when its declared Content-Type is
    one of the four image types *and* its content starts with that type's
    signature; None otherwise (including when the content is something else
    wearing an image type)."""
    entry = _IMAGE_TYPES.get((content_type or "").split(";", 1)[0].strip().lower())
    if entry is None or not contents.startswith(entry[1]):
        return None
    return entry[0]


def image_media_type(filename: str) -> str | None:
    """The Content-Type to serve `filename` with, or None unless it looks
    exactly like an inline image name this module generated (32 hex chars and
    a known image extension) - which is what keeps /files from ever serving a
    private attachment."""
    stem, _, ext = filename.partition(".")
    media_type = _MEDIA_TYPES.get(f".{ext}")
    if media_type is None or len(stem) != _NAME_LEN or not all(c in "0123456789abcdef" for c in stem):
        return None
    return media_type


def clean_filename(raw: str | None, default: str = "file") -> str:
    """The name a file gets when downloaded or mailed: the client's name
    reduced to its last path segment, without control characters, capped at
    255 characters. Display-only - it never touches the disk."""
    name = _CONTROL_CHARS.sub("", (raw or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()
    if not name or name in {".", ".."}:
        name = default
    if len(name) > _MAX_FILENAME_LEN:
        stem, dot, ext = name.rpartition(".")
        ext = ext[:20] if dot else ""
        name = f"{name[: _MAX_FILENAME_LEN - len(ext) - 1]}.{ext}" if ext else name[:_MAX_FILENAME_LEN]
    return name


def clean_content_type(raw: str | None) -> str:
    """The declared Content-Type without parameters, or the generic binary one
    when it is missing or not of the type/subtype shape. Only ever stored and
    mailed along, never trusted for serving."""
    value = (raw or "").split(";", 1)[0].strip().lower()
    return value if _CONTENT_TYPE.match(value) else "application/octet-stream"


async def read_limited(file: UploadFile, limit: int, too_large: str) -> bytes:
    contents = await file.read(limit + 1)
    if len(contents) > limit:
        raise HTTPException(status_code=413, detail=too_large)
    if not contents:
        raise HTTPException(status_code=422, detail="The file is empty")
    return contents


async def read_image(file: UploadFile) -> tuple[bytes, str]:
    """(bytes, extension) of the upload once it is proven to be an image of
    acceptable size: the declared type must be one of the four and the
    content must start with that type's signature."""
    if not _declares_image(file.content_type):
        raise HTTPException(status_code=415, detail="Unsupported image type")
    contents = await read_limited(file, MAX_IMAGE_BYTES, "Image too large (max 5 MB)")
    extension = sniff_image(file.content_type, contents)
    if extension is None:
        raise HTTPException(status_code=415, detail="File content does not match its image type")
    return contents, extension


def _declares_image(content_type: str | None) -> bool:
    return (content_type or "").split(";", 1)[0].strip().lower() in _IMAGE_TYPES


def save_bytes(settings: Settings, contents: bytes, extension: str) -> str:
    """Writes the file under a generated name and returns that name."""
    directory = uploads_dir(settings)
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    (directory / stored_name).write_bytes(contents)
    return stored_name


def stored_path(settings: Settings, stored_name: str) -> Path:
    """Where a stored file lives. The name comes from the DB, but is still
    refused if it could ever point outside the tickets directory."""
    if Path(stored_name).name != stored_name:
        raise HTTPException(status_code=404, detail="Not found")
    return uploads_dir(settings) / stored_name


def delete_file(settings: Settings, stored_name: str) -> None:
    stored_path(settings, stored_name).unlink(missing_ok=True)


def delete_files(settings: Settings, stored_names: list[str]) -> None:
    for stored_name in stored_names:
        delete_file(settings, stored_name)
