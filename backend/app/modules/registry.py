# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Discovery and enable/disable resolution for feature modules under app.modules.

A module is any subpackage of app.modules that exposes a module-level
`manifest` (an app.modules.base.ModuleManifest) from its __init__.py.
discover_modules() finds every module regardless of enabled state - Alembic
must see every module's tables so migrations stay identical across
deployments no matter which modules a given application turns on.
get_enabled_modules() is what actually gates which modules' routers get
mounted; toggling a key in backend/modules.json is a pure config change, it
never touches the DB schema.
"""

import importlib
import json
import logging
import pkgutil
from collections.abc import Iterable
from pathlib import Path

import app.modules as modules_pkg
from app.config import BASE_DIR
from app.modules.base import ModuleManifest

logger = logging.getLogger(__name__)

MODULES_CONFIG_FILE = BASE_DIR / "modules.json"


def load_enabled_module_keys(path: Path = MODULES_CONFIG_FILE) -> list[str]:
    """Read the `enabled` array of keys from backend/modules.json.

    Tracked in git on purpose, unlike .env: .env is untracked and shared by
    every branch checked out in the same working tree, so it silently carried
    one application's module selection into another. modules.json travels
    with its branch, same `{"enabled": [...]}` shape as the frontend's
    public/modules.json. A missing file means no modules (the frontend's
    fallback too); anything other than a list of strings raises, so a typo
    fails loudly at startup instead of quietly unmounting every module.
    """
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("%s not found - no feature modules enabled", path)
        return []
    enabled = config.get("enabled", [])
    if not isinstance(enabled, list) or not all(isinstance(key, str) for key in enabled):
        raise ValueError(f"{path}: `enabled` must be a list of module keys, got {enabled!r}")
    return enabled


def discover_modules() -> list[ModuleManifest]:
    """Import every subpackage of app.modules and collect its manifest.

    A subpackage without a `manifest` attribute, or whose manifest.key
    doesn't match its folder name, is skipped with a warning rather than
    raising - a stray or half-finished package under app.modules shouldn't
    take the whole app down.
    """
    manifests = []
    for _, name, is_pkg in pkgutil.iter_modules(modules_pkg.__path__):
        if not is_pkg:
            continue
        module = importlib.import_module(f"app.modules.{name}")
        manifest = getattr(module, "manifest", None)
        if manifest is None:
            logger.warning("app.modules.%s has no `manifest` attribute - skipped", name)
            continue
        if manifest.key != name:
            logger.warning(
                "app.modules.%s declares manifest.key=%r, expected %r - skipped",
                name,
                manifest.key,
                name,
            )
            continue
        manifests.append(manifest)
    return manifests


def get_enabled_modules(enabled_keys: Iterable[str]) -> list[ModuleManifest]:
    """Discovered modules whose key is listed in enabled_keys (normally
    load_enabled_module_keys()'s result)."""
    enabled_keys = set(enabled_keys)
    return [manifest for manifest in discover_modules() if manifest.key in enabled_keys]


def import_all_module_models() -> None:
    """Import <module>.models for every discovered module that has one.

    Called once from alembic/env.py so a new module's tables are picked up by
    autogenerate without editing that file - mirrors the manual `from
    app.models.user import User` import already there, just automated across
    however many modules exist. Deliberately imports every discovered
    module's models regardless of enabled state (see module docstring above).
    """
    for manifest in discover_modules():
        module = importlib.import_module(f"app.modules.{manifest.key}")
        submodule_names = {name for _, name, _ in pkgutil.iter_modules(module.__path__)}
        if "models" in submodule_names:
            importlib.import_module(f"app.modules.{manifest.key}.models")
