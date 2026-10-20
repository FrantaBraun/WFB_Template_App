# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The administrators' API of the forms module - the whole of it, every route
behind require_admin (this application's own administrators: the local
User.is_admin flag, never the JWT's role_name). There are no public routes:
answers arrive through the endpoints of the module that owns the form, which
calls the service in app.modules.forms.service.

This router covers every answer of a form. A consumer that has answers which
no longer count (a cancelled registration's) shows them through its own
endpoint, passing the ids that do to service.list_submissions / compute_stats.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.database import get_db
from app.modules.forms import service
from app.modules.forms.schemas import (
    FormCreate,
    FormOut,
    QuestionOut,
    QuestionsReplace,
    StatsOut,
    SubmissionOut,
    SubmissionPage,
)

router = APIRouter(prefix="/manage", dependencies=[Depends(require_admin)])


async def _form_out(db: AsyncSession, form_id: uuid.UUID) -> FormOut:
    form = await service.get_form(db, form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    questions = await service.get_questions(db, form_id)
    return FormOut(
        id=form.id,
        name=form.name,
        created_at=form.created_at,
        questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.post("", status_code=201)
async def create_form(body: FormCreate, db: AsyncSession = Depends(get_db)) -> FormOut:
    form = await service.create_form(db, body.name)
    await db.commit()
    return await _form_out(db, form.id)


@router.get("/{form_id}")
async def get_form(form_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> FormOut:
    return await _form_out(db, form_id)


@router.put("/{form_id}/questions")
async def replace_questions(form_id: uuid.UUID, body: QuestionsReplace, db: AsyncSession = Depends(get_db)) -> FormOut:
    """Replaces the whole ordered list of the form's questions at once - order,
    conditions and all - so reordering needs no partial operations. All or nothing."""
    if await service.get_form(db, form_id) is None:
        raise HTTPException(status_code=404, detail="Form not found")
    try:
        await service.replace_questions(db, form_id, body.questions)
    except service.QuestionIdConflictError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="a question id already belongs to another form") from exc
    await db.commit()
    return await _form_out(db, form_id)


@router.delete("/{form_id}", status_code=204)
async def delete_form(form_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Deletes the form with its questions; 409 while it still has answers."""
    try:
        deleted = await service.delete_form(db, form_id)
    except service.FormInUseError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="the form still has answers") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Form not found")
    await db.commit()


@router.get("/{form_id}/submissions")
async def list_submissions(
    form_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SubmissionPage:
    """Every answer of the form, newest first, each with its complete snapshot."""
    if await service.get_form(db, form_id) is None:
        raise HTTPException(status_code=404, detail="Form not found")
    rows, has_more = await service.list_submissions(db, form_id, offset=offset, limit=limit)
    return SubmissionPage(items=[SubmissionOut.model_validate(r) for r in rows], has_more=has_more)


@router.get("/{form_id}/submissions/{submission_id}")
async def get_submission(form_id: uuid.UUID, submission_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SubmissionOut:
    row = await service.get_submission(db, form_id, submission_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    return SubmissionOut.model_validate(row)


@router.get("/{form_id}/stats")
async def get_stats(form_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StatsOut:
    """The basic summary of every answer of the form (see logic.stats_from_answers)."""
    if await service.get_form(db, form_id) is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return StatsOut(**await service.compute_stats(db, form_id))
