# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from pathlib import Path


def save_spec_file(
    uploads_dir: str,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    format: str,
    content: bytes,
) -> str:
    """Write one spec file to uploads_dir/api_docs/{document_id}/{version_id}.{format}
    and return the path relative to uploads_dir (e.g.
    "api_docs/{document_id}/{version_id}.json") - the value stored in
    ApiDocumentVersion.storage_path. The relative path is always built with
    forward slashes regardless of host OS, since it is a stored DB value,
    not a filesystem path used directly on this machine.

    Takes uploads_dir as an explicit parameter rather than reading Settings
    internally, so this is trivially testable against a tmp_path - callers
    pass settings.uploads_dir themselves.
    """
    relative_path = f"api_docs/{document_id}/{version_id}.{format}"

    absolute_path = Path(uploads_dir) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)

    return relative_path


def read_spec_file(uploads_dir: str, storage_path: str) -> bytes:
    """Read back a spec file previously written by save_spec_file, given the
    storage_path relative to uploads_dir (ApiDocumentVersion.storage_path)."""
    return (Path(uploads_dir) / storage_path).read_bytes()
