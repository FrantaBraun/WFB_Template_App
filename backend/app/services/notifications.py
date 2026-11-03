# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.api_document import ApiDocument, ApiDocumentVersion
from app.models.collection import CollectionDocument
from app.models.notification import Notification, Subscription
from app.models.team import TeamMembership
from app.models.user import User
from app.services.email import send_email
from app.services.integration_usage import integrations_using_documents

logger = logging.getLogger(__name__)


async def _integration_names_by_user(db: AsyncSession, doc: ApiDocument) -> dict[UUID, set[str]]:
    """The members of teams whose integrations use this document, each with the
    names of THEIR OWN teams' integrations that do - an integration built on a
    document is affected by every change to it, so the people who own that
    integration are told even when they never subscribed.

    Only when they are allowed to see the document: it is public, or the
    integration belongs to the document's own team (whose members are
    recipients anyway). An integration may still reference a document that
    was made private after it was added, and its team must not learn of that
    document's versions."""
    refs = (await integrations_using_documents(db, [doc.id])).get(doc.id, [])
    refs = [ref for ref in refs if doc.is_public or ref.team_id == doc.team_id]
    if not refs:
        return {}
    names_by_team: dict[UUID, list[str]] = {}
    for ref in refs:
        names_by_team.setdefault(ref.team_id, []).append(ref.name)
    memberships = (
        await db.execute(
            select(TeamMembership.user_id, TeamMembership.team_id).where(TeamMembership.team_id.in_(names_by_team))
        )
    ).all()
    result: dict[UUID, set[str]] = {}
    for user_id, team_id in memberships:
        result.setdefault(user_id, set()).update(names_by_team[team_id])
    return result


def _compose_email(
    doc: ApiDocument, version: ApiDocumentVersion, link: str, integration_names: tuple[str, ...]
) -> tuple[str, str]:
    """Subject and body of the mail about one version. integration_names are
    the integrations of THIS recipient's teams that the document is part of -
    never anyone else's, since integrations are team-private."""
    # What changed for someone consuming the API, counted when the version
    # was recorded (ApiDocumentVersion.change_summary); absent for a first
    # version or when the comparison failed - then the mail just says less.
    summary = version.change_summary or {}
    breaking, warnings = summary.get("breaking", 0), summary.get("warning", 0)
    flag = f" - {breaking} breaking change{'s' if breaking != 1 else ''}" if breaking else ""
    counts = f"Breaking changes: {breaking}. Potentially breaking: {warnings}.\n\n" if breaking or warnings else ""
    affects = (
        f"This affects your integration{'s' if len(integration_names) != 1 else ''}: "
        f"{', '.join(integration_names)}.\n\n"
        if integration_names
        else ""
    )
    if version.content_changed:
        # Same version number, different content: say so, or the mail
        # would announce a "new version" that looks identical to the old one.
        subject = f"{doc.title} changed without a new version number ({version.version}){flag}"
        body = (
            f"The specification of {doc.title} has changed, but its version is still {version.version}.\n\n"
            f"What it said before is kept in the version history.\n\n{counts}{affects}"
            f"View it here: {link}"
        )
    else:
        subject = f"New version of {doc.title}: {version.version}{flag}"
        body = f"{doc.title} has a new version available: {version.version}.\n\n{counts}{affects}View it here: {link}"
    if any(summary.values()):
        body += f"\nWhat changed: {link}/versions/{version.id}/changes"
    return subject, body


async def notify_new_version(
    doc: ApiDocument,
    version: ApiDocumentVersion,
    db: AsyncSession,
    settings: Settings | None = None,
) -> None:
    """Notify a newly-archived version's recipients: every member of
    doc.team_id, unioned with every direct Subscription to doc.id, unioned
    with every Subscription to a Collection that contains doc.id (via
    CollectionDocument - see app/models/collection.py), unioned with the
    members of every team whose integration uses doc.id
    (_integration_names_by_user), deduplicated by user id. Inserts one
    Notification row per recipient - in-app, regardless of whether they have
    a cached email - then sends the email to whichever recipients have one,
    skipped entirely (not attempted) when there are zero recipients or zero
    with an email.

    Recipients are mailed in groups that share one text: nearly everybody
    gets the same mail with one shared To: list (so they can see each other's
    addresses - acceptable for this internal tool, the same judgment call
    already made in app/api/teams/router.py's create_invitation), but a
    recipient whose teams' integrations use the document gets a mail naming
    those integrations, so people with the same set of integrations share a
    mail and one team's integration names never reach another team.

    Never raises: called from process_new_spec
    (app/services/api_document_versions.py) right after a version is
    committed, and a notification failure - DB or email, anything - must
    never be mistaken by that caller for the version-check itself having
    failed. A mail that fails does not stop the groups after it.

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
        integration_names = await _integration_names_by_user(db, doc)
        recipient_ids = set(member_ids) | set(subscriber_ids) | set(collection_subscriber_ids) | set(integration_names)
        if not recipient_ids:
            return

        for user_id in recipient_ids:
            db.add(Notification(user_id=user_id, documentation_id=doc.id, version_id=version.id))
        await db.commit()

        recipients = (
            await db.execute(select(User.id, User.email).where(User.id.in_(recipient_ids), User.email.isnot(None)))
        ).all()
        if not recipients:
            return

        groups: dict[tuple[str, ...], list[str]] = {}
        for user_id, email in recipients:
            groups.setdefault(tuple(sorted(integration_names.get(user_id, ()))), []).append(email)

        link = f"{resolved_settings.frontend_url}/api-docs/{doc.id}"
        for names, emails in groups.items():
            subject, body = _compose_email(doc, version, link, names)
            try:
                await send_email(subject=subject, recipients=emails, body=body, settings=resolved_settings)
            except Exception:
                logger.exception("Failed to e-mail %d recipients of new version %s for document %s", len(emails), version.id, doc.id)
    except Exception:
        logger.exception(
            "Failed to notify recipients of new version %s for document %s", version.id, doc.id
        )
