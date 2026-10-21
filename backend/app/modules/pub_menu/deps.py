# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

LOCAL_ZONE = "Europe/Prague"

_zone_warned = False


def local_today() -> date:
    """Today's date in the pub's own time zone (Europe/Prague) - what a lunch
    menu's "today" is. Falls back to the server's own clock, with one warning,
    where the time zone database is missing (tzdata is in requirements.txt)."""
    global _zone_warned
    try:
        return datetime.now(ZoneInfo(LOCAL_ZONE)).date()
    except ZoneInfoNotFoundError:
        if not _zone_warned:
            logger.warning("No time zone database for %s (install tzdata) - using the server's local date", LOCAL_ZONE)
            _zone_warned = True
        return date.today()


def get_today() -> date:
    """Today as a dependency, so a test can set the clock."""
    return local_today()
