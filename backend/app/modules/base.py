# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

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

    `hooks` is the backend counterpart of the frontend's slots: a map of hook
    name -> async callable through which a module takes part in a flow another
    module owns (e.g. the tickets module turning a contact-form message into a
    ticket) without that module knowing about it. The module that owns the
    flow documents the hook's name, arguments and return value next to its
    definition and calls it with registry.get_enabled_hooks(name) - so only
    *enabled* modules take part - and is expected to survive a hook that
    raises. Nothing is imported in the other direction.

    `background_tasks` are long-running coroutine functions (no arguments)
    started once at application startup, only when the module is enabled
    (registry.start_background_tasks), and cancelled on shutdown - the
    scheduler this application otherwise doesn't have, e.g. polling a mailbox.
    A task that raises is logged and does not stop the application.
    """

    key: str
    router: APIRouter | None = None
    prefix: str | None = None
    tags: list[str] = field(default_factory=list)
    requires: tuple[str, ...] = ()
    hooks: Mapping[str, Callable[..., Awaitable[Any]]] = field(default_factory=dict)
    background_tasks: tuple[Callable[[], Awaitable[None]], ...] = ()
