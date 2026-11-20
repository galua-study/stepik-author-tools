"""Behavioral regression tests for course.legacy."""

from pathlib import Path

from stepik_author_tools import (
    load_course,
)
from stepik_author_tools.markdown.material import Material


def test_russian_map_multifile_and_fenced_headings(tmp_path: Path) -> None:
    (tmp_path / "intro.md").write_text("# Welcome\n", encoding="utf-8")
    topic = tmp_path / "Тема 1. Test"
    topic.mkdir()
    (topic / "body.md").write_text("More text.\n", encoding="utf-8")
    (topic / "README.md").write_text(
        "| 1 | [A](<../intro.md>) и [B](<body.md>) | text |", encoding="utf-8"
    )
    assert "More text" in load_course(topic).compile()[0].block.text
    task = Material(
        "## Task\n\n### Condition\n\n```python\n### Explanation\nprint(1)\n```\n\n"
        "### Correct answer\n\nSECRET\n\n### Explanation\n\nAUTHOR\n"
    )
    block = task.compile()
    assert "print(1)" in block.text and "SECRET" not in block.text and "AUTHOR" not in block.text


def test_legacy_module_orders_topics_numerically(tmp_path: Path) -> None:
    for number in (10, 2, 1):
        topic = tmp_path / f"Тема {number}. Demo"
        topic.mkdir()
        (topic / "lesson.md").write_text(f"# Lesson {number}\n", encoding="utf-8")
        (topic / "README.md").write_text("| 1 | [Lesson](<lesson.md>) | text |", encoding="utf-8")
    course = load_course(tmp_path)
    assert [t.id for t in course.topics()] == [f"Тема {i}. Demo" for i in (1, 2, 10)]
