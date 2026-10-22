# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Limits of the repository module, read from the git-tracked
backend/modules/repository.json - per-application content that follows the
branch, like backend/modules.json (see app/modules/registry.py).

They exist because the application is open to anyone who can register and
stores their data (images included) in our database:

- max_repositories_per_user / max_tables_per_repository /
  max_attributes_per_table / max_records_per_table / max_filters_per_table /
  max_statistics_per_table: how much one person may create.
- max_image_bytes: one image, after decoding.
- max_image_bytes_per_user: all of one person's images together.
- unattached_image_hours: an uploaded image that no record has claimed after
  this long is deleted (see images.purge_unattached).

Validated when the file is loaded, so a typo fails there and not when someone
reaches a limit. A missing file means the defaults below (none of this is
secret). There is no rate limiting in the core or in this module.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

CONFIG_FILE = BASE_DIR / "modules" / "repository.json"


class RepositoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_repositories_per_user: int = Field(default=20, ge=1, le=1000)
    max_tables_per_repository: int = Field(default=50, ge=1, le=500)
    max_attributes_per_table: int = Field(default=50, ge=1, le=200)
    max_records_per_table: int = Field(default=10_000, ge=1, le=1_000_000)
    max_filters_per_table: int = Field(default=50, ge=1, le=500)
    max_statistics_per_table: int = Field(default=20, ge=1, le=200)
    max_image_bytes: int = Field(default=3 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    max_image_bytes_per_user: int = Field(default=200 * 1024 * 1024, ge=1024)
    unattached_image_hours: int = Field(default=24, ge=1, le=24 * 30)

    @model_validator(mode="after")
    def _one_image_fits_the_quota(self) -> "RepositoryConfig":
        if self.max_image_bytes > self.max_image_bytes_per_user:
            raise ValueError("max_image_bytes is more than max_image_bytes_per_user")
        return self


def load_config(path: Path = CONFIG_FILE) -> RepositoryConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("%s not found - using the default limits of the repository module", path)
        return RepositoryConfig()
    return RepositoryConfig.model_validate(raw)


@lru_cache
def get_limits() -> RepositoryConfig:
    """FastAPI dependency (tests override it): the limits, read once per process."""
    return load_config()
