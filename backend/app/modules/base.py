# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

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
    """

    key: str
    router: APIRouter | None = None
    prefix: str | None = None
    tags: list[str] = field(default_factory=list)
