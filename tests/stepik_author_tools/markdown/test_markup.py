"""Behavioral regression tests for markdown.markup."""

from stepik_author_tools.markdown.markup import blocks, canonical, fragment


def test_html_semantics() -> None:
    assert canonical(
        '<div class="editor"><p id="x">A <span>B</span></p>\n<p>C</p></div>'
    ) == canonical("<p>A B</p><p>C</p>")
    assert canonical("<p><b>Bold</b>&nbsp;text</p>") == canonical(
        "<p><strong>Bold</strong> text</p>"
    )
    for a, b in [("x = 'a b'", "x = 'ab'"), ("    x", "  x")]:
        assert canonical(f"<pre><code>{a}</code></pre>") != canonical(
            f"<pre><code>{b}</code></pre>"
        )
    assert canonical('<a href="/one">link</a>') != canonical('<a href="/two">link</a>')
    assert canonical('<img src="a" alt="one"/>') != canonical('<img src="a" alt="two"/>')
    assert canonical('<p style="color:red">x</p>') != canonical('<p style="color:blue">x</p>')


def test_split_blocks_preserves_escaped_text_beside_tags() -> None:
    html = "Show &lt;b&gt; &amp; &lt;i&gt;<p>Example</p>"
    assert blocks(html) == ["Show &lt;b&gt; &amp; &lt;i&gt;", "<p>Example</p>"]
    assert "".join(blocks(html)) == canonical(html)


def test_option_fragment_keeps_styled_container_and_other_paragraphs() -> None:
    html = '<div style="color:red"><p>First</p><p>Second</p></div>'
    assert canonical(fragment(html)) == canonical(html)
