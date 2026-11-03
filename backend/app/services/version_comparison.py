# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import asyncio
import logging
from collections import OrderedDict
from uuid import UUID

from app.models.api_document import ApiDocumentVersion
from app.services.openapi_spec import parse_spec
from app.services.spec_diff import diff_specs
from app.services.spec_storage import read_spec_file

logger = logging.getLogger(__name__)

# Comparing two versions means reading and parsing two spec files, and a
# list of an integration's documents asks for it once per pinned document on
# every request. A version's file never changes, so the answer for a pair of
# version ids is good forever: it is kept (small - three counts) for as long
# as the process lives, the oldest dropped first once there are too many.
_CACHE: OrderedDict[tuple[UUID, UUID], dict[str, int]] = OrderedDict()
_CACHE_SIZE = 1000


def _summarise(old_raw: bytes, new_raw: bytes) -> dict[str, int]:
    return diff_specs(parse_spec(old_raw).document, parse_spec(new_raw).document).summary()


async def compare_versions(
    uploads_dir: str, base: ApiDocumentVersion, target: ApiDocumentVersion
) -> dict[str, int] | None:
    """What changed from `base` to `target`, counted by severity
    ({"breaking": n, "warning": n, "info": n}, app/services/spec_diff.py), or
    None when it cannot be worked out - a stored file that is gone or no
    longer parses. Never raises, and a failure is not remembered: the file
    may come back."""
    key = (base.id, target.id)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    try:
        old_raw = read_spec_file(uploads_dir, base.storage_path)
        new_raw = read_spec_file(uploads_dir, target.storage_path)
        summary = await asyncio.to_thread(_summarise, old_raw, new_raw)  # CPU work: off the event loop
    except Exception:
        logger.exception("Cannot compare version %s with version %s", base.id, target.id)
        return None
    _CACHE[key] = summary
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return summary
