# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Tables and their attributes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.repository import outputs, service
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.schemas import AttributesReplace, TableCreate, TableOrder, TableOut, TableSummary, TableUpdate

router = APIRouter(prefix="/repositories/{repository_slug}")


@router.get("/tables")
async def list_tables(
    repository_slug: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[TableSummary]:
    repository = await service.get_repository(db, user, repository_slug)
    return await outputs.table_summaries(db, await service.list_tables(db, repository.id))


@router.post("/tables", status_code=201)
async def create_table(
    repository_slug: str,
    body: TableCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> TableOut:
    """A new table has no attributes yet - save them with PUT .../attributes."""
    repository = await service.get_repository(db, user, repository_slug)
    table = await service.create_table(
        db,
        repository,
        name=body.name,
        description=body.description,
        slug=body.slug,
        view_type=body.view_type,
        limits=limits,
    )
    return await outputs.table_detail(db, table)


@router.put("/table-order", status_code=204)
async def reorder_tables(
    repository_slug: str, body: TableOrder, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    """Every table of the repository exactly once, in the order they should appear."""
    repository = await service.get_repository(db, user, repository_slug)
    await service.reorder_tables(db, repository, body.ids)


@router.get("/tables/{table_slug}")
async def get_table(
    repository_slug: str, table_slug: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> TableOut:
    repository = await service.get_repository(db, user, repository_slug)
    return await outputs.table_detail(db, await service.get_table(db, repository, table_slug))


@router.patch("/tables/{table_slug}")
async def update_table(
    repository_slug: str,
    table_slug: str,
    body: TableUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableOut:
    repository = await service.get_repository(db, user, repository_slug)
    table = await service.get_table(db, repository, table_slug)
    await service.update_table(db, repository, table, body.model_dump(exclude_unset=True))
    return await outputs.table_detail(db, table)


@router.put("/tables/{table_slug}/attributes")
async def replace_attributes(
    repository_slug: str,
    table_slug: str,
    body: AttributesReplace,
    confirm_purge: bool = Query(
        default=False, description="agree to delete the values of the attributes this list leaves out"
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> TableOut:
    """Makes the table's attributes exactly the list sent, in that order (new
    ids are added, unlisted ones removed). Removing an attribute that records
    hold values for answers 409 with `purge_required` until `confirm_purge` is
    set. The type of a saved attribute, and what a reference points at, cannot
    change."""
    repository = await service.get_repository(db, user, repository_slug)
    table = await service.get_table(db, repository, table_slug)
    await service.replace_attributes(
        db, repository, table, body.attributes, confirm_purge=confirm_purge, limits=limits
    )
    return await outputs.table_detail(db, table)


@router.delete("/tables/{table_slug}", status_code=204)
async def delete_table(
    repository_slug: str,
    table_slug: str,
    confirm_name: str | None = Query(default=None, max_length=200, description="must be the table's exact name"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes the table with its attributes and records, once its name is
    confirmed - refused (409, `referenced_by`) while another table's attribute
    points at it."""
    repository = await service.get_repository(db, user, repository_slug)
    table = await service.get_table(db, repository, table_slug)
    await service.delete_table(db, repository, table, confirm_name)
