# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter

from app.api.account import router as account_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.pages import router as pages_router
from app.api.public import release_news as public_release_news
from app.api.public import version as public_version
from app.config import get_settings
from app.modules.registry import get_enabled_modules

api_router = APIRouter(prefix="/api")
api_router.include_router(public_version.router, prefix="/public", tags=["public"])
api_router.include_router(public_release_news.router, prefix="/public", tags=["public"])
api_router.include_router(auth_router.router, prefix="/auth", tags=["auth"])
api_router.include_router(account_router.router, prefix="/account", tags=["account"])
api_router.include_router(pages_router.router, prefix="/pages", tags=["pages"])
api_router.include_router(admin_router.router, prefix="/admin", tags=["admin"])

# Feature modules (see app/modules/) mount themselves here, gated by
# Settings.enabled_modules - core routes above are never conditional.
for module in get_enabled_modules(get_settings()):
    if module.router is not None:
        api_router.include_router(
            module.router,
            prefix=module.prefix or f"/modules/{module.key}",
            tags=module.tags or [module.key],
        )
