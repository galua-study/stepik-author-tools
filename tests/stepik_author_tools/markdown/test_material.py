"""Behavioral regression tests for markdown.material."""

import pytest

from stepik_author_tools.markdown.material import Material
from tests.helpers import source_of


def test_unsupported_programming_and_text_entry_never_publish_solutions() -> None:
    for kind in ("программирование", "ввод текста", "заполнение пропусков"):
        material = Material(
            f"## Задание\n\n**Тип:** {kind}\n\n### Условие\n\nTask\n\n"
            "### Правильное решение\n\nSECRET"
        )
        with pytest.raises(ValueError, match="Unsupported"):
            material.compile()
    with pytest.raises(ValueError, match="Condition"):
        Material("# Task\n\n### Правильный ответ\n\nSECRET").compile()


def test_bold_answer_compatibility() -> None:
    material = Material(
        "## Task\n\n### Condition\n\nPick\n\n### Options\n\n1. A\n2. B\n\n"
        "### Correct answer\n\n**2.** B"
    )
    assert source_of(material.compile()).options[1].is_correct


def test_multiline_options_and_bullet_keys() -> None:
    material = Material(
        "## Task\n\n### Condition\n\nPick\n\n### Options\n\n"
        "Option 1:\n\n```python\nprint(1)\n```\n\n"
        "Option 2:\n\n```python\nprint(2)\n```\n\n"
        "### Correct answers\n\n- **1.** First\n- **2.** Second\n"
    )
    source = source_of(material.compile())
    assert source.is_multiple_choice
    assert all(o.is_correct for o in source.options)
    assert "<pre>" in source.options[0].text
