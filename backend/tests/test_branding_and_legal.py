# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""Guards for the application's name (short ApiVerCon, full "ApiVerCon - Api
Version Control System") and for the About, Terms and Privacy pages.

The pages are texts in the frontend's `legal` locales around the provider's
details from `public/legal.json`; there is no frontend test runner, so what can
silently drift is checked here by reading those files: no trace of the old
name, the new name where it is shown, the Czech and English texts saying the
same things with the same placeholders, every placeholder one the page fills
in, and the browser-storage table of the Privacy page naming every key the
code actually writes."""

import json
import re
from pathlib import Path

import pytest

from app.config import Settings
from app.main import app

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend"
LOCALES = FRONTEND / "src" / "i18n" / "locales"

SHORT_NAME = "ApiVerCon"
FULL_NAME = "ApiVerCon - Api Version Control System"
# Case-sensitive on purpose: the lower-case, hyphenated `api-hub` is the git branch and stays.
OLD_NAMES = re.compile(r"API[ -]Hub|Api[ -]Hub|ApiHub|api hub")
# What config/legal.ts's legalVars() puts at the legal texts' disposal.
PLACEHOLDERS = {"app", "fullName", "name", "ico", "dic", "address", "registration", "email", "phone", "web", "service", "effectiveFrom", "logDays"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def texts_in(value, path=""):
    """Every string in a nested JSON value with where it is."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from texts_in(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from texts_in(item, f"{path}.{key}" if path else key)


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"{{\s*(\w+)\s*}}", text))


