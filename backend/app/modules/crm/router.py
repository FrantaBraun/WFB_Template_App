# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The CRM's endpoints: partners, their tasks, and the invoice PDFs
uploaded against tasks.

Every route is administrator-only - the router itself carries
require_admin (the local User.is_admin flag, never the JWT's role_name:
that role belongs to the user across every application on the shared auth
service), so a route added later can't forget it. There is no anonymous or
"owner" access anywhere, and invoice files are served only through
GET /invoices/{id}/file, never as a public upload URL.

Deletes are deliberately conservative: a partner with tasks and a task with
invoices answer 409 instead of cascading (accounting records), partners are
archived rather than deleted, and only a single invoice can always be
removed (e.g. a wrong upload).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.modules.crm import storage
from app.modules.crm.models import Invoice, Partner, Task
from app.modules.crm.schemas import (
    InvoiceOut,
    PartnerCreate,
    PartnerListItem,
    PartnerOut,
    PartnerRef,
    PartnerUpdate,
    TaskCreate,
    TaskDetail,
    TaskListItem,
    TaskOut,
    TaskUpdate,
)
from app.services.sql import like_pattern

router =APIRouter(dependencies=[Depends(require_admin)])


async def _get_partner(db: AsyncSession, partner_id: uuid.UUID) -> Partner:
    partner = await db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner


async def _get_task(db: AsyncSession, task_id: uuid.UUID) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# --- Partners -----------------------------------------------------------------


@router.get("/partners")
async def list_partners(
    q: str | None = Query(default=None, max_length=100),
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[PartnerListItem]:
    """Partners by name, with their task counts. `q` matches name, company,
    e-mail and company id (case-insensitive); archived ones are left out
    unless asked for."""
    task_count = (
        select(func.count(Task.id)).where(Task.partner_id == Partner.id).correlate(Partner).scalar_subquery()
    )
    query = select(Partner, task_count)
    if not include_archived:
        query = query.where(Partner.archived.is_(False))
    if q and q.strip():
        pattern = like_pattern(q.strip())
        query = query.where(
            Partner.name.ilike(pattern, escape="\\")
            | Partner.company.ilike(pattern, escape="\\")
            | Partner.email.ilike(pattern, escape="\\")
            | Partner.company_id.ilike(pattern, escape="\\")
        )
    rows = (await db.execute(query.order_by(func.lower(Partner.name), Partner.created_at))).all()
    return [PartnerListItem(**PartnerOut.model_validate(p).model_dump(), task_count=count) for p, count in rows]


@router.post("/partners", status_code=201)
async def create_partner(body: PartnerCreate, db: AsyncSession = Depends(get_db)) -> PartnerOut:
    partner = Partner(**body.model_dump())
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return PartnerOut.model_validate(partner)


@router.get("/partners/{partner_id}")
async def get_partner(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PartnerOut:
    return PartnerOut.model_validate(await _get_partner(db, partner_id))


@router.patch("/partners/{partner_id}")
async def update_partner(partner_id: uuid.UUID, body: PartnerUpdate, db: AsyncSession = Depends(get_db)) -> PartnerOut:
    partner = await _get_partner(db, partner_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(partner, field, value)
    await db.commit()
    await db.refresh(partner)
    return PartnerOut.model_validate(partner)


@router.delete("/partners/{partner_id}", status_code=204)
async def delete_partner(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Only a partner without tasks - archive the others instead."""
    partner = await _get_partner(db, partner_id)
    if await db.scalar(select(func.count(Task.id)).where(Task.partner_id == partner_id)):
        raise HTTPException(status_code=409, detail="Partner has tasks - archive it instead")
    await db.delete(partner)
    await db.commit()


# --- Tasks --------------------------------------------------------------------


@router.get("/partners/{partner_id}/tasks")
async def list_partner_tasks(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[TaskListItem]:
    """A partner's tasks, newest first, with how many invoices each has."""
    await _get_partner(db, partner_id)
    invoice_count = (
        select(func.count(Invoice.id)).where(Invoice.task_id == Task.id).correlate(Task).scalar_subquery()
    )
    rows = (
        await db.execute(
            select(Task, invoice_count)
            .where(Task.partner_id == partner_id)
            .order_by(Task.created_at.desc(), Task.title)
        )
    ).all()
    return [TaskListItem(**TaskOut.model_validate(t).model_dump(), invoice_count=count) for t, count in rows]


@router.post("/partners/{partner_id}/tasks", status_code=201)
async def create_task(partner_id: uuid.UUID, body: TaskCreate, db: AsyncSession = Depends(get_db)) -> TaskOut:
    await _get_partner(db, partner_id)
    task = Task(partner_id=partner_id, **body.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskOut.model_validate(task)


@router.get("/tasks/{task_id}")
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> TaskDetail:
    task = await _get_task(db, task_id)
    partner = await _get_partner(db, task.partner_id)
    invoices = (
        await db.scalars(select(Invoice).where(Invoice.task_id == task_id).order_by(Invoice.uploaded_at.desc()))
    ).all()
    return TaskDetail(
        **TaskOut.model_validate(task).model_dump(),
        partner=PartnerRef.model_validate(partner),
        invoices=[InvoiceOut.model_validate(i) for i in invoices],
    )


@router.patch("/tasks/{task_id}")
async def update_task(task_id: uuid.UUID, body: TaskUpdate, db: AsyncSession = Depends(get_db)) -> TaskOut:
    task = await _get_task(db, task_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    if task.start_date and task.due_date and task.start_date > task.due_date:
        await db.rollback()
        raise HTTPException(status_code=422, detail="start_date must not be after due_date")
    await db.commit()
    await db.refresh(task)
    return TaskOut.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Only a task without invoices - cancel the others instead."""
    task = await _get_task(db, task_id)
    if await db.scalar(select(func.count(Invoice.id)).where(Invoice.task_id == task_id)):
        raise HTTPException(status_code=409, detail="Task has invoices - delete them first or cancel the task")
    await db.delete(task)
    await db.commit()


# --- Invoices -----------------------------------------------------------------


@router.post("/tasks/{task_id}/invoices", status_code=201)
async def upload_invoice(
    task_id: uuid.UUID,
    file: UploadFile,
    number: Annotated[str | None, Form(max_length=50)] = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InvoiceOut:
    """One PDF per call (multipart `file`, optional invoice `number`). The
    file must be declared as application/pdf, start with the %PDF- header
    and stay within 10 MB; it is stored under a generated name and the
    client's filename is kept only for the download."""
    await _get_task(db, task_id)
    contents = await storage.read_pdf(file)
    stored_name = storage.save_pdf(settings, contents)
    invoice = Invoice(
        task_id=task_id,
        number=(number or "").strip() or None,
        original_filename=storage.clean_filename(file.filename),
        stored_name=stored_name,
        size_bytes=len(contents),
    )
    db.add(invoice)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        storage.delete_file(settings, stored_name)
        raise
    await db.refresh(invoice)
    return InvoiceOut.model_validate(invoice)


@router.get("/invoices/{invoice_id}/file")
async def download_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    path = storage.stored_path(settings, invoice.stored_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Invoice file is missing")
    return FileResponse(
        path,
        media_type=storage.PDF_CONTENT_TYPE,
        filename=invoice.original_filename,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/invoices/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    stored_name = invoice.stored_name
    await db.delete(invoice)
    await db.commit()
    storage.delete_file(settings, stored_name)
