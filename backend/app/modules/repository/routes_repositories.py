# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Repositories and the live slug check."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.modules.repository import logic, outputs, service
from app.modules.repository.config import RepositoryConfig, get_limits
from app.modules.repository.models import Record, Repository, RepositoryTable
from app.modules.repository.schemas import RepositoryCreate, RepositoryDetail, RepositoryOut, RepositoryUpdate, SlugCheck

router = APIRouter()


@router.get("/repositories")
async def list_repositories(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[RepositoryOut]:
    """The caller's repositories by name, with how many tables and (not deleted) records each has."""
    repositories = (
        await db.scalars(
            select(Repository).where(Repository.owner_id == user.id).order_by(func.lower(Repository.name), Repository.created_at)
        )
    ).all()
    return await outputs.repository_outs(db, repositories)


@router.post("/repositories", status_code=201)
async def create_repository(
    body: RepositoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limits: RepositoryConfig = Depends(get_limits),
) -> RepositoryDetail:
    """`slug` is made from the name when it is left out; a given one must be free (409) and valid (422)."""
    repository = await service.create_repository(
        db,
        user,
        name=body.name,
        description=body.description,
        slug=body.slug,
        color_scheme=body.color_scheme,
        limits=limits,
    )
    return await outputs.repository_detail(db, repository)


@router.get("/slug-check")
async def check_slug(
    scope: Literal["repository", "table", "record"],
    slug: str = Query(max_length=200),
    repository: str | None = Query(default=None, max_length=200, description="the repository's slug, for the table and record scopes"),
    table: str | None = Query(default=None, max_length=200, description="the table's slug, for the record scope"),
    exclude: str | None = Query(default=None, max_length=200, description="the slug the edited row has now"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SlugCheck:
    """Whether `slug` is free in its scope - for the user's repositories, for
    the tables of `repository`, for the records of `table` (deleted ones count)
    - for the live check beside a slug field. A taken slug comes with the
    nearest free one."""
    slug = slug.strip()
    if scope == "repository":
        taken = await service.taken_slugs(db, Repository.slug, Repository.owner_id, user.id)
    else:
        if repository is None or (scope == "record" and table is None):
            raise HTTPException(status_code=422, detail="repository (and table, for records) are required for this scope")
        found = await service.get_repository(db, user, repository)
        if scope == "table":
            taken = await service.taken_slugs(db, RepositoryTable.slug, RepositoryTable.repository_id, found.id)
        else:
            found_table = await service.get_table(db, found, table)
            taken = await service.taken_slugs(db, Record.slug, Record.table_id, found_table.id)
    if exclude:
        taken = taken - {exclude}
    problem = logic.slug_problem(slug)
    if problem:
        return SlugCheck(slug=slug, available=False, reason=problem)
    if slug in taken:
        return SlugCheck(slug=slug, available=False, reason="taken", suggestion=logic.unique_slug(slug, taken))
    return SlugCheck(slug=slug, available=True)


@router.get("/repositories/{repository_slug}")
async def get_repository(
    repository_slug: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> RepositoryDetail:
    return await outputs.repository_detail(db, await service.get_repository(db, user, repository_slug))


@router.patch("/repositories/{repository_slug}")
async def update_repository(
    repository_slug: str,
    body: RepositoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryDetail:
    repository = await service.get_repository(db, user, repository_slug)
    await service.update_repository(db, user, repository, body.model_dump(exclude_unset=True))
    return await outputs.repository_detail(db, repository)


@router.delete("/repositories/{repository_slug}", status_code=204)
async def delete_repository(
    repository_slug: str,
    confirm_name: str | None = Query(default=None, max_length=200, description="must be the repository's exact name"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes the repository with all its tables and records, once its name is confirmed."""
    repository = await service.get_repository(db, user, repository_slug)
    await service.delete_repository(db, repository, confirm_name)
