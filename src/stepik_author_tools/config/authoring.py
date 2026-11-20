"""Validated course dialects for exercise Markdown and ordered lesson maps."""

import re
from typing import Annotated, Literal, Self, get_args

from pydantic import Field, model_validator

from .validation import ConfigModel, captures, placeholders

AuthorSection = Literal["options", "answer", "explanation", "left", "right", "transfer"]
SectionKey = Literal["condition", AuthorSection]
HeadingNames = Annotated[tuple[Annotated[str, Field(min_length=1)], ...], Field(min_length=1)]


class ExercisePatterns(ConfigModel):
    """Expressions for markers that are specific to an author's exercise format."""

    task_prefix: re.Pattern[str]
    type_line: Annotated[re.Pattern[str], captures("value")]
    multiple_choice: re.Pattern[str]
    self_check: re.Pattern[str]
    unsupported_layout: re.Pattern[str]
    numbered_item: Annotated[re.Pattern[str], captures("number")]
    option_heading: Annotated[re.Pattern[str], captures("number")]
    answer_list: Annotated[re.Pattern[str], captures("numbers")]
    answer_separator: re.Pattern[str]
    bullet_answer: Annotated[re.Pattern[str], captures("number")]
    right_item: Annotated[re.Pattern[str], captures("letter")]
    matching_pair: Annotated[re.Pattern[str], captures("number", "letter")]


class GradingFormat(ConfigModel):
    """Markdown emitted when pull updates an option list, answer key or matching pair."""

    numbered_item: Annotated[str, placeholders("number", "text")]
    right_item: Annotated[str, placeholders("letter", "text")]
    matching_pair: Annotated[str, placeholders("number", "letter")]
    answer_separator: Annotated[str, Field(min_length=1)]


class MarkdownSettings(ConfigModel):
    """Student headings and author-only headings have separate roles in the dialect."""

    condition: HeadingNames
    author_sections: dict[str, HeadingNames]
    patterns: ExercisePatterns
    format: GradingFormat

    @model_validator(mode="after")
    def check_headings(self) -> Self:
        """Every grading section needs aliases, and a heading may have only one role."""
        required = set(get_args(AuthorSection))
        if missing := required - self.author_sections.keys():
            raise ValueError(f"Missing author sections: {', '.join(sorted(missing))}")
        if "condition" in self.author_sections:
            raise ValueError("The condition is a student section")
        aliases = [*self.condition, *(h for group in self.author_sections.values() for h in group)]
        if len(aliases) != len(set(aliases)):
            raise ValueError("Each heading alias must have exactly one role")
        return self


class MapSettings(ConfigModel):
    """Legacy topic naming and row, link and lesson-ID conventions."""

    topic_folder: re.Pattern[str]
    row: Annotated[re.Pattern[str], captures("number", "cell")]
    link: Annotated[re.Pattern[str], captures("path")]
    lesson: Annotated[re.Pattern[str], captures("id")]
