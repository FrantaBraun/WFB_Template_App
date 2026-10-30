# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""What HomeRepository tells search engines. The frontend has no test runner, so
these read its sources: the static tags in index.html (all a crawler that does
not run JavaScript sees) are the home page's Czech text and must stay equal to
cs.json, the descriptions fit a search result, the share image has the size
link previews want, robots.txt / sitemap.xml are written by the build (a file
in public/ would collide with them), and every page except the home page keeps
itself out of the index."""

import json
import re
import struct
from html import unescape
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
SRC = FRONTEND / "src"


def _locale(language: str) -> dict:
    return json.loads((SRC / "i18n" / "locales" / f"{language}.json").read_text(encoding="utf-8"))


def _index_html() -> str:
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


def _meta(html: str, attribute: str, key: str) -> str:
    match = re.search(rf'<meta\s+{attribute}="{re.escape(key)}"\s+content="([^"]*)"', html)
    assert match, f"index.html has no <meta {attribute}={key!r}>"
    return unescape(match.group(1))


def _title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    assert match, "index.html has no <title>"
    return unescape(match.group(1)).strip()


def test_the_static_tags_in_index_html_are_the_czech_home_page_text():
    cs = _locale("cs")
    html = _index_html()
    title = f"{cs['home']['metaTitle']} — {cs['nav']['brand']}"

    assert _title(html) == title
    assert _meta(html, "property", "og:title") == title
    assert _meta(html, "property", "og:site_name") == cs["nav"]["brand"]
    assert _meta(html, "name", "description") == cs["meta"]["description"]
    assert _meta(html, "property", "og:description") == cs["meta"]["description"]
    assert _meta(html, "property", "og:locale") == "cs_CZ"
    assert _meta(html, "name", "twitter:card") == "summary_large_image"


def test_index_html_does_not_pin_a_canonical_address_that_would_be_wrong_for_every_other_page():
    assert 'rel="canonical"' not in _index_html()


@pytest.mark.parametrize("language", ["cs", "en"])
def test_the_descriptions_and_titles_fit_a_search_result(language):
    texts = _locale(language)
    title = f"{texts['home']['metaTitle']} — {texts['nav']['brand']}"

    assert 60 <= len(texts["meta"]["description"]) <= 160
    assert len(title) <= 70
    # the template's own wording must not survive on a real application
    assert "With FBraun" not in texts["meta"]["description"]


def test_the_share_image_is_the_size_link_previews_want():
    data = (FRONTEND / "public" / "og-image.png").read_bytes()

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (1200, 630)
    assert len(data) < 1_000_000


def test_robots_and_sitemap_are_written_by_the_build_not_kept_in_public():
    assert not (FRONTEND / "public" / "robots.txt").exists()
    assert not (FRONTEND / "public" / "sitemap.xml").exists()
    plugin = (FRONTEND / "vite-plugins" / "seo.ts").read_text(encoding="utf-8")
    assert "export const SITEMAP_PATHS = ['/']" in plugin
    assert "seoFiles(" in (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")


def _pages_that_must_stay_out_of_the_index() -> list[Path]:
    paths = [p for p in (SRC / "pages").glob("*.tsx") if p.name != "HomePage.tsx"]
    paths += (SRC / "modules" / "repository").glob("*.tsx")
    return sorted(p for p in paths if "usePageMeta(" in p.read_text(encoding="utf-8"))


def test_the_page_walk_finds_the_pages():
    names = {p.name for p in _pages_that_must_stay_out_of_the_index()}
    assert {"Login.tsx", "NotFound.tsx", "TablePage.tsx", "RecordPage.tsx"} <= names


@pytest.mark.parametrize("path", _pages_that_must_stay_out_of_the_index(), ids=lambda p: p.name)
def test_every_page_but_the_home_page_is_noindex(path):
    assert "noindex: true" in path.read_text(encoding="utf-8")
