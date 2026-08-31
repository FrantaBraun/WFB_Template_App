# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from fastapi import APIRouter, Depends

from app.api.admin import pages as admin_pages
from app.api.deps import require_admin

# require_admin applied once here rather than per-endpoint - every route
# aggregated under this router is admin-only by construction.
router = APIRouter(dependencies=[Depends(require_admin)])
router.include_router(admin_pages.router, prefix="/pages", tags=["admin:pages"])
