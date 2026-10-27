# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.database import engine
from app.logging_config import configure_logging
from app.modules.registry import load_enabled_module_keys, start_background_tasks, stop_background_tasks
from app.services.auth_client import auth_client
from app.services.scheduler import shutdown_scheduler, start_scheduler

settings = get_settings()
configure_logging(settings)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup/shutdown hook: starts/stops the automatic recheck
    scheduler (guarded by settings.scheduler_enabled, so tests can disable
    it) and the background tasks of every enabled module, and closes the
    shared AuthClient's HTTP connection and disposes the DB engine's
    connection pool on shutdown. The scheduler and the module tasks are
    stopped before either of those, since their jobs use the DB engine - they
    must not still be running once that engine is disposed."""
    logger.info("Application startup")
    if settings.scheduler_enabled:
        start_scheduler()
    background_tasks = start_background_tasks(load_enabled_module_keys())
    yield
    logger.info("Application shutdown")
    await stop_background_tasks(background_tasks)
    if settings.scheduler_enabled:
        shutdown_scheduler()
    await auth_client.aclose()
    await engine.dispose()

with open('./version.json', 'r', encoding='utf-8') as f:
    version = json.load(f)

app = FastAPI(title="API Hub", version=version['version'], lifespan=lifespan)

if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router)
