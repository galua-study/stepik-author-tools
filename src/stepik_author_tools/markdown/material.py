"""Student/author document boundaries and compilation of a single source material."""

import re
from dataclasses import dataclass

from ..domain.models import Block, StepKind, StepSource
from .exercises import choice_source, matching_source
from .markup import render
from .sections import SectionKey, find_section, student_span


@dataclass
class Material:
    """Editable Markdown preserving all source sections outside an explicit edit.

    Section offsets are recalculated after each edit: caching offsets would corrupt
    later replacements when a preceding paragraph changes length.
    """

    text: str

    def section(self, key: SectionKey) -> tuple[int, int] | None:
        """Return the section content span, excluding its heading."""
        section = find_section(self.text, key)
        return (section.content_start, section.end) if section else None

    def get(self, key: SectionKey) -> str:
        """Read a known section, or an empty string when absent."""
        span = self.section(key)
        return self.text[slice(*span)].strip() if span else ""

    def replace(self, key: SectionKey, value: str) -> None:
        """Replace only section content, retaining adjacent author sections."""
        span = self.section(key)
        if span is None:
            raise ValueError(f"Missing section: {key}")
        start, end = span
        self.text = self.text[:start] + "\n" + value.strip() + "\n\n" + self.text[end:]

    @property
    def task(self) -> bool:
        """Whether the document declares a separate student condition."""
        return self.section("condition") is not None

    @property
    def title(self) -> str:
        """Extract a student heading without the author's numbered task prefix."""
        title = re.sub(r"^#+\s*", "", self.text.splitlines()[0])
        return re.sub(r"^(?:Задание|Task)\s+[\d.]+\s*", "", title)

    def body_span(self) -> tuple[int, int]:
        """Locate condition/self-check content before grading and author sections."""
        return student_span(self.text)

    def body(self) -> str:
        """Return student Markdown only, including any local self-check steps."""
        return self.text[slice(*self.body_span())].strip() if self.task else self.text.strip()

    def replace_body(self, html: str) -> None:
        """Update student content without rewriting author explanations or keys."""
        if self.task:
            start, end = self.body_span()
            self.text = self.text[:start] + "\n" + html.strip() + "\n\n" + self.text[end:]
        else:
            self.text = html.strip() + "\n"

    def _grading(self, metadata: str) -> tuple[StepKind, StepSource]:
        if options := self.get("options"):
            prefix = self.text[: self.body_span()[0]]
            return "choice", choice_source(options, self.get("answer"), prefix)
        if left := self.get("left"):
            return "matching", matching_source(left, self.get("right"), self.get("answer"))
        prefix = self.text[: self.body_span()[0]]
        if re.search(r"сортиров|сопоставлен|упорядочив|sorting|matching", prefix, re.I):
            raise ValueError(
                "Unsupported exercise layout; use Left column / Right column for matching"
            )
        if metadata and not re.search(r"самопровер|self.check", metadata, re.I):
            raise ValueError(
                "Unsupported exercise type; only explicit local self-check tasks become text"
            )
        return "text", {}

    def compile(self) -> Block:
        """Compile student HTML and separate grading settings with empty feedback."""
        type_match = re.search(r"(?m)^\*\*(?:Тип|Type):\*\*\s*([^\n]+)", self.text)
        metadata = type_match[1] if type_match else ""
        kind: StepKind = "text"
        source: StepSource = {}
        if not self.task and (metadata or self.section("answer") or self.section("explanation")):
            raise ValueError("Exercise/author sections require an explicit Condition heading")
        if self.task:
            kind, source = self._grading(metadata)
        markdown = "## " + self.title + "\n\n" + self.body() if self.task else self.body()
        return {
            "name": kind,
            "text": render(markdown),
            "source": source,
            "options": {},
            "is_deprecated": False,
            "video": None,
            "subtitles": {},
            "subtitle_files": [],
            "tests_archive": None,
            "feedback_correct": "",
            "feedback_wrong": "",
        }
