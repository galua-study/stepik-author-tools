"""Editable heading offsets follow CommonMark line breaks and structural nesting."""

import pytest

from stepik_author_tools.markdown.material import Material


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_student_span_preserves_unicode_paragraphs_and_excludes_keys(newline: str) -> None:
    source = newline.join(
        [
            "## Task",
            "",
            "### Condition",
            "",
            "First\u2028Second",
            "",
            "> ### Explanation",
            "",
            "### Explanation",
            "",
            "PRIVATE NOTE",
        ]
    )
    material = Material(source)
    assert material.body() == f"First\u2028Second{newline}{newline}> ### Explanation"
    assert material.get("explanation") == "PRIVATE NOTE"
