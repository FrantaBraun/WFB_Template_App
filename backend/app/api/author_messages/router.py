# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.author_messages.schemas import AuthorMessageOut, AuthorMessageTargetOut
from app.api.deps import get_current_user
from app.database import get_db
from app.models.api_document import ApiDocument
from app.models.author_message import AuthorMessage
from app.models.collection import Collection
from app.models.user import User
from app.services.author_contact import display_name

router = APIRouter()


@router.get("")
async def list_author_messages(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuthorMessageOut]:
    """The messages other users sent to the caller as the author of a
    document or collection, newest first - what the header bell's message
    notifications lead to. Strictly the caller's own: there is no way to ask
    for anyone else's, and no state to change (read/unread lives on the
    Notification)."""
    stmt = (
        select(AuthorMessage, User, ApiDocument.title, Collection.name)
        .join(User, User.id == AuthorMessage.sender_user_id)
        .outerjoin(ApiDocument, ApiDocument.id == AuthorMessage.documentation_id)
        .outerjoin(Collection, Collection.id == AuthorMessage.collection_id)
        .where(AuthorMessage.recipient_user_id == current_user.id)
        .order_by(AuthorMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return [
        AuthorMessageOut(
            id=message.id,
            sender_name=display_name(sender),
            sender_email=sender.email,
            target=AuthorMessageTargetOut(
                kind="document" if message.documentation_id is not None else "collection",
                id=message.documentation_id or message.collection_id,
                title=document_title if message.documentation_id is not None else collection_name,
            ),
            body=message.body,
            created_at=message.created_at,
        )
        for message, sender, document_title, collection_name in rows
    ]
