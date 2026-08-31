# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import nh3

# Matches what the frontend's RichTextEditor (Tiptap StarterKit + Image +
# Link) actually produces. Applied server-side on every admin write so a
# direct API call bypassing the editor can't stash a stored-XSS payload in
# Page.content/Article.full_text, which is later served verbatim to
# anonymous visitors of the public detail routes.
_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "ul", "ol", "li",
    "a", "img", "h2", "h3", "blockquote",
}
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt"},
}


def sanitize_html(html: str) -> str:
    # link_rel=None: nh3 otherwise force-manages the "a" tag's "rel"
    # attribute itself and rejects it appearing in the allowlist at all.
    return nh3.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, link_rel=None)
