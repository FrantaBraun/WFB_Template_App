# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for app.services.spec_storage - save_spec_file/read_spec_file
round-tripping, isolated from the real backend/uploads directory via
pytest's tmp_path fixture used as uploads_dir."""

import uuid

from app.services.spec_storage import read_spec_file, save_spec_file


def test_save_then_read_round_trips_exact_bytes(tmp_path):
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    content = b'{"openapi": "3.0.0", "info": {"title": "Example", "version": "1.0.0"}}'

    storage_path = save_spec_file(str(tmp_path), document_id, version_id, "json", content)

    assert storage_path == f"api_docs/{document_id}/{version_id}.json"
    assert read_spec_file(str(tmp_path), storage_path) == content


def test_save_creates_nested_directory_structure(tmp_path):
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()

    save_spec_file(str(tmp_path), document_id, version_id, "yaml", b"openapi: 3.0.0")

    expected_file = tmp_path / "api_docs" / str(document_id) / f"{version_id}.yaml"
    assert expected_file.is_file()
    assert expected_file.read_bytes() == b"openapi: 3.0.0"


def test_save_two_versions_for_same_document_both_independently_readable(tmp_path):
    document_id = uuid.uuid4()
    version_a = uuid.uuid4()
    version_b = uuid.uuid4()

    path_a = save_spec_file(str(tmp_path), document_id, version_a, "json", b"version a content")
    path_b = save_spec_file(str(tmp_path), document_id, version_b, "json", b"version b content")

    assert read_spec_file(str(tmp_path), path_a) == b"version a content"
    assert read_spec_file(str(tmp_path), path_b) == b"version b content"
