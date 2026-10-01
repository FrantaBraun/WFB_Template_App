# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings
from app.database import engine
from app.logging_config import configure_logging
from app.models.user import User
from app.modules.event_calendar.permissions import set_editor_check
from app.services.auth_client import auth_client

settings = get_settings()
configure_logging(settings)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup/shutdown hook: closes the shared AuthClient's HTTP
    connection and disposes the DB engine's connection pool on shutdown."""
    logger.info("Application startup")
    yield
    logger.info("Application shutdown")
    await auth_client.aclose()
    await engine.dispose()

with open('./version.json', 'r', encoding='utf-8') as f:
    version = json.load(f)

app = FastAPI(title="Slavíčkovy knihohrátky API", version=version['version'], lifespan=lifespan)

if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)


async def _admins_edit_events(user: User, claims: dict) -> bool:
    """This app's administrators (User.is_admin, the same flag the /admin
    area checks) manage events - not the auth-service role the
    event_calendar module would otherwise look at."""
    return user.is_admin


set_editor_check(_admins_edit_events)

Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")
