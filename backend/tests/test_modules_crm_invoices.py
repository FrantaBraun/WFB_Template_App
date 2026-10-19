# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tests for the crm module's invoice PDF endpoints and storage helpers:
upload validation (content type, %PDF- magic bytes, size cap), private
storage under uploads_dir/crm/, the authenticated download, and deletion.

Same setup as test_modules_crm_router.py: a throwaway FastAPI app with just
this module's router, ASGITransport, and a rolled-back db_session."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User
from app.modules.crm import storage
from app.modules.crm.models import Invoice, Partner, Task
from app.modules.crm.router import router as crm_router

BASE = "/api/modules/crm"
PDF = b"%PDF-1.7\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n"

_crm_app = FastAPI()
_crm_app.include_router(crm_router, prefix=BASE)


@pytest.fixture(autouse=True)
async def _overrides(db_session, tmp_path, rsa_keypair, monkeypatch):
    for model in (Invoice, Task, Partner):
        await db_session.execute(delete(model))
    _, public_pem = rsa_keypair
    monkeypatch.setattr("app.security.jwt._public_key", public_pem)
    settings = Settings(uploads_dir=str(tmp_path))
    _crm_app.dependency_overrides[get_db] = lambda: db_session
    _crm_app.dependency_overrides[get_settings] = lambda: settings
    yield
    _crm_app.dependency_overrides.clear()


@pytest.fixture()
def crm_dir(tmp_path):
    return tmp_path / "crm"


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=_crm_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture()
async def admin(db_session, make_access_token):
    sub = uuid.uuid4()
    db_session.add(User(auth_sub=sub, is_admin=True))
    await db_session.commit()
    return {"Authorization": f"Bearer {make_access_token(sub=str(sub), role_name='user')}"}


@pytest.fixture()
def non_admin(make_access_token):
    return {"Authorization": f"Bearer {make_access_token(role_name='admin')}"}


@pytest.fixture()
async def task_id(db_session) -> uuid.UUID:
    partner = Partner(name="Jana")
    db_session.add(partner)
    await db_session.flush()
    task = Task(partner_id=partner.id, title="Web")
    db_session.add(task)
    await db_session.commit()
    return task.id


async def _upload(client, headers, task_id, *, name="faktura.pdf", content=PDF, content_type="application/pdf", **data):
    return await client.post(
        f"{BASE}/tasks/{task_id}/invoices", files={"file": (name, content, content_type)}, data=data, headers=headers
    )


def _stored_files(crm_dir):
    return sorted(crm_dir.iterdir()) if crm_dir.exists() else []


# --- Upload -------------------------------------------------------------------


async def test_upload_stores_the_pdf_under_a_generated_name(client, admin, task_id, crm_dir):
    resp = await _upload(client, admin, task_id, name="Faktura 2026-001.pdf", number=" 2026-001 ")

    assert resp.status_code == 201
    body = resp.json()
    assert body["task_id"] == str(task_id)
    assert body["number"] == "2026-001"
    assert body["original_filename"] == "Faktura 2026-001.pdf"
    assert body["size_bytes"] == len(PDF)
    assert "stored_name" not in body
    files = _stored_files(crm_dir)
    assert len(files) == 1
    assert len(files[0].stem) == 32 and files[0].suffix == ".pdf"
    assert files[0].read_bytes() == PDF


async def test_upload_never_uses_the_client_filename_on_disk(client, admin, task_id, crm_dir, tmp_path):
    resp = await _upload(client, admin, task_id, name="../../evil.pdf")

    assert resp.status_code == 201
    assert resp.json()["original_filename"] == "evil.pdf"
    assert [p.name for p in _stored_files(crm_dir)] != ["evil.pdf"]
    assert not (tmp_path.parent / "evil.pdf").exists()
    assert not (tmp_path / "evil.pdf").exists()


async def test_upload_number_is_optional(client, admin, task_id):
    resp = await _upload(client, admin, task_id)

    assert resp.status_code == 201
    assert resp.json()["number"] is None


async def test_upload_rejects_an_overlong_number(client, admin, task_id, crm_dir):
    resp = await _upload(client, admin, task_id, number="x" * 51)

    assert resp.status_code == 422
    assert _stored_files(crm_dir) == []


