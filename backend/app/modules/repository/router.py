# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The repository module's endpoints. Every route needs a signed-in user, and
every query is filtered by that user (`owner_id`): what belongs to somebody
else answers 404, never 403, so nothing reveals that it exists."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.modules.repository import routes_repositories, routes_tables

router = APIRouter(dependencies=[Depends(get_current_user)])
router.include_router(routes_repositories.router)
router.include_router(routes_tables.router)
