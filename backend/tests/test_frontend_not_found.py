# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The not-found page is a soft 404 to a crawler (the server answers every
unknown address with the SPA's index.html and status 200), so it must carry a
real description - a missing translation key printed itself into the page's
meta description - and must ask search engines not to index it. The frontend
has no test runner, so this reads its sources."""

import json
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


@pytest.mark.parametrize("language", ["cs", "en"])
def test_the_not_found_page_has_a_title_and_a_description_in_every_language(language):
    texts = json.loads((FRONTEND / "i18n" / "locales" / f"{language}.json").read_text(encoding="utf-8"))["notFound"]

    assert texts["pageTitle"].strip()
    assert texts["pageDescription"].strip()


def test_the_not_found_page_is_not_indexed():
    source = (FRONTEND / "pages" / "NotFound.tsx").read_text(encoding="utf-8")

    assert "noindex: true" in source
