# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Who may see an article - the single place these rules live.

Other modules built on articles (the event calendar, bookings) import these
two SQL conditions instead of restating them, so "visible" can't drift
between modules.

- listed(today): published and *today* inside the display window. This is
  what the wall, listings and anything "current" show. Browsing a past or
  future month never bypasses an embargo (display_from) or expiry
  (display_to): the window is always judged as of today.
- findable(today): listed, or archived. Archived articles are out of the
  listings but stay reachable through calendars, archives and search, and
  the display window does not apply to them. Drafts are in neither.
"""

from datetime import date

from sqlalchemy import and_, or_

from app.modules.articles.models import STATUS_ARCHIVED, STATUS_PUBLISHED, Article


def listed(today: date):
    return and_(
        Article.status == STATUS_PUBLISHED,
        or_(Article.display_from.is_(None), Article.display_from <= today),
        or_(Article.display_to.is_(None), Article.display_to >= today),
    )


def findable(today: date):
    return or_(listed(today), Article.status == STATUS_ARCHIVED)
