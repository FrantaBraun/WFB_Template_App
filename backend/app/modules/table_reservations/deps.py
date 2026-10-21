# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

LOCAL_ZONE = "Europe/Prague"

_zone_warned = False


def local_now() -> datetime:
    """"Now" as a naive local (Europe/Prague) datetime - what every time of this
    module is. Falls back to the server's own clock, with one warning, where the
    time zone database is missing (tzdata is in requirements.txt)."""
    global _zone_warned
    try:
        return datetime.now(ZoneInfo(LOCAL_ZONE)).replace(tzinfo=None)
    except ZoneInfoNotFoundError:
        if not _zone_warned:
            logger.warning("No time zone database for %s (install tzdata) - using the server's local time", LOCAL_ZONE)
            _zone_warned = True
        return datetime.now()


def get_now() -> datetime:
    """The local "now" as a dependency, so a test can set the clock."""
    return local_now()
