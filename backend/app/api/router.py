# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter

from app.api.account import router as account_router
from app.api.api_docs import router as api_docs_router
from app.api.auth import router as auth_router
from app.api.collections import router as collections_router
from app.api.integrations import router as integrations_router
from app.api.notifications import router as notifications_router
from app.api.public import api_docs as public_api_docs
from app.api.public import collections as public_collections
from app.api.public import release_news as public_release_news
from app.api.public import version as public_version
from app.api.teams import router as teams_router
from app.modules.registry import get_enabled_modules, load_enabled_module_keys

api_router = APIRouter(prefix="/api")
api_router.include_router(public_version.router, prefix="/public", tags=["public"])
api_router.include_router(public_release_news.router, prefix="/public", tags=["public"])
api_router.include_router(public_api_docs.router, prefix="/public", tags=["public"])
api_router.include_router(public_collections.router, prefix="/public", tags=["public"])
api_router.include_router(auth_router.router, prefix="/auth", tags=["auth"])
api_router.include_router(account_router.router, prefix="/account", tags=["account"])
api_router.include_router(teams_router.router, prefix="/teams", tags=["teams"])
api_router.include_router(api_docs_router.router, prefix="/api-docs", tags=["api-docs"])
api_router.include_router(notifications_router.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(collections_router.router, prefix="/collections", tags=["collections"])
api_router.include_router(integrations_router.router, prefix="/integrations", tags=["integrations"])

# Feature modules (see app/modules/) mount themselves here, gated by
# backend/modules.json's `enabled` array - core routes above are never
# conditional.
for module in get_enabled_modules(load_enabled_module_keys()):
    if module.router is not None:
        api_router.include_router(
            module.router,
            prefix=module.prefix or f"/modules/{module.key}",
            tags=module.tags or [module.key],
        )
