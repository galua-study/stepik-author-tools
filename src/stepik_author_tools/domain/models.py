"""Typed wire contracts and normalized domain values shared by the library.

TypedDict records retain the public JSON-compatible API. Immutable semantic values
are used inside comparison and merging, where missing or mixed field types would
otherwise be easy to overlook. Unknown Stepik source settings remain JSON values.
"""

from dataclasses import dataclass
from typing import Literal, NotRequired, TypeAlias, TypedDict

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
StepKind: TypeAlias = Literal["text", "choice", "matching"]


class ChoiceOption(TypedDict):
    """Author-visible option; a missing key is rejected during semantic validation."""

    text: str
    is_correct: NotRequired[bool]
    feedback: NotRequired[str]


class MatchingPair(TypedDict):
    """Two rendered fragments belonging to the same correct pair."""

    first: str
    second: str


class StepSource(TypedDict, total=False):
    """Known Stepik grading fields; validated JSON may retain extension settings."""

    options: list[ChoiceOption]
    pairs: list[MatchingPair]
    is_multiple_choice: bool
    is_always_correct: bool
    sample_size: int
    preserve_order: bool
    is_html_enabled: bool
    is_options_feedback: bool
    preserve_firsts_order: bool


class Block(TypedDict):
    """Stepik block payload; optional editor fields are unrelated to comparison."""

    name: str
    text: str
    source: NotRequired[StepSource | None]
    options: NotRequired[JsonObject]
    is_deprecated: NotRequired[bool]
    video: NotRequired[JsonValue]
    subtitles: NotRequired[JsonObject]
    subtitle_files: NotRequired[list[JsonValue]]
    tests_archive: NotRequired[JsonValue]
    feedback_correct: NotRequired[str]
    feedback_wrong: NotRequired[str]


class StepRecord(TypedDict):
    """Snapshot row; local compilation also populates id, topic and source paths."""

    stepik_id: int | None
    lesson: int | None
    position: int
    block: Block
    id: NotRequired[str]
    topic: NotRequired[str]
    paths: NotRequired[list[str]]


class Snapshot(TypedDict):
    """Complete selected lessons, optionally verified as a common merge base."""

    version: int
    steps: list[StepRecord]
    kind: NotRequired[str]


class StepSpec(TypedDict):
    """Stable local identity and either one path or ordered combined source paths."""

    id: str
    stepik_id: NotRequired[int | None]
    path: NotRequired[str]
    paths: NotRequired[list[str]]


class TopicSpec(TypedDict):
    """Ordered lesson manifest and its module membership."""

    id: str
    steps: list[StepSpec]
    module: NotRequired[str]
    lesson_id: NotRequired[int | None]


class Manifest(TypedDict):
    """Versioned source manifest, independent of the CLI and network transport."""

    version: int
    topics: list[TopicSpec]
    title: NotRequired[str]


class Conflict(TypedDict):
    """Reviewable three-way conflict; values are serializable without custom encoders."""

    step_id: str
    field: str
    base: JsonValue
    local: JsonValue
    remote: JsonValue


@dataclass(frozen=True)
class SemanticStep:
    """Normalized content and grading state, excluding transport/editor metadata."""

    kind: str
    body: str
    options: tuple[str, ...] = ()
    answers: tuple[int, ...] = ()
    pairs: tuple[tuple[str, str], ...] = ()
    settings: JsonObject | None = None
    feedback: tuple[str, ...] = ()

    def to_dict(self) -> JsonObject:
        """Expose comparison fields in the established machine-readable order."""
        return {
            "kind": self.kind,
            "body": self.body,
            "options": list(self.options),
            "answers": list(self.answers),
            "pairs": [list(pair) for pair in self.pairs],
            "settings": self.settings or {},
            "feedback": list(self.feedback),
        }


@dataclass(frozen=True)
class Change:
    """A single semantic or structural difference with an optional readable diff."""

    step_id: str
    position: int
    field: str
    before: JsonValue
    after: JsonValue
    message: str
    detail: str = ""

    def to_dict(self) -> JsonObject:
        """Serialize the public CLI/MCP-facing difference record."""
        return {
            "step_id": self.step_id,
            "position": self.position,
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PullResult:
    """Patch proposal only: preparing this value never changes course source files."""

    patch: str
    conflicts: list[Conflict]
    changed_files: list[str]