def shape(value):
    """The structure of a JSON value without its texts: keys, list lengths and the placeholders of each string."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(item) for item in value]
    return sorted(placeholders(value)) if isinstance(value, str) else value


# --- the name -----------------------------------------------------------------------


def sources_to_scan():
    patterns = [
        (BACKEND / "app", "*.py"),
        (FRONTEND / "src", "*.ts"),
        (FRONTEND / "src", "*.tsx"),
        (FRONTEND / "src", "*.json"),
        (FRONTEND / "public", "*.json"),
    ]
    for root, pattern in patterns:
        yield from root.rglob(pattern)
    for single in (BACKEND / "version.json", BACKEND / "release_news.json", FRONTEND / "index.html", REPO / "README.md", REPO / "CLAUDE.md"):
        yield single


def test_no_trace_of_the_old_name_is_left():
    """Migrations keep their historical names (they are identifiers), and so do the branch and the database."""
    found = []
    for path in sources_to_scan():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if OLD_NAMES.search(line):
                found.append(f"{path.relative_to(REPO)}:{number}: {line.strip()[:100]}")
    assert found == []


def test_the_api_title_and_the_version_files_carry_the_full_name():
    assert app.title == FULL_NAME
    assert load(BACKEND / "version.json")["description"] == FULL_NAME
    assert load(FRONTEND / "public" / "version.json")["description"] == FULL_NAME
    assert f"<title>{FULL_NAME}</title>" in (FRONTEND / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_the_locales_name_the_application(lang):
    locale = load(LOCALES / f"{lang}.json")

    assert locale["nav"] == {"brand": SHORT_NAME, "fullName": FULL_NAME}
    assert locale["home"]["pageTitle"] == FULL_NAME
    assert (locale["home"]["hero"]["title"], locale["home"]["hero"]["fullName"]) == (SHORT_NAME, "Api Version Control System")
    assert locale["meta"]["description"].startswith(SHORT_NAME) and "Api Version Control System" in locale["meta"]["description"]
    assert SHORT_NAME in locale["home"]["pageDescription"] and "Api Version Control System" in locale["home"]["pageDescription"]


# --- the legal texts ----------------------------------------------------------------


def test_the_czech_and_english_legal_texts_say_the_same_things():
    cs, en = load(LOCALES / "legal.cs.json"), load(LOCALES / "legal.en.json")

    assert shape(cs) == shape(en)


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_the_legal_texts_use_only_placeholders_the_page_fills_in(lang):
    unknown = {
        path: sorted(placeholders(text) - PLACEHOLDERS)
        for path, text in texts_in(load(LOCALES / f"legal.{lang}.json"))
        if placeholders(text) - PLACEHOLDERS
    }

    assert unknown == {}


def test_every_placeholder_is_one_legal_vars_provides():
    source = (FRONTEND / "src" / "config" / "legal.ts").read_text(encoding="utf-8")
    body = source[source.index("export function legalVars") :]

    missing = [name for name in PLACEHOLDERS if not re.search(rf"\b{name}\b\s*[:,]", body)]

    assert missing == []


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_the_texts_the_pages_look_up_exist(lang):
    legal = load(LOCALES / f"legal.{lang}.json")

    for key in ("about", "terms", "privacy"):
        assert legal["nav"][key] and legal[key]["title"] and legal[key]["pageDescription"]
    for field in ("name", "ico", "dic", "address", "registration", "email", "phone"):
        assert legal["provider"]["fields"][field]
    for column in ("name", "kind", "purpose", "duration"):
        assert legal["privacy"]["storage"]["columns"][column]
    for list_key in (["about", "sections"], ["about", "closingSections"], ["terms", "sections"], ["privacy", "sections"],
                     ["privacy", "storage", "intro"], ["privacy", "storage", "closing"], ["privacy", "closingSections"], ["privacy", "gdprSections"]):
        node = legal
        for part in list_key:
            node = node[part]
        assert isinstance(node, list) and node, list_key
        assert all(section["title"] and (section.get("paragraphs") or section.get("items")) for section in node)


def test_the_registration_notice_links_both_pages():
    for lang in ("cs", "en"):
        notice = load(LOCALES / f"{lang}.json")["register"]["legalNotice"]
        assert "<terms>" in notice and "</terms>" in notice and "<privacy>" in notice and "</privacy>" in notice


def test_legal_json_has_the_shape_the_pages_read():
    legal = load(FRONTEND / "public" / "legal.json")

    assert set(legal) == {"provider", "service", "dpoEmail", "effectiveFrom", "gdpr", "logRetentionDays", "extraStorage"}
    assert set(legal["provider"]) == {"name", "ico", "dic", "vatPayer", "address", "registration", "email", "phone", "web"}
    assert isinstance(legal["gdpr"], bool) and isinstance(legal["extraStorage"], list)
    # The Privacy page says how long logs are kept; that must be what the backend does unless the server's own .env says otherwise.
    assert legal["logRetentionDays"] == Settings.model_fields["logging_days_history"].default


# --- the browser-storage table ------------------------------------------------------


def storage_keys_in_code() -> set[str]:
    """Every localStorage / sessionStorage key the core frontend code (not the optional modules) uses."""
    keys = set()
    for path in (FRONTEND / "src").rglob("*.ts*"):
        relative = path.relative_to(FRONTEND / "src").as_posix()
        if relative.startswith("modules/"):
            continue
        text = path.read_text(encoding="utf-8")
        if "localStorage" not in text and "sessionStorage" not in text:
            continue
        keys.update(re.findall(r"(?:local|session)Storage\.\w+\(\s*'([^']+)'", text))
        keys.update(re.findall(r"const\s+\w*KEY\w*\s*=\s*'([^']+)'", text))
    # i18next's language detector caches the choice under its default key.
    if "caches: ['localStorage']" in (FRONTEND / "src" / "i18n" / "index.ts").read_text(encoding="utf-8"):
        keys.add("i18nextLng")
    return keys


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_the_privacy_page_lists_every_storage_key_the_code_uses(lang):
    listed = {item["name"] for item in load(LOCALES / f"legal.{lang}.json")["privacy"]["storage"]["items"]}
    used = storage_keys_in_code()

    assert used >= {"access_token", "refresh_token", "dark_mode", "i18nextLng"}  # the scan itself works
    assert used - listed == set(), "write the new key into privacy.storage.items of both legal locales"
    assert listed - used == set(), "a key the Privacy page lists is no longer written by the code"
