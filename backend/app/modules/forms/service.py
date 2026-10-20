# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What other modules call. The module has no public routes: a module that
owns a form (the registration of an event, say) creates it with create_form,
returns its questions to its own visitors (QuestionOut from schemas), and when
someone answers calls validate_answers and store_submission in the SAME
transaction as its own record, converting a FormValidationError into its
own 422 (`error.as_detail()`). For the administrators' view of the answers it
passes the submission ids that still count (list_submissions / compute_stats
take `submission_ids`), and when it deletes its own records it deletes the
answers with delete_submissions.

None of these commit: flush only, so the consumer decides what is one
transaction.
"""

import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forms.logic import (  # noqa: F401  (re-exported: this is the module's whole interface)
    FormValidationError,
    Question,
    stats_from_answers,
    validate_answers,
    visible_questions,
)
from app.modules.forms.models import Form, FormQuestion, FormSubmission
from app.modules.forms.schemas import QuestionIn


class FormInUseError(Exception):
    """The form still has answers; whoever holds them deletes them first."""


class QuestionIdConflictError(Exception):
    """A question id the caller sent already belongs to another form."""


def to_logic_questions(rows: Sequence[FormQuestion]) -> list[Question]:
    """FormQuestion rows as the plain objects logic.py works on, in order."""
    return [
        Question(
            id=str(row.id),
            type=row.type,
            label=row.label,
            required=row.required,
            config=row.config,
            conditions=row.conditions,
            position=row.position,
        )
        for row in sorted(rows, key=lambda r: r.position)
    ]


async def create_form(db: AsyncSession, name: str) -> Form:
    form = Form(name=name)
    db.add(form)
    await db.flush()
    return form


async def get_form(db: AsyncSession, form_id: uuid.UUID) -> Form | None:
    return await db.get(Form, form_id)


async def get_questions(db: AsyncSession, form_id: uuid.UUID) -> list[FormQuestion]:
    return list(
        (await db.scalars(select(FormQuestion).where(FormQuestion.form_id == form_id).order_by(FormQuestion.position))).all()
    )


async def replace_questions(db: AsyncSession, form_id: uuid.UUID, questions: Sequence[QuestionIn]) -> list[FormQuestion]:
    """Makes the form's questions exactly `questions`, in that order: those whose
    id is already on the form are updated, new ids are inserted, ids no longer
    listed are deleted. All or nothing (the caller's transaction)."""
    ids = [question.id for question in questions]
    if ids:
        foreign = await db.scalar(select(FormQuestion.id).where(FormQuestion.id.in_(ids), FormQuestion.form_id != form_id))
        if foreign is not None:
            raise QuestionIdConflictError(str(foreign))

    existing = {row.id: row for row in await get_questions(db, form_id)}
    for question_id, row in existing.items():
        if question_id not in ids:
            await db.delete(row)
    await db.flush()

    rows = []
    for position, question in enumerate(questions):
        row = existing.get(question.id)
        if row is None:
            row = FormQuestion(id=question.id, form_id=form_id)
            db.add(row)
        row.position = position
        row.type = question.type
        row.label = question.label
        row.help_text = question.help_text
        row.required = question.required
        row.config = question.config
        row.conditions = [condition.model_dump(mode="json") for condition in question.conditions]
        rows.append(row)
    await db.flush()
    return rows


async def delete_form(db: AsyncSession, form_id: uuid.UUID) -> bool:
    """Deletes the form with its questions; False if there is no such form.
    FormInUseError while it still has answers."""
    form = await db.get(Form, form_id)
    if form is None:
        return False
    if await db.scalar(select(func.count()).select_from(FormSubmission).where(FormSubmission.form_id == form_id)):
        raise FormInUseError(str(form_id))
    await db.delete(form)
    await db.flush()
    return True


async def store_submission(db: AsyncSession, form_id: uuid.UUID, entries: list[dict]) -> FormSubmission:
    """Stores the snapshot validate_answers returned."""
    submission = FormSubmission(form_id=form_id, answers=entries)
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return submission


def _scoped(query, form_id: uuid.UUID, submission_ids: Collection[uuid.UUID] | None):
    """`query` limited to one form's answers and, when given, to these ids."""
    query = query.where(FormSubmission.form_id == form_id)
    if submission_ids is not None:
        query = query.where(FormSubmission.id.in_(list(submission_ids)))
    return query


async def list_submissions(
    db: AsyncSession,
    form_id: uuid.UUID,
    *,
    submission_ids: Collection[uuid.UUID] | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[FormSubmission], bool]:
    """A page of answers, newest first, and whether there are more. With
    `submission_ids` only those count (the others - a cancelled registration's -
    are left out)."""
    rows = (
        await db.scalars(
            _scoped(select(FormSubmission), form_id, submission_ids)
            .order_by(FormSubmission.created_at.desc(), FormSubmission.id)
            .offset(offset)
            .limit(limit + 1)
        )
    ).all()
    return list(rows[:limit]), len(rows) > limit


async def get_submission(db: AsyncSession, form_id: uuid.UUID, submission_id: uuid.UUID) -> FormSubmission | None:
    return (await db.scalars(_scoped(select(FormSubmission), form_id, None).where(FormSubmission.id == submission_id))).first()


async def compute_stats(db: AsyncSession, form_id: uuid.UUID, *, submission_ids: Collection[uuid.UUID] | None = None) -> dict:
    """The summary of the form's answers (logic.stats_from_answers), optionally
    only of `submission_ids`."""
    snapshots = (
        await db.scalars(
            _scoped(select(FormSubmission.answers), form_id, submission_ids).order_by(
                FormSubmission.created_at.desc(), FormSubmission.id
            )
        )
    ).all()
    return stats_from_answers(list(snapshots))


async def delete_submissions(db: AsyncSession, submission_ids: Collection[uuid.UUID]) -> int:
    """Deletes these answers (a consumer's retention, or a deleted record); returns how many there were."""
    if not submission_ids:
        return 0
    result = await db.execute(delete(FormSubmission).where(FormSubmission.id.in_(list(submission_ids))))
    return result.rowcount or 0