@pytest.mark.parametrize("content_type", ["image/png", "text/plain", "application/octet-stream", "application/x-pdf"])
async def test_upload_rejects_a_non_pdf_content_type(client, admin, task_id, crm_dir, content_type):
    resp = await _upload(client, admin, task_id, content_type=content_type)

    assert resp.status_code == 415
    assert _stored_files(crm_dir) == []


@pytest.mark.parametrize(
    "content",
    [b"<html>not a pdf</html>", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16, b" %PDF-1.4", b"PDF-1.4 no percent sign"],
)
async def test_upload_rejects_content_that_is_not_a_pdf(client, admin, task_id, crm_dir, content):
    resp = await _upload(client, admin, task_id, content=content)

    assert resp.status_code == 415
    assert _stored_files(crm_dir) == []


async def test_upload_rejects_an_empty_file(client, admin, task_id, crm_dir):
    resp = await _upload(client, admin, task_id, content=b"")

    assert resp.status_code == 422
    assert _stored_files(crm_dir) == []


async def test_upload_rejects_a_file_over_the_size_cap(client, admin, task_id, crm_dir, monkeypatch):
    monkeypatch.setattr(storage, "MAX_INVOICE_BYTES", 100)

    too_big = await _upload(client, admin, task_id, content=PDF + b"x" * (100 - len(PDF) + 1))
    just_fits = await _upload(client, admin, task_id, content=PDF + b"x" * (100 - len(PDF)))

    assert too_big.status_code == 413
    assert just_fits.status_code == 201
    assert len(_stored_files(crm_dir)) == 1


def test_the_size_cap_is_10_mb():
    assert storage.MAX_INVOICE_BYTES == 10 * 1024 * 1024


async def test_upload_without_a_file_is_422(client, admin, task_id):
    resp = await client.post(f"{BASE}/tasks/{task_id}/invoices", data={"number": "1"}, headers=admin)

    assert resp.status_code == 422


async def test_upload_for_an_unknown_task_is_404_and_stores_nothing(client, admin, crm_dir):
    resp = await _upload(client, admin, uuid.uuid4())

    assert resp.status_code == 404
    assert _stored_files(crm_dir) == []


async def test_upload_requires_an_administrator(client, non_admin, task_id, crm_dir):
    anonymous = await _upload(client, {}, task_id)
    forbidden = await _upload(client, non_admin, task_id)

    assert anonymous.status_code in (401, 403)
    assert forbidden.status_code == 403
    assert _stored_files(crm_dir) == []


async def test_upload_removes_the_file_when_saving_the_row_fails(client, admin, task_id, crm_dir, db_session, monkeypatch):
    async def boom():
        raise RuntimeError("database down")

    monkeypatch.setattr(db_session, "commit", boom)

    with pytest.raises(RuntimeError):
        await _upload(client, admin, task_id)

    assert _stored_files(crm_dir) == []


# --- Download -----------------------------------------------------------------


async def test_download_returns_the_pdf_as_a_private_attachment(client, admin, task_id):
    invoice = (await _upload(client, admin, task_id, name="faktura.pdf")).json()

    resp = await client.get(f"{BASE}/invoices/{invoice['id']}/file", headers=admin)

    assert resp.status_code == 200
    assert resp.content == PDF
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == 'attachment; filename="faktura.pdf"'
    assert resp.headers["cache-control"] == "private, no-store"
    assert resp.headers["x-content-type-options"] == "nosniff"


async def test_download_keeps_a_czech_filename(client, admin, task_id):
    invoice = (await _upload(client, admin, task_id, name="Faktura č. 1 – říjen.pdf")).json()

    resp = await client.get(f"{BASE}/invoices/{invoice['id']}/file", headers=admin)

    assert resp.status_code == 200
    assert "filename*=utf-8''" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].startswith("attachment;")


async def test_download_requires_an_administrator(client, admin, non_admin, task_id):
    invoice = (await _upload(client, admin, task_id)).json()
    url = f"{BASE}/invoices/{invoice['id']}/file"

    anonymous = await client.get(url)
    forbidden = await client.get(url, headers=non_admin)

    assert anonymous.status_code in (401, 403)
    assert forbidden.status_code == 403
    assert PDF not in anonymous.content + forbidden.content


async def test_stored_files_have_no_public_url(client, admin, task_id, crm_dir):
    await _upload(client, admin, task_id)
    stored = _stored_files(crm_dir)[0].name

    for path in (f"/uploads/{stored}", f"/files/{stored}", f"/invoices/{stored}"):
        resp = await client.get(f"{BASE}{path}", headers=admin)
        assert resp.status_code != 200
        assert resp.content != PDF


