# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter

from app.api.account import router as account_router
from app.api.auth import router as auth_router
from app.api.public import release_news as public_release_news
from app.api.public import version as public_version
from app.modules.registry import get_enabled_modules, load_enabled_module_keys

api_router = APIRouter(prefix="/api")
api_router.include_router(public_version.router, prefix="/public", tags=["public"])
api_router.include_router(public_release_news.router, prefix="/public", tags=["public"])
api_router.include_router(auth_router.router, prefix="/auth", tags=["auth"])
api_router.include_router(account_router.router, prefix="/account", tags=["account"])

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
