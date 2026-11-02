# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What api_docs/router.py and collections/router.py share for "the author of
this document / collection": the author block of their detail responses and
the contact-author endpoint's body, so the two routers differ only in what
they look up and how they check visibility."""

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.author_messages.schemas import AuthorOut, ContactAuthorResult
from app.config import Settings
from app.models.api_document import ApiDocument
from app.models.collection import Collection
from app.models.user import User
from app.services.author_contact import AuthorContactError, get_author_info, send_author_message


async def build_author_out(
    db: AsyncSession, *, created_by_user_id: uuid.UUID, team_id: uuid.UUID, viewer: User | None
) -> AuthorOut:
    info = await get_author_info(db, created_by_user_id=created_by_user_id, team_id=team_id)
    return AuthorOut(
        display_name=info.display_name,
        team_name=info.team_name,
        accepts_messages=info.accepts_messages,
        is_self=viewer is not None and viewer.id == created_by_user_id,
    )


async def contact_author(
    db: AsyncSession,
    settings: Settings,
    *,
    sender: User,
    message: str,
    document: ApiDocument | None = None,
    collection: Collection | None = None,
) -> ContactAuthorResult:
    """The caller has already established that sender may see the target.
    The author is whoever created it (created_by_user_id)."""
    target = document if document is not None else collection
    try:
        stored = await send_author_message(
            db,
            sender=sender,
            author_user_id=target.created_by_user_id,
            body=message,
            document=document,
            collection=collection,
            settings=settings,
        )
    except AuthorContactError as exc:
        status = {"rate_limited": 429, "not_accepting": 403}.get(exc.code, 422)
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return ContactAuthorResult(id=stored.id, email_sent=stored.email_sent)
