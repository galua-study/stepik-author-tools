"""Behavioral regression tests for sync.merge."""

from stepik_author_tools.sync.merge import merge_body


def test_disjoint_paragraphs_and_overlapping_code() -> None:
    b = "<p>One</p><p>Two</p>"
    assert merge_body(b, "<p>Local</p><p>Two</p>", "<p>One</p><p>Remote</p>") == (
        "<p>Local</p><p>Remote</p>",
        False,
    )
    assert merge_body("<pre>a\nb</pre>", "<pre>A\nb</pre>", "<pre>a\nB</pre>")[1]
