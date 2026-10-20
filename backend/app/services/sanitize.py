# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import re

import nh3

# Matches exactly what the frontend's shared RichTextEditor
# (src/components/RichTextEditor.tsx: TipTap StarterKit with headings 1-5,
# Image, Link, TextStyle + Color/FontFamily/FontSize, TextAlign, tables, the
# video-embed node) produces. Apply it server-side on every write of editor
# HTML, so a direct API call bypassing the editor - or the editor's raw HTML
# source mode - can't stash a stored-XSS payload in content that is later
# served verbatim to anonymous visitors. Keep the two in sync: anything the
# editor can produce but this list drops is silently lost on save.
_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "ul", "ol", "li", "blockquote",
    "h1", "h2", "h3", "h4", "h5",
    "a", "img", "span",
    "hr", "pre", "code",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "iframe",
}
_STYLED_TAGS = {"span", "p", "h1", "h2", "h3", "h4", "h5", "th", "td"}
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt"},
    # TextStyle marks render as <span style="color: ...; font-size: ...">,
    # TextAlign as style="text-align: ..." on paragraphs and headings.
    **{tag: {"style"} for tag in _STYLED_TAGS},
    "th": {"style", "colspan", "rowspan"},
    "td": {"style", "colspan", "rowspan"},
    # Only the video embed's own attributes; loading / referrerpolicy /
    # sandbox are forced below rather than trusted from the input.
    "iframe": {"src", "allowfullscreen", "title"},
}
# Everything else inside a style attribute (position, background:url(...),
# ...) is stripped - only the properties the toolbar sets survive.
_ALLOWED_STYLE_PROPERTIES = {"color", "font-family", "font-size", "text-align"}

# The only places an iframe may load from: the privacy-friendly YouTube
# embed host and Vimeo's player, with just the embed path and a short
# plain query (e.g. ?h=<hash> for unlisted Vimeo videos). Keep in sync with
# the frontend's components/videoEmbed.ts, which produces exactly these.
_QUERY = r"(?:\?[A-Za-z0-9=&_.-]{1,60})?"
_IFRAME_SRC_PATTERNS = (
    re.compile(rf"^https://www\.youtube-nocookie\.com/embed/[A-Za-z0-9_-]{{11}}{_QUERY}$"),
    re.compile(rf"^https://player\.vimeo\.com/video/[0-9]{{1,12}}{_QUERY}$"),
)

# A video can't read the page or navigate it away, but still needs scripts,
# its own origin and popups (the "watch on" link) to play.
_IFRAME_FORCED_ATTRIBUTES = {
    "loading": "lazy",
    "referrerpolicy": "strict-origin-when-cross-origin",
    "sandbox": "allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox",
}

# nh3 keeps an iframe whose src the filter rejected, just without the src.
_SRCLESS_IFRAME = re.compile(r"<iframe\b(?![^>]*\ssrc=)[^>]*>\s*</iframe>")


def _filter_attribute(tag: str, attribute: str, value: str) -> str | None:
    if tag == "iframe" and attribute == "src":
        return value if any(pattern.match(value) for pattern in _IFRAME_SRC_PATTERNS) else None
    return value


def sanitize_html(html: str) -> str:
    # link_rel=None: nh3 otherwise force-manages the "a" tag's "rel"
    # attribute itself and rejects it appearing in the allowlist at all.
    cleaned = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        attribute_filter=_filter_attribute,
        set_tag_attribute_values={"iframe": _IFRAME_FORCED_ATTRIBUTES},
        filter_style_properties=_ALLOWED_STYLE_PROPERTIES,
        link_rel=None,
    )
    return _SRCLESS_IFRAME.sub("", cleaned)
