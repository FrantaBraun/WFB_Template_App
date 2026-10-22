# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Small SQL helpers that more than one module needs."""


def like_pattern(text: str) -> str:
    """`text` as a LIKE / ILIKE pattern that matches it anywhere in a value: `%`, `_`
    and the escape character itself are taken literally, so a search for "100%" or
    "snake_case" finds that and not everything. The query must say `escape="\\\\"`
    (SQLAlchemy: `column.ilike(like_pattern(text), escape="\\\\")`)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\%").replace("_", "\_")
    return f"%{escaped}%"
