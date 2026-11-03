# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import CollectionDocument
from app.models.integration import Integration, IntegrationCollection, IntegrationDocument
from app.models.team import TeamMembership


@dataclass(frozen=True)
class IntegrationRef:
    id: UUID
    name: str
    team_id: UUID


async def integrations_using_documents(
    db: AsyncSession, document_ids: Iterable[UUID], *, user_id: UUID | None = None
) -> dict[UUID, list[IntegrationRef]]:
    """For each document, the integrations that use it - as a direct member
    (IntegrationDocument) or through a member collection (IntegrationCollection
    + CollectionDocument, the same two ways app/api/integrations/router.py's
    _compute_document_sources merges) - each integration once, by name.
    Documents no integration uses are absent from the result.

    With user_id only integrations of teams that user belongs to are returned:
    integrations are always team-private (never public), so their names must
    reach nobody outside the team - this is the filter every answer to a
    person has to go through; without it (the caller is the notification
    service, which decides recipients itself) it is everybody's."""
    ids = set(document_ids)
    if not ids:
        return {}

    def restrict(statement: Select) -> Select:
        if user_id is not None:
            statement = statement.join(
                TeamMembership,
                (TeamMembership.team_id == Integration.team_id) & (TeamMembership.user_id == user_id),
            )
        return statement

    direct = restrict(
        select(IntegrationDocument.documentation_id, Integration.id, Integration.name, Integration.team_id)
        .select_from(IntegrationDocument)
        .join(Integration, Integration.id == IntegrationDocument.integration_id)
        .where(IntegrationDocument.documentation_id.in_(ids))
    )
    through_collection = restrict(
        select(CollectionDocument.documentation_id, Integration.id, Integration.name, Integration.team_id)
        .select_from(CollectionDocument)
        .join(IntegrationCollection, IntegrationCollection.collection_id == CollectionDocument.collection_id)
        .join(Integration, Integration.id == IntegrationCollection.integration_id)
        .where(CollectionDocument.documentation_id.in_(ids))
    )

    found: dict[UUID, dict[UUID, IntegrationRef]] = {}
    for statement in (direct, through_collection):
        for document_id, integration_id, name, team_id in (await db.execute(statement)).all():
            found.setdefault(document_id, {})[integration_id] = IntegrationRef(integration_id, name, team_id)
    return {
        document_id: sorted(refs.values(), key=lambda ref: (ref.name.lower(), str(ref.id)))
        for document_id, refs in found.items()
    }
