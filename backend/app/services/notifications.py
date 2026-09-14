# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.collection import CollectionDocument
from app.models.notification import Notification, Subscription
from app.models.team import TeamMembership
from app.models.user import User
from app.services.email import send_email

logger = logging.getLogger(__name__)


async def notify_new_version(
    doc: ApiDocument,
    version: ApiDocumentVersion,
    db: AsyncSession,
    settings: Settings | None = None,
) -> None:
    """Notify a newly-archived version's recipients: every member of
    doc.team_id, unioned with every direct Subscription to doc.id, unioned
    with every Subscription to a Collection that contains doc.id (via
    CollectionDocument - see app/models/collection.py), deduplicated by user
    id. Inserts one Notification row per recipient - in-app, regardless
    of whether they have a cached email - then sends a single email to
    whichever recipients have one, skipped entirely (not attempted) when
    there are zero recipients or zero with an email.

    Never raises: called from process_new_spec
    (app/services/api_document_versions.py) right after a version is
    committed, and a notification failure - DB or email, anything - must
    never be mistaken by that caller for the version-check itself having
    failed.

    settings follows send_email's own convention (falls back to
    get_settings() when omitted) so callers/tests can inject
    mail_test_settings the same way test_teams_router.py already does for
    create_invitation - see test_notifications_service.py. process_new_spec
    itself never passes one (its own signature isn't changed for this), so
    in production this always resolves the real deployment's mail settings;
    tests/conftest.py forces MAIL_SUPPRESS_SEND on session-wide so that
    fallback can never attempt a real SMTP connection.
    """
    try:
        resolved_settings = settings or get_settings()

        member_ids = (
            await db.execute(select(TeamMembership.user_id).where(TeamMembership.team_id == doc.team_id))
        ).scalars().all()
        subscriber_ids = (
            await db.execute(select(Subscription.user_id).where(Subscription.documentation_id == doc.id))
        ).scalars().all()
        collection_subscriber_ids = (
            await db.execute(
                select(Subscription.user_id)
                .join(CollectionDocument, CollectionDocument.collection_id == Subscription.collection_id)
                .where(
                    Subscription.collection_id.isnot(None),
                    CollectionDocument.documentation_id == doc.id,
                )
            )
        ).scalars().all()
        recipient_ids = set(member_ids) | set(subscriber_ids) | set(collection_subscriber_ids)
        if not recipient_ids:
            return

        for user_id in recipient_ids:
            db.add(Notification(user_id=user_id, documentation_id=doc.id, version_id=version.id))
        await db.commit()

        recipient_emails = (
            await db.execute(select(User.email).where(User.id.in_(recipient_ids), User.email.isnot(None)))
        ).scalars().all()
        if not recipient_emails:
            return

        link = f"{resolved_settings.frontend_url}/api-docs/{doc.id}"
        # One shared To: list means recipients can see each other's email
        # addresses - acceptable for this internal tool (same judgment call
        # already made in app/api/teams/router.py's create_invitation); a
        # per-recipient send loop is a one-line change later if that's ever
        # undesirable.
        await send_email(
            subject=f"New version of {doc.title}: {version.version}",
            recipients=recipient_emails,
            body=f"{doc.title} has a new version available: {version.version}.\n\nView it here: {link}",
            settings=resolved_settings,
        )
    except Exception:
        logger.exception(
            "Failed to notify recipients of new version %s for document %s", version.id, doc.id
        )
