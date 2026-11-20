"""Map CommonMark headings back to editable spans in the original document."""

from dataclasses import dataclass
from io import StringIO
from itertools import accumulate

from ..config.authoring import MarkdownSettings
from .markup import MARKDOWN


@dataclass(frozen=True)
class Section:
    """Offsets for the heading and the original text below it."""

    heading_start: int
    content_start: int
    end: int


def parse_sections(text: str, dialect: MarkdownSettings) -> dict[str, Section]:
    """Index configured headings outside fences, block quotes and nested lists."""
    # CommonMark counts CR, LF and CRLF as line breaks. Unicode paragraph separators
    # remain inside a line and must not shift a later answer heading into student text.
    offsets = list(accumulate(map(len, StringIO(text, newline="")), initial=0))
    tokens = MARKDOWN.parse(text)
    headings = [
        (tokens[index + 1].content, offsets[token.map[0]], offsets[token.map[1]])
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == "h3" and token.level == 0 and token.map
    ]
    roles = {title: key for key, titles in dialect.author_sections.items() for title in titles}
    roles.update(dict.fromkeys(dialect.condition, "condition"))
    sections: dict[str, Section] = {}
    for index, (title, start, content) in enumerate(headings):
        if role := roles.get(title):
            end = headings[index + 1][1] if index + 1 < len(headings) else len(text)
            sections.setdefault(role, Section(start, content, end))
    return sections
