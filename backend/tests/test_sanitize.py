# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""app.services.sanitize keeps everything the shared RichTextEditor
produces and strips anything that could execute or escape the content."""

import pytest

from app.services.sanitize import sanitize_html


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_keeps_every_editor_heading_level(level):
    html = f"<h{level}>Title</h{level}>"
    assert sanitize_html(html) == html


def test_keeps_text_style_spans():
    html = '<p><span style="color: #ff0000; font-family: Georgia, serif; font-size: 24px">Hi</span></p>'
    cleaned = sanitize_html(html)
    assert "color:#ff0000" in cleaned.replace(" ", "")
    assert "font-family:Georgia,serif" in cleaned.replace(" ", "")
    assert "font-size:24px" in cleaned.replace(" ", "")


def test_strips_disallowed_style_properties():
    cleaned = sanitize_html('<span style="color: red; position: fixed; background: url(x)">x</span>')
    assert "position" not in cleaned
    assert "background" not in cleaned
    assert "color" in cleaned


def test_keeps_formatting_lists_links_and_images():
    html = (
        '<p><strong>b</strong> <em>i</em> <u>u</u> <s>s</s></p>'
        '<ul><li>a</li></ul><ol><li>b</li></ol><blockquote><p>q</p></blockquote>'
        '<p><a href="/events/x">link</a></p><img src="https://example.com/a.png" alt="a">'
    )
    cleaned = sanitize_html(html)
    for fragment in ("<strong>", "<em>", "<u>", "<s>", "<ul>", "<ol>", "<blockquote>", 'href="/events/x"', 'src="https://example.com/a.png"'):
        assert fragment in cleaned


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        '<img src="x" onerror="alert(1)">',
        '<a href="javascript:alert(1)">x</a>',
        '<p style="color:red" onclick="alert(1)">x</p>',
        '<iframe src="https://evil.example"></iframe>',
    ],
)
def test_strips_executable_content(payload):
    cleaned = sanitize_html(payload).lower()
    assert "<script" not in cleaned
    assert "onerror" not in cleaned
    assert "onclick" not in cleaned
    assert "javascript:" not in cleaned
    assert "<iframe" not in cleaned


# --- Tables, alignment, rules, code, video embeds ---------------------------------


def test_keeps_tables_with_header_cells_and_spans():
    html = (
        '<table><tbody><tr><th colspan="2" style="text-align:center">H</th></tr>'
        '<tr><td rowspan="2">a</td><td>b</td></tr></tbody></table>'
    )
    cleaned = sanitize_html(html)
    for fragment in ("<table>", "<th", 'colspan="2"', 'rowspan="2"', "text-align:center", "<td"):
        assert fragment in cleaned


@pytest.mark.parametrize("tag", ["p", "h1", "h3", "h5"])
def test_keeps_text_align_on_paragraphs_and_headings(tag):
    cleaned = sanitize_html(f'<{tag} style="text-align: right">x</{tag}>')
    assert "text-align:right" in cleaned.replace(" ", "")


def test_keeps_horizontal_rule_and_code_block():
    cleaned = sanitize_html("<hr><pre><code>a &lt; b</code></pre><p>x <code>y</code></p>")
    for fragment in ("<hr>", "<pre>", "<code>"):
        assert fragment in cleaned


@pytest.mark.parametrize(
    "src",
    [
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=30",
        "https://player.vimeo.com/video/76979871",
        "https://player.vimeo.com/video/76979871?h=8272103f6e",
    ],
)
def test_keeps_youtube_and_vimeo_embeds_and_hardens_them(src):
    cleaned = sanitize_html(f'<iframe src="{src}" allowfullscreen allow="camera; microphone" onload="x()"></iframe>')
    assert f'src="{src}"' in cleaned
    assert "allowfullscreen" in cleaned
    assert 'loading="lazy"' in cleaned
    assert 'referrerpolicy="strict-origin-when-cross-origin"' in cleaned
    assert "sandbox=" in cleaned
    assert "allow=" not in cleaned
    assert "onload" not in cleaned


@pytest.mark.parametrize(
    "src",
    [
        "https://evil.example/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "http://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        "https://www.youtube-nocookie.com.evil.example/embed/dQw4w9WgXcQ",
        "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ/../../x",
        "https://www.youtube-nocookie.com/embed/short",
        "https://player.vimeo.com/video/abc",
        "https://player.vimeo.com/video/123?x=<script>",
        "//www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
    ],
)
def test_drops_iframes_from_anywhere_else(src):
    cleaned = sanitize_html(f'<p>before</p><iframe src="{src}"></iframe><p>after</p>')
    assert "<iframe" not in cleaned
    assert "<p>before</p>" in cleaned and "<p>after</p>" in cleaned


def test_drops_iframe_without_src_and_srcdoc():
    cleaned = sanitize_html('<iframe></iframe><iframe srcdoc="<script>alert(1)</script>"></iframe>')
    assert "<iframe" not in cleaned
    assert "srcdoc" not in cleaned


def test_strips_style_properties_that_load_or_position_on_every_styled_tag():
    cleaned = sanitize_html(
        '<table><tbody><tr><td style="background:url(https://evil.example/x);position:absolute;text-align:left">x</td></tr></tbody></table>'
        '<p style="color:red;behavior:url(x)">y</p>'
    )
    assert "url(" not in cleaned
    assert "position" not in cleaned
    assert "behavior" not in cleaned
    assert "text-align:left" in cleaned.replace(" ", "")
