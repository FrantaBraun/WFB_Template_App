# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Boards settings, read from the git-tracked backend/modules/boards.json -
per-application values that follow the branch, like backend/modules.json
(see app/modules/registry.py).

- page_size: how many posts / categories one page of a listing loads.
- points_per_usd, points_per_resonance, points_per_day: the post value
  formula - value = paid USD * points_per_usd + resonances *
  points_per_resonance - whole days of age * points_per_day (see service.py).

The text limits (post title / text, category title / description) are
fixed in schemas.py and the column sizes in models.py, not configured here:
changing one would need a migration.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.config import BASE_DIR

CONFIG_FILE = BASE_DIR / "modules" / "boards.json"


class BoardsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size: int = Field(default=20, ge=1, le=50)
    points_per_usd: int = Field(default=10, ge=0)
    points_per_resonance: int = Field(default=1, ge=0)
    points_per_day: int = Field(default=1, ge=0)


def load_config(path: Path = CONFIG_FILE) -> BoardsConfig:
    """A missing file means the defaults; a malformed one raises (fail at
    startup/first use, not silently with surprising settings)."""
    if not path.exists():
        return BoardsConfig()
    return BoardsConfig.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def get_config() -> BoardsConfig:
    return load_config()
