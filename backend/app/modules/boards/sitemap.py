# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The sitemap (sitemap.xml) search engines are pointed at from robots.txt.

It lists the public pages of the frontend - the home page, the category list,
every published category and the legal / contact pages of the modules that are
switched on - under the frontend's address (Settings.frontend_url). Pages that
need a sign-in, the administration and the search results are not in it. The
frontend has no server of its own that could write it, so the backend serves it
(`GET .../sitemap.xml`) and the web server maps /sitemap.xml to that."""

from collections.abc import Iterable
from datetime import datetime, timezone
from urllib.parse import quote
from xml.sax.saxutils import escape

# The sitemap protocol allows 50 000 URLs in one file.
URL_LIMIT = 50_000

# Pages that belong to other modules, listed when that module is enabled. The
# paths are the frontend's (stripe_payment_gate's LEGAL_PATHS, the contact page).
MODULE_PAGES: dict[str, tuple[str, ...]] = {
    "stripe_payment_gate": ("/o-nas", "/obchodni-podminky", "/ochrana-osobnich-udaju", "/cookies"),
    "kontaktni_formular": ("/contact",),
}


def static_paths(enabled_modules: Iterable[str]) -> list[str]:
    """The pages that do not depend on the data: home, the categories and the
    pages of the enabled modules, in a fixed order."""
    enabled = set(enabled_modules)
    paths = ["/", "/categories"]
    for module, pages in MODULE_PAGES.items():
        if module in enabled:
            paths.extend(pages)
    return paths


def category_path(slug: str) -> str:
    return f"/categories/{quote(slug, safe='')}"


def _lastmod(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_sitemap(base_url: str, paths: Iterable[str], dated_paths: Iterable[tuple[str, datetime]]) -> str:
    """The XML: `paths` without a date, `dated_paths` with the moment the page
    last changed. Every address is escaped, so nothing in a slug can break it."""
    base = base_url.rstrip("/")
    entries = [f"  <url><loc>{escape(base + path)}</loc></url>" for path in paths]
    entries.extend(
        f"  <url><loc>{escape(base + path)}</loc><lastmod>{_lastmod(moment)}</lastmod></url>"
        for path, moment in dated_paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(entries) + "\n</urlset>\n"
    )
