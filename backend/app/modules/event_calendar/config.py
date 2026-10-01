# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Event calendar settings, read from the git-tracked
backend/modules/event_calendar.json - per-application content that follows
the branch, like backend/modules.json (see app/modules/registry.py).

- editor_roles: auth-service roles (the JWT's role_name claim) allowed to
  create and edit events, unless the application replaced that check with
  its own (see permissions.set_editor_check).
- page_size: how many upcoming events one page of the public list loads.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.config import BASE_DIR

CONFIG_FILE = BASE_DIR / "modules" / "event_calendar.json"


class EventCalendarConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    editor_roles: list[str] = Field(default_factory=lambda: ["admin"])
    page_size: int = Field(default=10, ge=1, le=50)


def load_config(path: Path = CONFIG_FILE) -> EventCalendarConfig:
    """A missing file means the defaults; a malformed one raises (fail at
    startup/first use, not silently with surprising permissions)."""
    if not path.exists():
        return EventCalendarConfig()
    return EventCalendarConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> EventCalendarConfig:
    return load_config()
