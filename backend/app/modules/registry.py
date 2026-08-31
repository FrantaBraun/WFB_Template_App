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
mounted; toggling Settings.enabled_modules is a pure config change, it never
touches the DB schema.
"""

import importlib
import logging
import pkgutil

import app.modules as modules_pkg
from app.config import Settings
from app.modules.base import ModuleManifest

logger = logging.getLogger(__name__)


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


def get_enabled_modules(settings: Settings) -> list[ModuleManifest]:
    """Discovered modules whose key is listed in settings.enabled_modules."""
    enabled_keys = set(settings.enabled_modules)
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
