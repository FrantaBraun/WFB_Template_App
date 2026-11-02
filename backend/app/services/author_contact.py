# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.api_document import ApiDocument
from app.models.author_message import AuthorMessage
from app.models.collection import Collection
from app.models.notification import Notification
from app.models.team import Team
from app.models.user import User
from app.services.email import send_email

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 2000
PREVIEW_LENGTH = 140


class AuthorContactError(Exception):
    """A message that must not be sent. code is "own_target" (the sender is
    the author) or "rate_limited" (too many messages in the last hour); the
    API layer turns them into 422 and 429."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AuthorInfo:
    """What other users may learn about the author of a document or
    collection: the name and the owning team - never the e-mail address."""

    user_id: UUID
    display_name: str | None
    team_name: str | None


def display_name(user: User | None) -> str | None:
    """The name shown for a user to others: the nickname they chose, else
    their username, else nothing (the UI then says "unknown"). Real first and
    last names and e-mail addresses are never shown - this app only has the
    username claim locally anyway (see User.login)."""
    if user is None:
        return None
    for candidate in (user.nickname, user.login):
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def one_line(text: str) -> str:
    """Collapses every whitespace run, newlines included - for e-mail subjects
    (a header must not contain a line break) and for previews."""
    return " ".join(text.split())


def preview(body: str) -> str:
    text = one_line(body)
    if len(text) <= PREVIEW_LENGTH:
        return text
    return text[: PREVIEW_LENGTH - 1].rstrip() + "…"


async def get_author_info(db: AsyncSession, *, created_by_user_id: UUID, team_id: UUID) -> AuthorInfo:
    author = await db.get(User, created_by_user_id)
    team = await db.get(Team, team_id)
    return AuthorInfo(
        user_id=created_by_user_id,
        display_name=display_name(author),
        team_name=team.name if team is not None else None,
    )


async def _enforce_rate_limit(db: AsyncSession, sender: User, settings: Settings) -> None:
    """Soft limit: two requests racing each other can both pass the count, so
    the cap can be exceeded by the number of simultaneous requests - good
    enough against someone mailing an author over and over, which is all it
    is for."""
    limit = settings.author_message_max_per_hour
    if limit <= 0:
        return
    recent = await db.scalar(
        select(func.count())
        .select_from(AuthorMessage)
        .where(
            AuthorMessage.sender_user_id == sender.id,
            AuthorMessage.created_at > func.now() - timedelta(hours=1),
        )
    )
    if (recent or 0) >= limit:
        raise AuthorContactError(
            "rate_limited", "You have sent too many messages recently - try again in an hour."
        )


async def _email_author(
    *,
    author: User | None,
    sender: User,
    body: str,
    kind: str,
    target_id: UUID,
    target_title: str,
    settings: Settings,
) -> bool:
    """Best-effort e-mail copy of the message: True only if it was sent. An
    author without a cached address, or a failing SMTP server, never undoes
    the stored message - it is still in the app (the bell and /messages).

    The sender's address goes into Reply-To so the author can answer straight
    from the mail client; the UI tells the sender that before they write. The
    From address stays the application's own."""
    if author is None or not author.email:
        return False
    try:
        sender_name = display_name(sender) or "A user"
        base_url = settings.frontend_url.rstrip("/")
        target_path = "api-docs" if kind == "document" else "collections"
        lines = [
            f'{sender_name} wrote to you as the author of "{target_title}" in API Hub:',
            "",
            body,
            "",
            "---",
        ]
        if sender.email:
            lines.append(f"Reply to this e-mail to answer {sender_name} - it goes to their address.")
        lines.append(f"Read it in the app: {base_url}/messages")
        lines.append(f"Open the {kind}: {base_url}/{target_path}/{target_id}")
        await send_email(
            subject=f"Message from {one_line(sender_name)} about {one_line(target_title)}",
            recipients=[author.email],
            body="\n".join(lines),
            reply_to=[sender.email] if sender.email else None,
            settings=settings,
        )
        return True
    except Exception:
        logger.exception("Failed to e-mail the author %s about a message from user %s", author.id, sender.id)
        return False


async def send_author_message(
    db: AsyncSession,
    *,
    sender: User,
    author_user_id: UUID,
    body: str,
    document: ApiDocument | None = None,
    collection: Collection | None = None,
    settings: Settings | None = None,
) -> AuthorMessage:
    """Stores the message, adds the in-app Notification for the author and
    e-mails them. Exactly one of document / collection is the target (the
    caller has already checked the sender may see it). Raises
    AuthorContactError before anything is written; the e-mail is sent after
    the commit, so a failure there is only recorded in email_sent."""
    if (document is None) == (collection is None):
        raise ValueError("exactly one of document / collection is required")
    resolved_settings = settings or get_settings()

    if sender.id == author_user_id:
        raise AuthorContactError("own_target", "You are the author - there is nobody to write to.")
    await _enforce_rate_limit(db, sender, resolved_settings)

    author = await db.get(User, author_user_id)
    message = AuthorMessage(
        sender_user_id=sender.id,
        recipient_user_id=author_user_id,
        documentation_id=document.id if document is not None else None,
        collection_id=collection.id if collection is not None else None,
        body=body,
    )
    db.add(message)
    await db.flush()
    db.add(Notification(kind="author_message", user_id=author_user_id, message_id=message.id))
    await db.commit()

    message.email_sent = await _email_author(
        author=author,
        sender=sender,
        body=body,
        kind="document" if document is not None else "collection",
        target_id=message.documentation_id or message.collection_id,
        target_title=document.title if document is not None else collection.name,
        settings=resolved_settings,
    )
    if message.email_sent:
        await db.commit()
    return message