async def test_download_of_an_unknown_invoice_is_404(client, admin):
    resp = await client.get(f"{BASE}/invoices/{uuid.uuid4()}/file", headers=admin)

    assert resp.status_code == 404


async def test_download_when_the_file_is_gone_from_disk_is_404(client, admin, task_id, crm_dir):
    invoice = (await _upload(client, admin, task_id)).json()
    _stored_files(crm_dir)[0].unlink()

    resp = await client.get(f"{BASE}/invoices/{invoice['id']}/file", headers=admin)

    assert resp.status_code == 404


async def test_download_refuses_a_stored_name_that_escapes_the_directory(client, admin, task_id, db_session, tmp_path):
    (tmp_path / "secret.pdf").write_bytes(PDF)
    invoice = Invoice(task_id=task_id, original_filename="x.pdf", stored_name="../secret.pdf", size_bytes=1)
    db_session.add(invoice)
    await db_session.commit()

    resp = await client.get(f"{BASE}/invoices/{invoice.id}/file", headers=admin)

    assert resp.status_code == 404
    assert resp.content != PDF


# --- Delete -------------------------------------------------------------------


async def test_delete_invoice_removes_the_row_and_the_file(client, admin, task_id, crm_dir, db_session):
    invoice = (await _upload(client, admin, task_id)).json()

    resp = await client.delete(f"{BASE}/invoices/{invoice['id']}", headers=admin)

    assert resp.status_code == 204
    assert _stored_files(crm_dir) == []
    assert (await db_session.scalar(select(func.count(Invoice.id)))) == 0
    assert (await client.get(f"{BASE}/invoices/{invoice['id']}/file", headers=admin)).status_code == 404


async def test_delete_invoice_still_succeeds_if_the_file_is_already_gone(client, admin, task_id, crm_dir):
    invoice = (await _upload(client, admin, task_id)).json()
    _stored_files(crm_dir)[0].unlink()

    resp = await client.delete(f"{BASE}/invoices/{invoice['id']}", headers=admin)

    assert resp.status_code == 204


async def test_delete_unknown_invoice_is_404(client, admin):
    resp = await client.delete(f"{BASE}/invoices/{uuid.uuid4()}", headers=admin)

    assert resp.status_code == 404


async def test_a_deleted_invoice_frees_its_task_to_be_deleted(client, admin, task_id):
    invoice = (await _upload(client, admin, task_id)).json()
    assert (await client.delete(f"{BASE}/tasks/{task_id}", headers=admin)).status_code == 409

    await client.delete(f"{BASE}/invoices/{invoice['id']}", headers=admin)

    assert (await client.delete(f"{BASE}/tasks/{task_id}", headers=admin)).status_code == 204


# --- Storage helpers ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("faktura.pdf", "faktura.pdf"),
        ("FAKTURA.PDF", "FAKTURA.PDF"),
        ("faktura", "faktura.pdf"),
        ("faktura.docx", "faktura.docx.pdf"),
        ("../../etc/passwd", "passwd.pdf"),
        ("C:\\Users\\me\\faktura.pdf", "faktura.pdf"),
        ("a/b/c.pdf", "c.pdf"),
        ("bad\r\nname\x00.pdf", "badname.pdf"),
        ("  spaced.pdf  ", "spaced.pdf"),
        ("", "invoice.pdf"),
        (None, "invoice.pdf"),
        ("..", "invoice.pdf"),
        ("/", "invoice.pdf"),
        ("Faktura č. 1.pdf", "Faktura č. 1.pdf"),
    ],
)
def test_clean_filename(raw, expected):
    assert storage.clean_filename(raw) == expected


def test_clean_filename_caps_the_length_and_keeps_the_extension():
    cleaned = storage.clean_filename("x" * 500 + ".pdf")

    assert len(cleaned) == 255
    assert cleaned.endswith(".pdf")


def test_uploads_dir_is_under_the_configured_uploads_dir(tmp_path):
    assert storage.uploads_dir(Settings(uploads_dir=str(tmp_path))) == tmp_path / "crm"


def test_a_relative_uploads_dir_is_anchored_to_the_backend_dir():
    from app.config import BASE_DIR

    assert storage.uploads_dir(Settings(uploads_dir="./uploads")) == BASE_DIR / "uploads" / "crm"
