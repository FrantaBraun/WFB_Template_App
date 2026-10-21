# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Settings of the pub menu module, read from the git-tracked
backend/modules/pub_menu.json - per-application content that follows the branch,
like backend/modules.json (see app/modules/registry.py). What the administrators
edit (the dishes, the lunch menu, the notes) lives in the database, not here.

- currency: the ISO 4217 code prices are shown in (a visitor's browser formats it).
- weeks_back / weeks_ahead: how many weeks before and after the current one the
  public page lets a visitor look at the lunch menu (the week of today is always
  there); asking for a week outside is a 422.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.config import BASE_DIR

CONFIG_FILE = BASE_DIR / "modules" / "pub_menu.json"


class PubMenuConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="CZK", pattern=r"^[A-Z]{3}$")
    weeks_back: int = Field(default=1, ge=0, le=52)
    weeks_ahead: int = Field(default=4, ge=0, le=52)


def load_config(path: Path = CONFIG_FILE) -> PubMenuConfig:
    return PubMenuConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> PubMenuConfig:
    return load_config()
