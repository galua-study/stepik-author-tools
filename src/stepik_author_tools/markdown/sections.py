"""Locate authoring sections without interpreting headings inside fenced code."""

import re
from dataclasses import dataclass
from typing import Literal, TypeAlias

SectionKey: TypeAlias = Literal[
    "condition", "options", "answer", "explanation", "left", "right", "transfer"
]
ALIASES: dict[SectionKey, tuple[str, ...]] = {
    "condition": ("Condition", "Условие"),
    "options": ("Options", "Варианты ответа"),
    "answer": (
        "Correct answer",
        "Correct answers",
        "Правильный ответ",
        "Правильные ответы",
        "Правильное решение",
        "Reference solution",
    ),
    "explanation": ("Explanation", "Объяснение"),
    "left": ("Left column", "Левая колонка"),
    "right": ("Right column", "Правая колонка"),
    "transfer": ("Transfer notes", "Для переноса в Stepik"),
}
AUTHOR_SECTIONS: tuple[SectionKey, ...] = (
    "options",
    "left",
    "right",
    "answer",
    "explanation",
    "transfer",
)


@dataclass(frozen=True)
class Section:
    """Offsets into the original document, including its untouched heading."""

    title: str
    heading_start: int
    content_start: int
    end: int


def headings(text: str) -> list[tuple[str, int, int]]:
    """Return level-three headings outside backtick and tilde fences."""
    result: list[tuple[str, int, int]] = []
    offset = 0
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and (heading := re.match(r"^### (.+?)\s*$", line)):
            result.append((heading[1], offset, offset + len(line)))
        offset += len(line)
    return result


def find_section(text: str, key: SectionKey) -> Section | None:
    """Find a known authoring section and its next heading boundary."""
    items = headings(text)
    for index, (title, heading_start, content_start) in enumerate(items):
        if title in ALIASES[key]:
            end = items[index + 1][1] if index + 1 < len(items) else len(text)
            return Section(title, heading_start, content_start, end)
    return None


def student_span(text: str) -> tuple[int, int]:
    """Keep self-check sections, stopping before the first grading/author heading."""
    condition = find_section(text, "condition")
    if condition is None:
        raise ValueError("Missing section: condition")
    boundaries = [
        section.heading_start
        for key in AUTHOR_SECTIONS
        if (section := find_section(text, key)) is not None
    ]
    return condition.content_start, min(boundaries, default=len(text))
