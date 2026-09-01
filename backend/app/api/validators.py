# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import re

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# First path segment of every real frontend/backend route today. Page slugs
# render at root level (/{slug}), so one matching a real route would make
# React Router's own static-route-wins ranking silently swallow it - the
# admin who saved it would see no error, just a page that never renders
# anywhere. Article slugs live under /clanek/ and aren't at risk of this.
# Keep this in sync with frontend/src/App.tsx's route table.
PAGE_RESERVED_SLUGS = frozenset({
    "login", "register", "account", "oauth", "consent", "consent-rejected",
    "version", "release-news", "admin", "clanek", "api", "uploads",
})


def validate_slug(value: str) -> str:
    """Shared by Page and Article write schemas - both are plain
    admin-entered text fields with no server-side auto-generation."""
    if not SLUG_PATTERN.match(value):
        raise ValueError("slug must be lowercase letters, digits and single hyphens only")
    return value


def validate_page_slug(value: str) -> str:
    """Page-specific: format check plus the reserved-word guard above."""
    value = validate_slug(value)
    if value in PAGE_RESERVED_SLUGS:
        raise ValueError(f'"{value}" is reserved for an existing route and cannot be used as a page slug')
    return value
