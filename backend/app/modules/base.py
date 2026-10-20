# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import APIRouter


@dataclass(frozen=True)
class ModuleManifest:
    """Self-description a feature module exposes as `manifest` from its
    app/modules/<key>/__init__.py.

    `key` must match the module's folder name - app.modules.registry uses it
    both to resolve backend/modules.json's `enabled` keys and (unless
    `prefix` overrides it) to derive the module's API prefix, so a mismatch
    would silently split one module's identity in two and it's rejected at
    discovery time.

    `requires` lists the keys of other modules this one only works with
    (e.g. a calendar built on articles). It is advisory: enabling a module
    without what it requires never stops the app, it is logged as a warning
    at startup (registry.check_module_dependencies) so a half-switched-on
    configuration is visible instead of failing in some request later.
    """

    key: str
    router: APIRouter | None = None
    prefix: str | None = None
    tags: list[str] = field(default_factory=list)
    # Called once at application startup when the module is enabled (see
    # app.modules.registry.run_startup_hooks) - for a check that should be
    # said out loud in the console, such as a setting that quietly switches
    # a feature off. Whatever it raises is logged and does not stop the startup.
    on_startup: Callable[[], None] | None = None
    requires: tuple[str, ...] = ()
