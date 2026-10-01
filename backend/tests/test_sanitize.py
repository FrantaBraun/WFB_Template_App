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
