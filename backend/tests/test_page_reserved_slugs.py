# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""A static page cannot take the first path segment of a route of this
application or of one of its enabled modules (/articles, /events, /bookings,
/forms ...): the page would sit at the root next to routes that own that word."""

import pytest

from app.api.validators import PAGE_RESERVED_SLUGS, validate_page_slug


@pytest.mark.parametrize("slug", ["articles", "events", "bookings", "forms", "admin", "login", "clanek"])
def test_the_first_segment_of_a_route_is_not_a_page_slug(slug):
    assert slug in PAGE_RESERVED_SLUGS
    with pytest.raises(ValueError, match="reserved"):
        validate_page_slug(slug)


@pytest.mark.parametrize("slug", ["o-projektu", "ochrana-osobnich-udaju", "kontakt", "bookings-info"])
def test_an_ordinary_slug_is_accepted(slug):
    assert validate_page_slug(slug) == slug
