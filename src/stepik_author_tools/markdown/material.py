"""Student/author document boundaries and compilation of a single source material."""

from ..config import load_settings
from ..config.authoring import MarkdownSettings, SectionKey
from ..domain.enums import StepKind
from ..domain.models import Block, StepSource
from .exercises import choice_source, matching_source
from .markup import render
from .sections import parse_sections


class Material:
    """Editable Markdown preserving all source sections outside an explicit edit.

    Section offsets are recalculated after each edit: caching offsets would corrupt
    later replacements when a preceding paragraph changes length.
    """

    def __init__(self, text: str, dialect: MarkdownSettings | None = None) -> None:
        self.dialect = dialect or load_settings().markdown
        self.text = text

    @property
    def text(self) -> str:
        """Return the original Markdown, including local author sections."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value
        self._sections = parse_sections(value, self.dialect)

    def section(self, key: SectionKey) -> tuple[int, int] | None:
        """Return the section content span, excluding its heading."""
        section = self._sections.get(key)
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
        title = self.text.splitlines()[0].lstrip("#").lstrip()
        return self.dialect.patterns.task_prefix.sub("", title, count=1)

    def body_span(self) -> tuple[int, int]:
        """Locate condition/self-check content before grading and author sections."""
        condition = self._sections.get("condition")
        if condition is None:
            raise ValueError("Missing section: condition")
        end = min(
            (
                section.heading_start
                for key, section in self._sections.items()
                if key != "condition"
            ),
            default=len(self.text),
        )
        if end < condition.content_start:
            raise ValueError("Author sections must follow the condition")
        return condition.content_start, end

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
        rules = self.dialect.patterns
        prefix = self.text[: self.body_span()[0]]
        if options := self.get("options"):
            return StepKind.CHOICE, choice_source(options, self.get("answer"), prefix, rules)
        if left := self.get("left"):
            return StepKind.MATCHING, matching_source(
                left, self.get("right"), self.get("answer"), rules
            )
        if rules.unsupported_layout.search(prefix):
            raise ValueError(
                "Unsupported exercise layout; use Left column / Right column for matching"
            )
        if metadata and not rules.self_check.search(metadata):
            raise ValueError(
                "Unsupported exercise type; only explicit local self-check tasks become text"
            )
        return StepKind.TEXT, StepSource()

    def compile(self) -> Block:
        """Compile student HTML and separate grading settings with empty feedback."""
        type_match = self.dialect.patterns.type_line.search(self.text)
        metadata = type_match["value"] if type_match else ""
        kind = StepKind.TEXT
        source = StepSource()
        if self.task:
            kind, source = self._grading(metadata)
            markdown = f"## {self.title}\n\n{self.body()}"
        elif metadata or self._sections:
            raise ValueError("Exercise/author sections require an explicit Condition heading")
        else:
            markdown = self.body()
        return Block(
            name=kind,
            text=render(markdown),
            source=source,
            options={},
            is_deprecated=False,
            video=None,
            subtitles={},
            subtitle_files=[],
            tests_archive=None,
            feedback_correct="",
            feedback_wrong="",
        )
