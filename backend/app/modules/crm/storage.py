# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Invoice PDF validation and storage under Settings.uploads_dir/crm/.

Unlike event_calendar's images, these files are NOT public: nothing here
builds a URL, and the only way to read one back is the module's
admin-gated download route, which looks the file up through its Invoice
row. Stored names are server-generated (uuid4 hex + .pdf), never derived
from the client's filename.
"""

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import BASE_DIR, Settings

PDF_CONTENT_TYPE = "application/pdf"
PDF_MAGIC = b"%PDF-"
MAX_INVOICE_BYTES = 10 * 1024 * 1024

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_FILENAME_LEN = 255


def uploads_dir(settings: Settings) -> Path:
    base = Path(settings.uploads_dir)
    if not base.is_absolute():
        base = BASE_DIR / base
    return base / "crm"


def clean_filename(raw: str | None) -> str:
    """The name the file gets when downloaded: the client's name reduced to
    its last path segment, without control characters, capped at 255 chars
    and always ending in .pdf. Display-only - it never touches the disk."""
    name = _CONTROL_CHARS.sub("", (raw or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()
    if not name or name in {".", ".."}:
        name = "invoice.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    if len(name) > _MAX_FILENAME_LEN:
        name = f"{name[: _MAX_FILENAME_LEN - 4]}.pdf"
    return name


async def read_pdf(file: UploadFile) -> bytes:
    """The upload's bytes, once it is proven to be a PDF of acceptable size:
    declared Content-Type application/pdf *and* the %PDF- header actually at
    the start of the content."""
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != PDF_CONTENT_TYPE:
        raise HTTPException(status_code=415, detail="Only PDF files can be uploaded")
    contents = await file.read(MAX_INVOICE_BYTES + 1)
    if len(contents) > MAX_INVOICE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    if not contents:
        raise HTTPException(status_code=422, detail="The file is empty")
    if not contents.startswith(PDF_MAGIC):
        raise HTTPException(status_code=415, detail="File content is not a PDF")
    return contents


def save_pdf(settings: Settings, contents: bytes) -> str:
    """Writes the file and returns its generated stored name."""
    directory = uploads_dir(settings)
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.pdf"
    (directory / stored_name).write_bytes(contents)
    return stored_name


def stored_path(settings: Settings, stored_name: str) -> Path:
    """Where a stored file lives. The name comes from the DB, but is still
    refused if it could ever point outside the crm directory."""
    if Path(stored_name).name != stored_name:
        raise HTTPException(status_code=404, detail="Not found")
    return uploads_dir(settings) / stored_name


def delete_file(settings: Settings, stored_name: str) -> None:
    stored_path(settings, stored_name).unlink(missing_ok=True)
