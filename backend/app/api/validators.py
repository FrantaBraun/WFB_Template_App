# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import re

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_slug(value: str) -> str:
    """Shared by Page and Article write schemas - both are plain
    admin-entered text fields with no server-side auto-generation."""
    if not SLUG_PATTERN.match(value):
        raise ValueError("slug must be lowercase letters, digits and single hyphens only")
    return value
