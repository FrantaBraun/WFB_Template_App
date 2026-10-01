# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import nh3

# Matches exactly what the frontend's shared RichTextEditor
# (src/components/RichTextEditor.tsx: TipTap StarterKit with headings 1-5,
# Image, Link, TextStyle + Color/FontFamily/FontSize) produces. Apply it
# server-side on every write of editor HTML, so a direct API call bypassing
# the editor can't stash a stored-XSS payload in content that is later
# served verbatim to anonymous visitors. Keep the two in sync: anything the
# editor can produce but this list drops is silently lost on save.
_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "ul", "ol", "li", "blockquote",
    "h1", "h2", "h3", "h4", "h5",
    "a", "img", "span",
}
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt"},
    # TextStyle marks render as <span style="color: ...; font-size: ...">.
    "span": {"style"},
}
# Everything else inside a style attribute (position, background:url(...),
# ...) is stripped - only the three properties the toolbar sets survive.
_ALLOWED_STYLE_PROPERTIES = {"color", "font-family", "font-size"}


def sanitize_html(html: str) -> str:
    # link_rel=None: nh3 otherwise force-manages the "a" tag's "rel"
    # attribute itself and rejects it appearing in the allowlist at all.
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        filter_style_properties=_ALLOWED_STYLE_PROPERTIES,
        link_rel=None,
    )
